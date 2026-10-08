"""Agent persistence. Only durable inbox controls can commit list mutations."""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Literal
from uuid import uuid4

from catalog import resolve_product
from dialogue import parse_answer
from dialogue_controller import reduce_dialogue
from dialogue_replies import render_dialogue_result
from domain import IncomingMessage, Model, Reply, utc
from interpreter import diaper_reference, parse_command, purchase_authorized
from shopping_agent.contracts import (
    AgentProposal,
    AgentSnapshot,
    CompleteProposal,
    ProposalDecision,
    ProposeAdds,
    ProposeChange,
    Reservation,
    ToolResult,
)
from shopping_agent.proposals import (
    _revalidate,
    answer_proposal,
    complete_proposal,
    parse_control,
    prepare_proposal,
)
from shopping_agent.replies import MAX_REPLY, TOO_LONG, render_proposal


class EmptyArguments(Model):
    pass


# Fixed mutation catalog; reads are dispatched separately by Task 4.
OPERATION_CONTRACTS = {
    'proponer_altas': ProposeAdds,
    'proponer_cambio': ProposeChange,
    'completar_propuesta': CompleteProposal,
    'cancelar_propuesta': EmptyArguments,
}
CONTROL_WORDS = {'si', 'confirmo', 'confirmar', 'no', 'cancelar'}


def _raw_json(value):
    if type(value) is dict:
        return all(type(key) is str and _raw_json(item) for key, item in value.items())
    if type(value) is list:
        return all(_raw_json(item) for item in value)
    return value is None or type(value) in {str, int, float, bool}


