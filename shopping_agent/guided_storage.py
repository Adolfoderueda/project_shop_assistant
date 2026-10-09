"""Transaction-owned guided choices, provenance and delivery witnesses."""

import secrets
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from catalog import resolve_product
from domain import IncomingCallback, IncomingMessage, InlineButton, InlineKeyboard, Reply, utc
from interpreter import diaper_reference, purchase_authorized
from shopping_agent.contracts import AgentSnapshot, Contribution, GuidedProposal, Reservation
from shopping_agent.guided_contracts import (
    ChangeCandidate,
    GuidedAnswer,
    GuidedDecision,
    GuidedQuestion,
    GuidedState,
    PendingTopic,
    ResolvedChoice,
    TopicCandidate,
    decode_guided_answer,
)
from shopping_agent.guided_controller import reduce_guided, resolve_text_choice
from shopping_agent.guided_replies import render_question, render_review, review_fits
from shopping_agent.proposals import prepare_proposal, revalidate_proposal


def _digest(text):
    return sha256(text.encode('utf-8')).hexdigest()


class GuidedRepository:
    def _guided_question_row(self, db, row):
        q = GuidedQuestion.model_validate_json(row['question_json'])
        if (str(q.id), q.version, q.owner_id, q.chat_id, q.source_update_id) != (
                row['id'], row['version'], row['user_id'], row['chat_id'], row['source_update_id']):
            raise ValueError('Question metadata mismatch')
        source = self._agent_source(db, q.source_update_id)
        event = self._stored_event(source)
        notice = self._delivery_notice(db, row['notice_id'], q.chat_id, 1, 'validation')
        if ((event.user_id, event.chat_id) != (q.owner_id, q.chat_id)
                or notice['update_id'] != q.source_update_id
                or Reply.model_validate_json(notice['reply_json']).text != render_question(q).text):
            raise ValueError('Question source/notice mismatch')
        return q

    def _guided_token_row(self, db, row):
        if row is None:
            raise ValueError('Unknown choice')
        question_row = db.execute('SELECT * FROM guided_questions WHERE id=? AND version=?',
            (row['question_id'], row['question_version'])).fetchone()
        if question_row is None:
            raise ValueError('Orphan choice')
        q = self._guided_question_row(db, question_row)
        if ((row['user_id'], row['chat_id'], row['notice_id']) !=
                (q.owner_id, q.chat_id, question_row['notice_id'])
                or not 0 <= row['choice_index'] < len(q.choices)):
            raise ValueError('Choice binding mismatch')
        notice = db.execute('SELECT reply_json FROM outbox WHERE id=?', (row['notice_id'],)).fetchone()
        reply = Reply.model_validate_json(notice[0])
        buttons = [b for line in reply.keyboard.rows for b in line] if reply.keyboard else []
        if (len(buttons) != len(q.choices) or buttons[row['choice_index']].token != row['token']
                or buttons[row['choice_index']].label != q.choices[row['choice_index']].label):
            raise ValueError('Choice was not offered')
        if row['consumed_update_id'] is not None:
            source = self._agent_source(db, row['consumed_update_id'])
            event = self._stored_event(source)
            result = Reply.model_validate_json(row['result_json'])
            if ((event.user_id, event.chat_id) != (q.owner_id, q.chat_id)
                    or not self._committed_reply_matches(db, source, result)):
                raise ValueError('Choice result mismatch')
            if isinstance(event, IncomingCallback):
                if event.data != row['token'] or not self._guided_receipt(db, row, event, q):
                    raise ValueError('Unauthenticated consumed callback')
            else:
                choice = resolve_text_choice(event, q.model_copy(update={'status': 'active'}))
                if choice is None or choice.choice_index != row['choice_index']:
                    raise ValueError('Unauthenticated consumed text choice')
        elif row['result_json'] is not None:
            raise ValueError('Orphan choice result')
        return q

    def _guided_receipt(self, db, token, event, q):
        digest = _digest(render_question(q).text)
        self._delivery_notice(db, token['notice_id'], event.chat_id, event.message_id, digest)
        return db.execute('SELECT 1 FROM telegram_deliveries WHERE notice_id=? AND chat_id=? '
            'AND message_id=? AND digest=?',
            (token['notice_id'], event.chat_id, event.message_id, digest)).fetchone() is not None

    def _validate_guided_proposal(self, db, proposal, snapshot):
        original = self._agent_source(db, proposal.source_update_id)
        event = self._stored_event(original)
        if (not isinstance(event, IncomingMessage)
                or (event.user_id, event.chat_id, event.text) !=
                (proposal.user_id, proposal.chat_id, proposal.original_text)
                or event.text.strip().startswith('/') or purchase_authorized(event.text)):
            raise ValueError('Guided original source mismatch')
        positions = {item.position for item in proposal.items}
        if not any(c.kind == 'create' and c.update_id == proposal.source_update_id
                   for c in proposal.contributions):
            raise ValueError('Missing original contribution')
        for contribution in proposal.contributions:
            source = self._agent_source(db, contribution.update_id)
            event = self._stored_event(source)
            reply = Reply.model_validate_json(source['reply_json']) if source['completed'] else None
            if ((event.user_id, event.chat_id) != (proposal.user_id, proposal.chat_id)
                    or not set(contribution.positions) <= positions or reply is None
                    or not self._committed_reply_matches(db, source, reply)):
                raise ValueError('Contribution source mismatch')
            if isinstance(event, IncomingCallback):
                if contribution.kind not in {'edit', 'decision'}:
                    raise ValueError('Callback cannot originate a proposal or topic')
                token = db.execute('SELECT * FROM guided_tokens WHERE token=? AND consumed_update_id=?',
                                   (event.data, event.update_id)).fetchone()
                self._guided_token_row(db, token)
        witness = proposal.review
        if witness is not None:
            row = db.execute('SELECT * FROM guided_questions WHERE id=? AND notice_id=?',
                             (str(witness.question_id), witness.notice_id)).fetchone()
            if row is None:
                raise ValueError('Missing review question')
            q = self._guided_question_row(db, row)
            state = GuidedState(snapshot=snapshot.model_copy(update={'proposal': proposal}), review=witness)
            # A legitimate later row edit/reservation makes permission stale, not provenance corrupt.
            summary = (Reply(text=q.text) if revalidate_proposal(proposal, snapshot) in {'stale', 'reserved'}
                       else render_review(state))
            if (q.kind != 'review' or q.status != 'active' or q.proposal_id != proposal.id
                    or q.proposal_revision != proposal.revision or q.source_update_id != witness.source_update_id
                    or q.text != summary.text or not review_fits(summary)
                    or witness.summary_digest != _digest(summary.text)):
                raise ValueError('Review content mismatch')
            if (witness.delivered_message_id is not None
                    and db.execute('SELECT 1 FROM telegram_deliveries WHERE notice_id=? AND chat_id=? '
                    'AND message_id=? AND digest=?', (witness.notice_id, proposal.chat_id,
                    witness.delivered_message_id, witness.summary_digest)).fetchone() is None):
                raise ValueError('Review delivery mismatch')
        return proposal

    def _guided_state(self, db, source, *, now):
        event = self._stored_event(source)
        snapshot = AgentSnapshot(user_id=event.user_id, chat_id=event.chat_id,
            source_update_id=event.update_id, original_text=event.text if isinstance(event, IncomingMessage) else '',
            lines=tuple(self._lines(db)), reservations=tuple(Reservation(**dict(row)) for row in
            db.execute('SELECT line_id,order_id FROM reservations')))
        proposal = self._read_agent_proposal(db, snapshot)
        snapshot = snapshot.model_copy(update={'proposal': proposal})
        if proposal is None:
            return GuidedState(snapshot=snapshot)
        try:
            row = db.execute("SELECT * FROM guided_questions WHERE user_id=? AND chat_id=? "
                "AND json_extract(question_json,'$.status')='active'", (event.user_id, event.chat_id)).fetchone()
            q = self._guided_question_row(db, row) if row else None
            if q is not None:
                tokens = db.execute('SELECT * FROM guided_tokens WHERE question_id=? AND question_version=?',
                                    (str(q.id), q.version)).fetchall()
                if (len(tokens) != len(q.choices)
                        or {t['choice_index'] for t in tokens} != set(range(len(q.choices)))):
                    raise ValueError('Question choice set mismatch')
                for token in tokens:
                    self._guided_token_row(db, token)
            topics = db.execute('SELECT * FROM guided_topics WHERE user_id=? AND chat_id=?',
                               (event.user_id, event.chat_id)).fetchall()
            if len(topics) > 1:
                raise ValueError('Multiple pending topics')
            topic = None
            if topics:
                row = topics[0]
                topic = PendingTopic.model_validate_json(row['topic_json'])
                original = self._agent_source(db, topic.source_update_id)
                origin = self._stored_event(original)
                if (not isinstance(origin, IncomingMessage) or not original['completed']
                        or (origin.user_id, origin.chat_id, origin.text) !=
                        (event.user_id, event.chat_id, topic.original_text)
                        or (row['id'], row['version'], row['source_update_id']) !=
                        (str(topic.id), topic.version, topic.source_update_id)
                        or not self._committed_reply_matches(db, original,
                            Reply.model_validate_json(original['reply_json']))):
                    raise ValueError('Topic source mismatch')
            return GuidedState(snapshot=snapshot, question=q, topic=topic,
                               review=proposal.review if isinstance(proposal, GuidedProposal) else None)
        except (ValueError, KeyError, TypeError):
            return GuidedState(snapshot=snapshot.model_copy(update={'proposal': None}))

    def guided_state(self, update_id: int, *, now: datetime) -> GuidedState:
        utc(now)
        with self._connection() as db:
            db.execute('BEGIN')
            return self._guided_state(db, self._agent_source(db, update_id), now=now)

    def apply_guided(self, update_id: int, answer: GuidedAnswer | ResolvedChoice | None, *,
                     expected_question_version: int | None, now: datetime) -> Reply:
        utc(now)
        supplied_choice = answer if isinstance(answer, ResolvedChoice) else None
        if expected_question_version is not None and (
                type(expected_question_version) is not int or expected_question_version < 1):
            raise ValueError('Invalid expected question version')
        if answer is not None and supplied_choice is None:
            answer = decode_guided_answer(answer.model_dump(mode='json'))
        with self._connection(write=True) as db:
            source = self._agent_source(db, update_id)
            event = self._stored_event(source)
            if not isinstance(event, IncomingMessage):
                raise TypeError('Use the authenticated callback entry point')
            if source['completed']:
                return Reply.model_validate_json(source['reply_json'])
            if event.text.strip().startswith('/') or purchase_authorized(event.text):
                raise ValueError('Deterministic commands cannot enter guided mutation')
            state = self._guided_state(db, source, now=now)
            version = state.question.version if state.question else None
            if version != expected_question_version:
                return self._complete_reply(db, source, Reply(text='Pregunta anterior. Responde a la pregunta vigente.'))
            if state.snapshot.proposal is None and isinstance(answer, (TopicCandidate, ChangeCandidate)):
                if answer.source_update_id != event.update_id:
                    raise ValueError('Candidate source mismatch')
                args = answer.adds if isinstance(answer, TopicCandidate) else answer.change
                initial = prepare_proposal(event, args, state.snapshot, now=now).proposal
                if initial is not None:
                    proposal = GuidedProposal.model_validate({**initial.__dict__, 'schema_version': 2,
                        'contributions': (Contribution(update_id=event.update_id,
                            positions=tuple(i.position for i in initial.items), kind='create'),)})
                    state = GuidedState(snapshot=state.snapshot.model_copy(update={'proposal': proposal}))
                    answer = None
            # Only application dispatch can supply choice authority. None is the
            # published deterministic fallback; model candidates stay candidates.
            resolved = (resolve_text_choice(event, state.question)
                        if state.question and (answer is None or supplied_choice is not None) else None)
            if supplied_choice is not None and supplied_choice != resolved:
                raise ValueError('Choice does not match the durable text and current question')
            if resolved is not None:
                answer = resolved
            decision = reduce_guided(state, event, answer, now=now)
            if (resolved is not None and state.question.kind == 'review'
                    and state.question.choices[resolved.choice_index].kind == 'confirm'
                    and decision.reason == 'pending' and state.review is not None
                    and state.review.delivered_message_id is None):
                decision = self._resend_guided_question(state, event, now)
            token = None
            if resolved is not None:
                token = db.execute('SELECT * FROM guided_tokens WHERE question_id=? AND question_version=? '
                    'AND choice_index=?', (str(resolved.question_id), resolved.question_version,
                    resolved.choice_index)).fetchone()
                if token is None:
                    raise ValueError('Missing offered text choice')
                self._guided_token_row(db, token)
            return self._commit_guided(db, source, state, decision, token=token, now=now)

    def apply_guided_callback(self, update_id: int, *, now: datetime) -> Reply:
        utc(now)
        with self._connection(write=True) as db:
            source = self._agent_source(db, update_id)
            event = self._stored_event(source)
            if not isinstance(event, IncomingCallback):
                raise TypeError('Expected callback event')
            if source['completed']:
                return Reply.model_validate_json(source['reply_json'])
            token = db.execute('SELECT * FROM guided_tokens WHERE token=?', (event.data,)).fetchone()
            resend = None
            try:
                q = self._guided_token_row(db, token)
                if (event.user_id, event.chat_id) != (q.owner_id, q.chat_id):
                    raise ValueError('Callback owner mismatch')
                receipt = self._guided_receipt(db, token, event, q)
                if not receipt:
                    state = self._guided_state(db, source, now=now)
                    if q.status == 'active' and now < q.expires_at and state.question == q:
                        resend = self._resend_guided_question(state, event, now)
                    else:
                        raise ValueError('Unknown delivery')
                if receipt and token['consumed_update_id'] is not None:
                    return self._complete_reply(db, source, Reply.model_validate_json(token['result_json']))
                state = self._guided_state(db, source, now=now)
                if (q.status != 'active' or now >= q.expires_at or state.question != q
                        or state.snapshot.proposal is None or now >= state.snapshot.proposal.expires_at):
                    raise ValueError('Old question')
            except (ValueError, KeyError, TypeError):
                return self._complete_reply(db, source, Reply(text='Pregunta anterior o entrega desconocida. '
                    'Responde a la pregunta vigente.'))
            if resend is not None:
                return self._commit_guided(db, source, state, resend, now=now)
            answer = ResolvedChoice(question_id=q.id, question_version=q.version,
                choice_index=token['choice_index'], source_update_id=event.update_id)
            decision = reduce_guided(state, event, answer, now=now)
            return self._commit_guided(db, source, state, decision, token=token, now=now)

    @staticmethod
    def _resend_guided_question(state, event, now):
        q = state.question.model_copy(update={'id': uuid4(), 'version': state.question.version + 1,
            'source_update_id': event.update_id, 'created_at': now})
        witness = state.review
        proposal = state.snapshot.proposal
        if witness is not None:
            witness = witness.model_copy(update={'question_id': q.id, 'source_update_id': event.update_id,
                                                 'notice_id': str(q.id), 'delivered_message_id': None})
            proposal = proposal.model_copy(update={'review': witness})
        renewed = GuidedState(snapshot=state.snapshot.model_copy(update={'proposal': proposal}),
                             question=q, topic=state.topic, review=witness)
        return GuidedDecision(state=renewed, reply=render_question(q), reason='pending')

    def _commit_guided(self, db, source, previous, decision, *, token=None, now):
        state = decision.state
        proposal, q = state.snapshot.proposal, state.question
        reply = decision.reply
        if (decision.reason != 'read' and q is not None and q == previous.question
                and q.status == 'active' and now < q.expires_at
                and reply.text == render_question(q).text):
            # A new keyboard is a new authenticated offer, never an alias of an old notice.
            decision = self._resend_guided_question(state, self._stored_event(source), now)
            state = decision.state
            proposal, q = state.snapshot.proposal, state.question
            reply = decision.reply
        changed_question = q != previous.question
        if decision.reason == 'confirmed':
            if (decision.mutations == () or previous.review is None
                    or previous.question is None or previous.question.kind != 'review'
                    or previous.topic is not None or revalidate_proposal(proposal, state.snapshot) is not None):
                raise ValueError('Invalid final mutation authority')
            # The reducer and these guarded writes share BEGIN IMMEDIATE's current rows/reservations.
            for mutation in decision.mutations:
                if diaper_reference(mutation.description) and mutation.unit not in {'paquetes', 'envases'}:
                    raise ValueError('Explicit package unit required')
                if mutation.kind == 'add':
                    db.execute('INSERT INTO list_lines VALUES (?,?,?,?,1,?)',
                        (str(uuid4()), resolve_product(mutation.description), mutation.description,
                         mutation.quantity, source['update_id']))
                else:
                    target = mutation.target
                    result = db.execute('UPDATE list_lines SET description=?,product_id=?,quantity=?,revision=revision+1 '
                        'WHERE id=? AND revision=? AND NOT EXISTS (SELECT 1 FROM reservations WHERE line_id=?)',
                        (mutation.description, resolve_product(mutation.description), mutation.quantity,
                         target.id, target.revision, target.id))
                    if result.rowcount != 1:
                        raise ValueError('Mutation requires one current unreserved row')
            proposal = None
            reply = Reply(text=f'Lote guardado: {len(decision.mutations)} cambios confirmados. La lista se ha actualizado.')
        elif decision.mutations:
            raise ValueError('Intermediate mutations forbidden')
        buttons = None
        if (decision.reason != 'read' and changed_question and q is not None and q.status == 'active'
                and reply.text == render_question(q).text):
            buttons = tuple(InlineButton(label=c.label, token='q:' + secrets.token_urlsafe(16)) for c in q.choices)
            reply = reply.model_copy(update={'keyboard': InlineKeyboard(rows=tuple((b,) for b in buttons))})
        self._complete_reply(db, source, reply)
        notice_id = db.execute('SELECT id FROM outbox WHERE update_id=?', (source['update_id'],)).fetchone()[0]
        if previous.question and (changed_question or proposal is None):
            old = previous.question.model_copy(update={'status': 'consumed' if token is not None else 'revoked'})
            db.execute('UPDATE guided_questions SET question_json=? WHERE id=? AND version=?',
                       (old.model_dump_json(), str(old.id), old.version))
        if q is not None and changed_question and proposal is not None and q.status == 'active':
            if buttons is None:
                raise ValueError('New question requires its full notice')
            db.execute('INSERT INTO guided_questions VALUES (?,?,?,?,?,?,?)',
                (str(q.id), q.version, q.owner_id, q.chat_id, q.source_update_id, notice_id, q.model_dump_json()))
            for i, button in enumerate(buttons):
                db.execute('INSERT INTO guided_tokens VALUES (?,?,?,?,?,?,?,NULL,NULL)',
                    (button.token, q.owner_id, q.chat_id, str(q.id), q.version, i, notice_id))
            if isinstance(proposal, GuidedProposal) and proposal.review:
                witness = proposal.review.model_copy(update={'notice_id': notice_id})
                proposal = proposal.model_copy(update={'review': witness})
        if token is not None and (changed_question or proposal is None):
            db.execute('UPDATE guided_tokens SET consumed_update_id=?,result_json=? WHERE token=? '
                       'AND consumed_update_id IS NULL', (source['update_id'], reply.model_dump_json(), token['token']))
        key = (source['user_id'], source['chat_id'])
        db.execute('DELETE FROM guided_topics WHERE user_id=? AND chat_id=?', key)
        if state.topic is not None and proposal is not None:
            t = state.topic
            db.execute('INSERT INTO guided_topics VALUES (?,?,?,?,?,?)',
                (str(t.id), t.version, *key, t.source_update_id, t.model_dump_json()))
        self._write_agent_proposal(db, source, proposal)
        if proposal is not None:
            db.execute('DELETE FROM dialogue_state WHERE user_id=? AND chat_id=?', key)
            db.execute('UPDATE conversation_routes SET command_update_id=NULL WHERE user_id=? AND chat_id=?', key)
        return reply

    def _guided_delivery(self, db, notice_id, chat_id, message_id, digest):
        row = db.execute('SELECT * FROM guided_questions WHERE notice_id=?', (notice_id,)).fetchone()
        if row is None:
            return
        q = self._guided_question_row(db, row)
        now = datetime.now(UTC)
        if q.kind != 'review' or q.status != 'active' or now >= q.expires_at or digest != _digest(q.text):
            return
        source = self._agent_source(db, q.source_update_id)
        state = self._guided_state(db, source, now=now)
        if (state.question != q or state.review is None or state.review.notice_id != notice_id
                or state.review.summary_digest != digest or state.snapshot.proposal.expires_at <= now):
            return
        witness = state.review.model_copy(update={'delivered_message_id': message_id})
        self._write_agent_proposal(db, source, state.snapshot.proposal.model_copy(update={'review': witness}))

    def guided_history(self, user_id: int, chat_id: int) -> tuple[dict, ...]:
        with self._connection() as db:
            db.execute('BEGIN')
            rows = db.execute('SELECT * FROM inbox WHERE user_id=? AND chat_id=? AND completed=1 '
                              'ORDER BY update_id DESC LIMIT 3', (user_id, chat_id)).fetchall()
            history = []
            for source in reversed(rows):
                event = self._stored_event(source)
                reply = Reply.model_validate_json(source['reply_json'])
                if not self._committed_reply_matches(db, source, reply):
                    raise ValueError('History lacks committed reply')
                if isinstance(event, IncomingCallback):
                    token = db.execute('SELECT * FROM guided_tokens WHERE token=?', (event.data,)).fetchone()
                    q = self._guided_token_row(db, token)
                    if ((q.owner_id, q.chat_id) != (user_id, chat_id)
                            or token['consumed_update_id'] is None
                            or not self._guided_receipt(db, token, event, q)
                            or reply != Reply.model_validate_json(token['result_json'])):
                        raise ValueError('History callback lacks authenticated selection')
                    text = q.choices[token['choice_index']].label
                else:
                    text = event.text
                history.extend(({'role': 'user', 'content': text}, {'role': 'assistant', 'content': reply.text}))
            return tuple(history)

    def revoke_guided(self, user_id: int, *, now: datetime) -> None:
        utc(now)
        if type(user_id) is not int or user_id <= 0:
            raise ValueError('Invalid owner')
        with self._connection(write=True) as db:
            self._revoke_guided(db, user_id)

    @staticmethod
    def _revoke_guided(db, user_id):
        for row in db.execute('SELECT * FROM guided_questions WHERE user_id=?', (user_id,)).fetchall():
            q = GuidedQuestion.model_validate_json(row['question_json'])
            q = q.model_copy(update={'status': 'revoked'})
            db.execute('UPDATE guided_questions SET question_json=? WHERE id=? AND version=?',
                       (q.model_dump_json(), str(q.id), q.version))
        db.execute('DELETE FROM guided_topics WHERE user_id=?', (user_id,))
        db.execute("DELETE FROM agent_proposals WHERE user_id=? AND json_extract(proposal_json,'$.schema_version')=2",
                   (user_id,))