class AgentRepository:
    @staticmethod
    def _agent_source(db, update_id):
        if type(update_id) is not int:
            raise ValueError('Invalid inbox update')
        source = db.execute('SELECT * FROM inbox WHERE update_id=?', (update_id,)).fetchone()
        if source is None:
            raise KeyError(update_id)
        return source

    @staticmethod
    def _agent_message(source):
        return IncomingMessage(**{k: source[k] for k in ('update_id', 'user_id', 'chat_id', 'text')})

    def _agent_snapshot(self, db, source):
        message = self._agent_message(source)
        snapshot = AgentSnapshot(
            user_id=message.user_id, chat_id=message.chat_id,
            source_update_id=message.update_id, original_text=message.text,
            lines=tuple(self._lines(db)), reservations=tuple(
                Reservation(**dict(row)) for row in db.execute('SELECT line_id,order_id FROM reservations')))
        proposal = self._read_agent_proposal(db, snapshot)
        return snapshot.model_copy(update={'proposal': proposal})

    def _read_agent_proposal(self, db, snapshot):
        row = db.execute('SELECT proposal_json FROM agent_proposals WHERE user_id=? AND chat_id=?',
                         (snapshot.user_id, snapshot.chat_id)).fetchone()
        if row is None:
            return None
        try:
            proposal = AgentProposal.model_validate_json(row[0])
            if (proposal.user_id, proposal.chat_id) != (snapshot.user_id, snapshot.chat_id):
                raise ValueError('Proposal owner mismatch')
            original = self._agent_source(db, proposal.source_update_id)
            original_notices = db.execute('SELECT chat_id,reply_json FROM outbox WHERE update_id=?',
                                          (proposal.source_update_id,)).fetchall()
            if ((original['user_id'], original['chat_id'], original['text']) !=
                    (proposal.user_id, proposal.chat_id, proposal.original_text)
                    or not original['completed'] or len(original_notices) != 1
                    or original_notices[0]['chat_id'] != proposal.chat_id
                    or original_notices[0]['reply_json'] != original['reply_json']
                    or original['text'].strip().startswith('/') or purchase_authorized(original['text'])):
                raise ValueError('Proposal source mismatch')
            Reply.model_validate_json(original['reply_json'])
            if proposal.reviewed_update_id is not None:
                review = self._agent_source(db, proposal.reviewed_update_id)
                notices = db.execute('SELECT chat_id,reply_json FROM outbox WHERE update_id=?',
                                     (proposal.reviewed_update_id,)).fetchall()
                if (not review['completed'] or proposal.reviewed_update_id < proposal.source_update_id
                        or (review['user_id'], review['chat_id']) != (proposal.user_id, proposal.chat_id)
                        or len(notices) != 1 or notices[0]['chat_id'] != proposal.chat_id
                        or notices[0]['reply_json'] != review['reply_json']):
                    raise ValueError('Review lacks committed inbox/outbox witness')
                # Changed rows are rejected by the reducer. Otherwise the committed
                # full summary must describe exactly this persisted revision.
                if _revalidate(proposal, snapshot) not in {'stale', 'reserved'}:
                    expected = render_proposal(ProposalDecision(proposal=proposal, reason='reviewed'), snapshot)
                    if expected.text == TOO_LONG or Reply.model_validate_json(review['reply_json']) != expected:
                        raise ValueError('Review content mismatch')
            return proposal
        except (ValueError, KeyError):
            return None

    def agent_snapshot(self, update_id: int, *, now: datetime) -> AgentSnapshot:
        utc(now)
        with self._connection() as db:
            # Explicit read transaction gives rows, reservations and proposal one view.
            db.execute('BEGIN')
            return self._agent_snapshot(db, self._agent_source(db, update_id))

    @staticmethod
    def _write_agent_proposal(db, source, proposal):
        key = (source['user_id'], source['chat_id'])
        if proposal is None:
            db.execute('DELETE FROM agent_proposals WHERE user_id=? AND chat_id=?', key)
        else:
            proposal = AgentProposal.model_validate_json(proposal.model_dump_json())
            if (proposal.user_id, proposal.chat_id) != key:
                raise ValueError('Proposal owner mismatch')
            db.execute('INSERT INTO agent_proposals VALUES (?,?,?) ON CONFLICT(user_id,chat_id) '
                       'DO UPDATE SET proposal_json=excluded.proposal_json', (*key, proposal.model_dump_json()))

    def _commit_agent_decision(self, db, source, decision, snapshot):
        reply = render_proposal(decision, snapshot)
        proposal = decision.proposal
        if (proposal is not None and proposal.reviewed_update_id == source['update_id']
                and (decision.reason != 'reviewed' or reply.text == TOO_LONG or len(reply.text) > MAX_REPLY)):
            proposal = proposal.model_copy(update={'reviewed_revision': None, 'reviewed_update_id': None})
        if decision.reason == 'confirmed':
            for mutation in decision.mutations:
                if diaper_reference(mutation.description) and mutation.unit not in {'paquetes', 'envases'}:
                    raise ValueError('Explicit package unit required')
                if mutation.kind == 'add':
                    db.execute('INSERT INTO list_lines VALUES (?,?,?,?,1,?)',
                               (str(uuid4()), resolve_product(mutation.description), mutation.description,
                                mutation.quantity, source['update_id']))
                else:
                    target = mutation.target
                    changed = db.execute(
                        'UPDATE list_lines SET description=?,product_id=?,quantity=?,revision=revision+1 '
                        'WHERE id=? AND revision=? AND NOT EXISTS '
                        '(SELECT 1 FROM reservations WHERE line_id=?)',
                        (mutation.description, resolve_product(mutation.description), mutation.quantity,
                         target.id, target.revision, target.id))
                    if changed.rowcount != 1:
                        raise ValueError('Mutation requires exactly one current unreserved row')
            proposal = None
            reply = Reply(text=f'Lote guardado: {len(decision.mutations)} cambios confirmados. La lista se ha actualizado.')
        self._write_agent_proposal(db, source, proposal)
        if proposal is not None:
            db.execute('DELETE FROM dialogue_state WHERE user_id=? AND chat_id=?',
                       (source['user_id'], source['chat_id']))
            db.execute('UPDATE conversation_routes SET command_update_id=NULL WHERE user_id=? AND chat_id=?',
                       (source['user_id'], source['chat_id']))
        return self._complete_reply(db, source, reply)

    def apply_agent_operation(self, update_id: int, name: str, arguments: dict,
                              expected_revision: int | None, *, now: datetime) -> ToolResult:
        utc(now)
        with self._connection(write=True) as db:
            source = self._agent_source(db, update_id)
            if (type(name) is not str or name not in OPERATION_CONTRACTS
                    or type(arguments) is not dict or not _raw_json(arguments)):
                raise ValueError('Unknown operation or invalid arguments')
            if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 1):
                raise ValueError('Invalid application revision')
            args = OPERATION_CONTRACTS[name].model_validate_json(json.dumps(arguments, allow_nan=False))
            if source['completed']:
                reply = Reply.model_validate_json(source['reply_json'])
            elif (prepared := self._read_prepared(db, update_id)) is not None:
                reply = self._complete_reply(db, source, prepared.snapshot.fallback)
            else:
                message = self._agent_message(source)
                if message.text.strip().startswith('/') or purchase_authorized(message.text):
                    raise ValueError('Deterministic commands cannot enter the agent mutation path')
                snapshot = self._agent_snapshot(db, source)
                if name in {'proponer_altas', 'proponer_cambio'}:
                    decision = prepare_proposal(message, args, snapshot, now=now)
                elif name == 'cancelar_propuesta':
                    decision = ProposalDecision(reason='cancelled')
                elif snapshot.proposal is None or snapshot.proposal.revision != expected_revision:
                    decision = ProposalDecision(reason='stale' if snapshot.proposal else 'no_pending')
                else:
                    decision = complete_proposal(message, args, snapshot, now=now)
                reply = self._commit_agent_decision(db, source, decision, snapshot)
            return ToolResult(name=name, data={'reply': reply.model_dump(mode='json')}, reply=reply, terminal=True)

    def apply_agent_control(self, update_id: int, *, now: datetime) -> Reply | None:
        from dialogue import canonical_name
        utc(now)
        with self._connection(write=True) as db:
            source = self._agent_source(db, update_id)
            if source['completed']:
                return Reply.model_validate_json(source['reply_json'])
            prepared = self._read_prepared(db, update_id)
            if prepared is not None:
                return self._complete_reply(db, source, prepared.snapshot.fallback)
            message = self._agent_message(source)
            snapshot = self._agent_snapshot(db, source)
            if (canonical_name(message.text) not in CONTROL_WORDS
                    and parse_control(message.text, snapshot.proposal, now=now) is None):
                return None
            decision = answer_proposal(message, snapshot, now=now)
            return self._commit_agent_decision(db, source, decision, snapshot)

    def complete_agent_reply(self, update_id: int, reply: Reply) -> Reply:
        with self._connection(write=True) as db:
            source = self._agent_source(db, update_id)
            if source['completed']:
                return Reply.model_validate_json(source['reply_json'])
            prepared = self._read_prepared(db, update_id)
            if prepared is not None:
                reply = prepared.snapshot.fallback
            if reply.order_id is not None:
                raise ValueError('Agent replies cannot authorize an order')
            return self._complete_reply(db, source, reply)

    def _command_context_reply(self, db, message, state):
        """Replay only a deterministic command, never arbitrary natural requests."""
        if state is None or state.question is None or not (
                message.text.strip().startswith('/') or purchase_authorized(message.text)):
            return None
        lines = self._lines(db)
        intent = parse_command(message.text, lines)
        if intent is None or intent.action not in {'add', 'buy', 'clarify'}:
            return None
        if intent.action == 'clarify' and not intent.lines:
            return None
        reserved = frozenset(row[0] for row in db.execute('SELECT line_id FROM reservations'))
        decision = reduce_dialogue(message, None, None, lines, reserved, now=state.updated_at)
        expected = decision.state
        if expected is None or expected.question is None or decision.mutation is not None:
            return None
        # A duplicate slash addition can legitimately select a saved total.
        # Match the exact offered references and transition fields, not just an ID.
        if expected.question == 'duplicate_choice' and state.question == 'select_line':
            expected = expected.model_copy(update={
                'question': 'select_line', 'options': ('change_quantity',), 'pending_kind': None})
        elif (expected.question == 'duplicate_choice' and state.question == 'quantity'
              and state.target in expected.candidates):
            expected = expected.model_copy(update={
                'question': 'quantity', 'target': state.target, 'candidates': (), 'options': (),
                'pending_kind': None, 'duplicate_confirmed': False, 'proposal_quantity': None,
                'focus': expected.focus.model_copy(update={'line': state.target})})
        elif (expected.question == 'duplicate_choice' and state.question == 'add_quantity'
              and state.duplicate_confirmed):
            expected = self._trace_duplicate_add_choice(db, message, expected, state, lines, reserved)
            if expected is None:
                return None
        excluded = {'updated_at', 'expires_at'}
        if state.model_dump(exclude=excluded) != expected.model_dump(exclude=excluded):
            return None
        return render_dialogue_result(decision, None, lines, None)

    def _trace_duplicate_add_choice(self, db, origin, initial, retained, lines, reserved):
        """Accredit the separate-line choice only through its committed transition."""
        excluded = {'updated_at', 'expires_at'}
        for source in db.execute(
            'SELECT * FROM inbox WHERE user_id=? AND chat_id=? AND completed=1 '
            'AND update_id>? ORDER BY update_id DESC',
            (origin.user_id, origin.chat_id, origin.update_id),
        ):
            message = self._agent_message(source)
            answer = parse_answer(message.text, initial, now=retained.updated_at)
            if answer is None or not (answer.kind == 'add' or (
                    answer.kind == 'select' and initial.options[answer.selection - 1] == 'add')):
                continue
            decision = reduce_dialogue(message, None, initial, lines, reserved, now=retained.updated_at)
            if (decision.mutation is not None or decision.state is None
                    or decision.state.model_dump(exclude=excluded) != retained.model_dump(exclude=excluded)):
                continue
            reply = render_dialogue_result(decision, None, lines, None)
            if self._committed_reply_matches(db, source, reply):
                return decision.state
        return None

    def _command_origin(self, db, user_id, chat_id):
        state = self._read_dialogue_state(db, user_id, chat_id)
        row = db.execute('SELECT command_update_id FROM conversation_routes WHERE user_id=? AND chat_id=?',
                         (user_id, chat_id)).fetchone()
        if row is None:
            # Migrated legacy context may already carry an inbox-backed focus.
            update_id = state.focus.source_update_id if state and state.focus else None
            if state and state.question == 'remove_id' and state.focus is None:
                # Removal state has no focus/source field. Accredit only a committed
                # removal command whose deterministic candidates and reply match.
                for source in db.execute(
                    "SELECT * FROM inbox WHERE user_id=? AND chat_id=? AND completed=1 "
                    "AND text LIKE '/quitar %' ORDER BY update_id DESC", (user_id, chat_id)
                ):
                    if self._committed_command_context(db, source, state):
                        return self._agent_message(source)
        else:
            update_id = row[0]
        if update_id is None:
            return None
        source = self._agent_source(db, update_id)
        message = self._agent_message(source)
        if (message.user_id, message.chat_id) != (user_id, chat_id):
            raise ValueError('Command origin owner mismatch')
        if not self._committed_command_context(db, source, state):
            return None
        return message

    def _committed_command_context(self, db, source, state):
        if not source['completed']:
            return False
        expected = self._command_context_reply(db, self._agent_message(source), state)
        return expected is not None and self._committed_reply_matches(db, source, expected)

    @staticmethod
    def _committed_reply_matches(db, source, expected):
        if not source['completed'] or Reply.model_validate_json(source['reply_json']) != expected:
            return False
        notices = db.execute('SELECT chat_id,reply_json FROM outbox WHERE update_id=?',
                             (source['update_id'],)).fetchall()
        return (len(notices) == 1 and notices[0]['chat_id'] == source['chat_id']
                and notices[0]['reply_json'] == source['reply_json'])

    def command_origin(self, user_id: int, chat_id: int) -> IncomingMessage | None:
        with self._connection() as db:
            try:
                return self._command_origin(db, user_id, chat_id)
            except (ValueError, KeyError):
                return None

    def _record_command_origin(self, db: sqlite3.Connection, source: sqlite3.Row) -> None:
        durable = self._agent_source(db, source['update_id'])
        if self._agent_message(durable) != self._agent_message(source):
            raise ValueError('Command must come from durable inbox')
        message = self._agent_message(durable)
        state = self._read_dialogue_state(db, message.user_id, message.chat_id)
        if self._command_context_reply(db, message, state) is None:
            raise ValueError('Command did not create this retained continuation')
        db.execute('INSERT INTO conversation_routes VALUES (?,?,?,?) ON CONFLICT(user_id,chat_id) '
                   'DO UPDATE SET command_update_id=excluded.command_update_id',
                   (message.user_id, message.chat_id, 'legacy', message.update_id))
        self._write_agent_proposal(db, durable, None)

    def set_conversation_route(self, user_id: int, chat_id: int,
                               route: Literal['legacy', 'agent'], *, now: datetime) -> bool:
        utc(now)
        if route not in {'legacy', 'agent'} or type(user_id) is not int or type(chat_id) is not int:
            raise ValueError('Invalid conversation route')
        with self._connection(write=True) as db:
            previous = db.execute('SELECT * FROM conversation_routes WHERE user_id=? AND chat_id=?',
                                  (user_id, chat_id)).fetchone()
            if previous is not None and previous['route'] == route:
                return False
            command = None
            if route == 'agent':
                try:
                    command = self._command_origin(db, user_id, chat_id)
                except (ValueError, KeyError):
                    pass
            discarded = db.execute('SELECT 1 FROM agent_proposals WHERE user_id=? AND chat_id=?',
                                   (user_id, chat_id)).fetchone() is not None
            preserve_legacy = previous is None and route == 'legacy' and not discarded
            if command is None and not preserve_legacy:
                discarded = discarded or self._read_dialogue_state(db, user_id, chat_id) is not None
            db.execute('DELETE FROM agent_proposals WHERE user_id=? AND chat_id=?', (user_id, chat_id))
            if command is None and not preserve_legacy:
                db.execute('DELETE FROM dialogue_state WHERE user_id=? AND chat_id=?', (user_id, chat_id))
            db.execute('INSERT INTO conversation_routes VALUES (?,?,?,?) ON CONFLICT(user_id,chat_id) '
                       'DO UPDATE SET route=excluded.route,command_update_id=excluded.command_update_id',
                        (user_id, chat_id, route, command.update_id if command else None))
            if discarded:
                logging.getLogger('runtime').warning('Incompatible conversation memory discarded; review a new proposal before confirming')
            return True

    def revoke_agent_proposals(self) -> None:
        """Explicit local switches revoke permissions even without intervening turns."""
        with self._connection(write=True) as db:
            db.execute('DELETE FROM agent_proposals')
