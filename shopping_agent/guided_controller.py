"""Pure application-owned questions and transitions; no SQL, transport or model calls."""

from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from dialogue import canonical_name
from domain import IncomingEvent, IncomingMessage, Reply, utc
from shopping_agent.contracts import (
    Contribution,
    GuidedProposal,
    ItemPatch,
    ProposalItem,
    ReviewWitness,
)
from shopping_agent.guided_contracts import (
    ChangeCandidate,
    Choice,
    ControlCandidate,
    GuidedAnswer,
    GuidedDecision,
    GuidedQuestion,
    GuidedState,
    PendingTopic,
    QuantityCandidate,
    ReadCandidate,
    ResolvedChoice,
    ScopeCandidate,
    TopicCandidate,
)
from shopping_agent.guided_replies import render_question, render_review, review_fits
from shopping_agent.proposals import (
    matching_lines,
    missing_unit,
    patch_item,
    proposal_mutations,
    proposal_status,
    recompute_conflicts,
    revalidate_proposal,
)
from shopping_agent.replies import REASONS, TOO_LONG


def _copy(model, **changes):
    return type(model).model_validate({**model.__dict__, **changes})


def _state(state, *, proposal, question=None, topic=None):
    return GuidedState(snapshot=_copy(state.snapshot, proposal=proposal), question=question,
                       topic=topic, review=proposal.review if isinstance(proposal, GuidedProposal) else None)


def _question(state, event, now, kind, positions, text, choices, *, candidate=None):
    proposal = state.snapshot.proposal
    version = state.question.version + 1 if state.question else 1
    identity = (f'guided:{event.user_id}:{event.chat_id}:{event.update_id}:'
                f'{proposal.id}:{proposal.revision}:{kind}:{version}')
    return GuidedQuestion(id=uuid5(NAMESPACE_URL, identity), version=version,
        owner_id=event.user_id, chat_id=event.chat_id, kind=kind,
        proposal_id=proposal.id, proposal_revision=proposal.revision, positions=positions,
        choices=choices, source_update_id=event.update_id, created_at=now,
        expires_at=proposal.expires_at, status='active', text=text, candidate=candidate)


def _successor(question, previous):
    """Bind both logical identity and version to the consumed predecessor."""
    version = previous.version + 1
    identity = (f'guided:{question.owner_id}:{question.chat_id}:{question.source_update_id}:'
                f'{question.proposal_id}:{question.proposal_revision}:{question.kind}:{version}')
    return _copy(question, version=version, id=uuid5(NAMESPACE_URL, identity))


def _names(state, positions):
    return ', '.join(item.description for item in state.snapshot.proposal.items if item.position in positions)


def _scope(state, event, now, positions, *, candidate=None):
    choices = tuple(Choice(kind='choose_scope', label=item.description, positions=(item.position,))
                    for item in state.snapshot.proposal.items if item.position in positions)
    if len(positions) > 1:
        choices += (Choice(kind='choose_scope', label='Todos', positions=positions),)
    return _question(state, event, now, 'scope', positions,
                     '¿De cuál o cuáles? ' + _names(state, positions), choices, candidate=candidate)


def _quantity_question(state, event, now, positions, *, shared=False):
    return _question(state, event, now, 'quantity_shared' if shared else 'quantity_single',
        positions, '¿Qué cantidad quieres de ' + _names(state, positions) + '?',
        (Choice(kind='write_answer', label='Escribir respuesta'),))


def next_question(state: GuidedState, event: IncomingEvent, *, now: datetime) -> GuidedQuestion | None:
    utc(now)
    proposal = state.snapshot.proposal
    if proposal is None or now >= proposal.expires_at:
        return None
    if (event.user_id, event.chat_id) != (state.snapshot.user_id, state.snapshot.chat_id):
        return None
    if state.question and state.question.status == 'active':
        return state.question if now < state.question.expires_at else None
    if state.topic:
        return _question(state, event, now, 'topic', (),
            f'Tema adicional: {state.topic.original_text}. ¿Añadir al borrador o mantener sin añadir?',
            (Choice(kind='append_topic', label='Añadir al borrador'),
             Choice(kind='keep_topic', label='Mantener sin añadir')))
    if proposal.condition:
        return _question(state, event, now, 'condition', (),
            f'Condición pendiente: {proposal.condition}. No está comprobada.',
            (Choice(kind='remove_condition', label='Retirar condición'),
             Choice(kind='write_answer', label='Escribir respuesta')))
    reserved = {reservation.line_id for reservation in state.snapshot.reservations}
    rows = {line.id: line for line in state.snapshot.lines}
    for item in proposal.items:
        positions = (item.position,)
        if item.target is None and item.candidates and (
                item.kind != 'add' or item.duplicate_decision == 'set_total'):
            choices = tuple(Choice(kind='choose_line', positions=positions, candidate_index=index,
                label=f'{rows[ref.id].description} [{ref.id}, revisión {ref.revision}]')
                for index, ref in enumerate(item.candidates, 1)
                if ref.id in rows and ref.id not in reserved and rows[ref.id].revision == ref.revision)
            if choices:
                return _question(state, event, now, 'source_line', positions,
                    f'Elige la fila de origen para {item.description}.', choices)
            return None
        unknown = item.kind == 'increment' and (not item.candidates or (
            item.target is not None and item.base_quantity is None))
        duplicate = item.duplicate_decision is None and (item.internal_conflicts or (
            item.kind == 'add' and item.candidates or item.kind == 'replace' and item.conflict_signatures))
        if unknown or duplicate:
            choices = ()
            if not (item.kind == 'increment' and item.target is not None):
                choices += (Choice(kind='separate', label='Añadir otra línea', positions=positions),)
            if item.kind != 'replace' and any(ref.id not in reserved for ref in item.candidates):
                choices += (Choice(kind='set_total', label='Cambiar cantidad total', positions=positions),)
            if choices:
                return _question(state, event, now, 'duplicate', positions,
                    (f'Base desconocida de {item.description}; no es cero. Elige un total explícito.'
                     if unknown and item.target else
                     f'Decide el duplicado de {item.description}; no se suman líneas automáticamente.'), choices)
        if missing_unit(item):
            return _question(state, event, now, 'unit', positions,
                f'Indica la unidad de compra de {item.replacement or item.description}.',
                tuple(Choice(kind='choose_unit', label=unit, unit=unit, positions=positions)
                      for unit in ('paquetes', 'envases')))
    missing = tuple(item.position for item in proposal.items if item.quantity is None)
    if len(missing) == 1:
        return _quantity_question(state, event, now, missing)
    if missing:
        return _question(state, event, now, 'scope', missing,
            '¿Qué cantidad quieres de ' + _names(state, missing) + '?',
            (Choice(kind='one_each', label='Uno de cada', positions=missing),
             Choice(kind='same_quantity', label='Misma cantidad', positions=missing),
             Choice(kind='different_quantities', label='Cantidades diferentes', positions=missing),
             Choice(kind='write_answer', label='Escribir respuesta')))
    if proposal_status(proposal, state.snapshot) == 'reviewed' and review_fits(render_review(state)):
        return _question(state, event, now, 'review', (), render_review(state).text,
            (Choice(kind='confirm', label='Confirmar'), Choice(kind='correct', label='Corregir'),
             Choice(kind='cancel', label='Cancelar')))
    return None


def resolve_text_choice(message: IncomingMessage, question: GuidedQuestion) -> ResolvedChoice | None:
    if question.status != 'active' or (message.user_id, message.chat_id) != (question.owner_id, question.chat_id):
        return None
    clean = canonical_name(message.text)
    # Offered data wins over control words (a product may literally be called «no»).
    matches = [index for index, choice in enumerate(question.choices)
               if clean == canonical_name(choice.label)]
    if (not matches and question.kind not in {'quantity_single', 'quantity_shared', 'review'}
            and clean.isascii() and clean.isdecimal() and len(clean) <= 20):
        index = int(clean) - 1
        if 0 <= index < len(question.choices):
            matches = [index]
    control = None
    if not matches:
        if question.kind == 'review':
            control = {'si': 'confirm', 'confirmo': 'confirm', 'no': 'cancel'}.get(clean)
        elif question.kind == 'topic':
            control = {'si': 'append_topic', 'no': 'keep_topic'}.get(clean)
        if clean == 'cancelar':
            control = 'cancel'
        matches = [index for index, choice in enumerate(question.choices) if choice.kind == control]
    if len(matches) != 1:
        return None
    return ResolvedChoice(question_id=question.id, question_version=question.version,
                          choice_index=matches[0], source_update_id=message.update_id)


def _decision(state, reason='pending', *, text=None, mutations=()):
    if text is None:
        if state.question and state.question.kind == 'review':
            reply = render_review(state)
        elif state.question:
            reply = render_question(state.question)
        else:
            reply = Reply(text=REASONS.get(reason, 'Pendiente, sin guardar.'))
    else:
        reply = Reply(text=text)
    return GuidedDecision(state=state, reply=reply, reason=reason, mutations=mutations)


def _clear_review(state):
    proposal = state.snapshot.proposal
    changes = {'reviewed_revision': None, 'reviewed_update_id': None}
    if isinstance(proposal, GuidedProposal):
        changes['review'] = None
    proposal = _copy(proposal, **changes)
    return _state(state, proposal=proposal, topic=state.topic)


def _record_decision(state, event, positions=()):
    proposal = state.snapshot.proposal
    contributions = proposal.contributions if isinstance(proposal, GuidedProposal) else (
        Contribution(update_id=proposal.source_update_id,
                     positions=tuple(item.position for item in proposal.items), kind='create'),)
    proposal = GuidedProposal.model_validate({**proposal.__dict__, 'schema_version': 2,
        'contributions': (*contributions, Contribution(update_id=event.update_id,
                                                       positions=positions, kind='decision'))})
    return _state(state, proposal=proposal, question=state.question, topic=state.topic)


def _advance(state, event, now, *, old_question=None, individual=False):
    # Keep only the old version to determine the successor; it is never reused.
    version_state = state
    if old_question and old_question.proposal_revision == state.snapshot.proposal.revision:
        version_state = _copy(state, question=_copy(old_question, status='consumed'))
    question = next_question(version_state, event, now=now)
    if individual and question and question.kind == 'scope':
        question = _quantity_question(version_state, event, now, (question.positions[0],))
    if question and old_question:
        question = _successor(question, old_question)
    proposal = state.snapshot.proposal
    status = proposal_status(proposal, state.snapshot)
    if status in {'stale', 'reserved', 'invalid', 'quantity_range'}:
        return _decision(state, status, text=REASONS[status])
    if question and question.kind == 'review' and not isinstance(proposal, GuidedProposal):
        state = _record_decision(state, event)
        proposal = state.snapshot.proposal
    if question and question.kind == 'review' and isinstance(proposal, GuidedProposal):
        reply = render_review(state)
        witness = ReviewWitness(proposal_id=proposal.id, revision=proposal.revision,
            question_id=question.id, summary_digest=sha256(reply.text.encode('utf-8')).hexdigest(),
            source_update_id=event.update_id, notice_id=str(question.id), delivered_message_id=None)
        proposal = _copy(proposal, review=witness)
    result = _state(state, proposal=proposal, question=question, topic=state.topic)
    if question is None and not review_fits(render_review(result)):
        return _decision(result, 'too_long', text=TOO_LONG)
    return _decision(result, 'reviewed' if question and question.kind == 'review' else 'pending')


def _edit(state, event, now, patches=(), *, remove_condition=False, source=None, individual=False):
    proposal = state.snapshot.proposal
    reason = revalidate_proposal(proposal, state.snapshot)
    if reason:
        return _decision(state, reason, text=REASONS[reason])
    items = {item.position: item for item in proposal.items}
    for patch in patches:
        if patch.position not in items:
            return _decision(state, 'invalid')
        changed = patch_item(items[patch.position], patch, state.snapshot)
        if changed is None:
            return _decision(state, 'invalid')
        items[patch.position] = changed
    contributions = proposal.contributions if isinstance(proposal, GuidedProposal) else (
        Contribution(update_id=proposal.source_update_id, positions=tuple(items), kind='create'),)
    positions = tuple(p.position for p in patches)
    contributions += (Contribution(update_id=source if source is not None else event.update_id,
                                    positions=positions, kind='edit' if patches else 'decision'),)
    if source is not None and source != event.update_id:
        contributions += (Contribution(update_id=event.update_id, positions=positions, kind='decision'),)
    fields = {**proposal.__dict__, 'schema_version': 2, 'contributions': contributions, 'review': None,
              'items': recompute_conflicts(tuple(items.values()), {line.id: line for line in state.snapshot.lines}),
              'condition': None if remove_condition else proposal.condition,
              'revision': proposal.revision + 1, 'reviewed_revision': None, 'reviewed_update_id': None,
              'updated_at': now}
    proposal = GuidedProposal.model_validate(fields)
    reason = revalidate_proposal(proposal, state.snapshot)
    if reason:
        return _decision(state, reason, text=REASONS[reason])
    topic = _copy(state.topic, proposal_revision=proposal.revision) if state.topic else None
    edited = _state(state, proposal=proposal, topic=topic)
    return _advance(edited, event, now, old_question=state.question, individual=individual)


def append_topic(state: GuidedState, event: IncomingEvent, *, now: datetime) -> GuidedDecision:
    utc(now)
    if not _live(state, event, now):
        return _decision(state, 'invalid')
    topic = state.topic
    proposal = state.snapshot.proposal
    if topic is None or now >= topic.expires_at:
        return _decision(state, 'invalid')
    if len(proposal.items) + len(topic.items) > 20 or max(i.position for i in proposal.items) + len(topic.items) > 20:
        return _decision(state, 'too_many', text='El borrador y el tema superan 20 elementos. Divide la petición; ambos siguen pendientes, sin guardar.')
    # A single condition field cannot represent two independent conditions safely.
    if proposal.condition and topic.condition and proposal.condition != topic.condition:
        return _decision(state, 'condition', text='Resuelve las condiciones de ambos temas antes de añadir; ambos siguen pendientes.')
    reason = revalidate_proposal(proposal, state.snapshot)
    if reason:
        return _decision(state, reason, text=REASONS[reason])
    first = max(item.position for item in proposal.items) + 1
    added = tuple(ProposalItem(position=position, kind='add', description=item.description,
        quantity=item.quantity, unit=item.unit, candidates=matching_lines(item.description, state.snapshot.lines),
        conflict_signatures=matching_lines(item.description, state.snapshot.lines))
        for position, item in enumerate(topic.items, first))
    contributions = proposal.contributions if isinstance(proposal, GuidedProposal) else (
        Contribution(update_id=proposal.source_update_id, positions=tuple(i.position for i in proposal.items), kind='create'),)
    positions = tuple(item.position for item in added)
    contributions += (Contribution(update_id=topic.source_update_id, positions=positions, kind='append'),
                      Contribution(update_id=event.update_id, positions=positions, kind='decision'))
    proposal = GuidedProposal.model_validate({**proposal.__dict__, 'schema_version': 2,
        'contributions': contributions, 'review': None, 'reviewed_revision': None, 'reviewed_update_id': None,
        'revision': proposal.revision + 1, 'updated_at': now,
        'condition': proposal.condition or topic.condition,
        'items': recompute_conflicts((*proposal.items, *added), {line.id: line for line in state.snapshot.lines})})
    return _advance(_state(state, proposal=proposal), event, now, old_question=state.question)


def _live(state, event, now):
    proposal = state.snapshot.proposal
    return (proposal is not None and now < proposal.expires_at
            and proposal.source_update_id >= 0 and event.update_id >= 0
            and (event.user_id, event.chat_id) == (state.snapshot.user_id, state.snapshot.chat_id)
            and (state.question is None or state.question.status == 'active' and now < state.question.expires_at))


def reduce_guided(state: GuidedState, event: IncomingEvent,
                  answer: GuidedAnswer | ResolvedChoice | None, *, now: datetime) -> GuidedDecision:
    utc(now)
    if not _live(state, event, now):
        expired = (state.snapshot.proposal and now >= state.snapshot.proposal.expires_at
                   or state.question and now >= state.question.expires_at)
        reason = 'expired' if expired else 'invalid'
        return _decision(state, reason, text=REASONS[reason])
    question = state.question
    if not isinstance(event, IncomingMessage) and not isinstance(answer, ResolvedChoice):
        return _decision(state, 'invalid')
    if isinstance(answer, ReadCandidate):
        return _decision(state, 'read')
    if isinstance(event, IncomingMessage) and (answer is None or isinstance(answer, ControlCandidate)):
        if question:
            resolved = resolve_text_choice(event, question)
            if resolved is not None:
                answer = resolved
        if not isinstance(answer, ResolvedChoice) and canonical_name(event.text) == 'cancelar':
            answer = ControlCandidate(kind='cancel')
    if isinstance(answer, ControlCandidate) and answer.kind == 'cancel':
        if isinstance(event, IncomingMessage) and canonical_name(event.text) == 'cancelar':
            return _decision(_state(state, proposal=None), 'cancelled')
        return _decision(state)
    if isinstance(answer, ResolvedChoice):
        if (question is None or answer.question_id != question.id
                or answer.question_version != question.version or answer.source_update_id != event.update_id
                or answer.choice_index >= len(question.choices)):
            return _decision(state, 'invalid')
        choice = question.choices[answer.choice_index]
        positions = choice.positions or question.positions
        if choice.kind == 'cancel':
            return _decision(_state(state, proposal=None), 'cancelled')
        if choice.kind == 'confirm':
            proposal = state.snapshot.proposal
            witness = state.review
            reply = render_review(state)
            status = proposal_status(proposal, state.snapshot)
            if (question.kind != 'review' or state.topic or status != 'reviewed' or witness is None
                    or witness.delivered_message_id is None or event.update_id <= witness.source_update_id
                    or not review_fits(reply) or witness.summary_digest != sha256(reply.text.encode('utf-8')).hexdigest()):
                return _decision(state, 'pending', text='Necesitas revisar el resumen completo vigente y entregado antes de confirmar.')
            consumed = _copy(_record_decision(state, event), question=_copy(question, status='consumed'))
            return _decision(consumed, 'confirmed', text=REASONS['confirmed'],
                             mutations=proposal_mutations(proposal, state.snapshot))
        if choice.kind == 'append_topic':
            return append_topic(state, event, now=now)
        if choice.kind == 'keep_topic':
            selected = _record_decision(state, event)
            return _advance(_state(selected, proposal=selected.snapshot.proposal), event, now, old_question=question)
        if choice.kind == 'remove_condition':
            return _edit(state, event, now, remove_condition=True)
        if choice.kind == 'one_each':
            return _edit(state, event, now, tuple(ItemPatch(position=p, quantity=1) for p in positions))
        if choice.kind in {'same_quantity', 'different_quantities', 'choose_scope', 'correct'}:
            cleared = _clear_review(state)
            if choice.kind == 'correct':
                positions = tuple(item.position for item in state.snapshot.proposal.items)
                new = _scope(cleared, event, now, positions)
            elif choice.kind == 'choose_scope' and question.candidate:
                if question.candidate.source_update_id > question.source_update_id:
                    return _decision(state, 'invalid')
                values = {(patch.quantity, patch.unit) for patch in question.candidate.patches}
                if len(values) == 1:
                    quantity, unit = next(iter(values))
                    return _edit(state, event, now, tuple(ItemPatch(position=p, quantity=quantity, unit=unit)
                        for p in positions), source=question.candidate.source_update_id)
                new = _quantity_question(cleared, event, now, (positions[0],))
            else:
                shared = choice.kind == 'same_quantity' or choice.kind == 'choose_scope' and len(positions) > 1
                new = _quantity_question(cleared, event, now,
                    positions if shared else (positions[0],), shared=shared)
            cleared = _record_decision(cleared, event, positions)
            new = _successor(new, question)
            return _decision(_state(cleared, proposal=cleared.snapshot.proposal, question=new, topic=cleared.topic))
        if choice.kind in {'choose_unit', 'choose_line', 'separate', 'set_total'}:
            patch = ItemPatch(position=positions[0], unit=choice.unit, candidate_index=choice.candidate_index,
                             duplicate_decision=choice.kind if choice.kind in {'separate', 'set_total'} else None)
            return _edit(state, event, now, (patch,))
        if choice.kind == 'write_answer':
            cleared = _record_decision(_clear_review(state), event)
            new = _question(cleared, event, now, question.kind, question.positions,
                            question.text, question.choices, candidate=question.candidate)
            new = _successor(new, question)
            return _decision(_state(cleared, proposal=cleared.snapshot.proposal,
                                    question=new, topic=cleared.topic))
    if isinstance(answer, TopicCandidate):
        if answer.source_update_id != event.update_id or not isinstance(event, IncomingMessage):
            return _decision(state, 'invalid')
        if state.topic:
            return _decision(state, 'topic_pending', text='Ya hay un tema pendiente. Decide añadirlo o mantener sin añadir antes de otra petición.')
        cleared = _clear_review(state)
        proposal = cleared.snapshot.proposal
        topic = PendingTopic(id=uuid5(NAMESPACE_URL, f'guided-topic:{event.user_id}:{event.chat_id}:{event.update_id}'),
            version=1, source_update_id=event.update_id, original_text=event.text, items=answer.adds.items,
            condition=answer.adds.condition, proposal_id=proposal.id, proposal_revision=proposal.revision,
            expires_at=proposal.expires_at)
        return _advance(_state(cleared, proposal=proposal, topic=topic), event, now, old_question=question)
    if isinstance(answer, QuantityCandidate):
        if answer.source_update_id != event.update_id:
            return _decision(state, 'invalid')
        proposal = state.snapshot.proposal
        if any(p.position not in {i.position for i in proposal.items} or p.candidate_index is not None
               or p.duplicate_decision is not None for p in answer.patches):
            return _decision(state, 'invalid')
        if all(p.quantity is None and p.unit is None for p in answer.patches):
            return _decision(state)
        if question is None and len(proposal.items) == 1:
            return _edit(state, event, now, answer.patches)
        if question and question.kind in {'quantity_shared', 'quantity_single'}:
            if any(p.position not in question.positions for p in answer.patches):
                return _decision(state, 'invalid')
            patches = answer.patches
            if question.kind == 'quantity_shared':
                values = {(p.quantity, p.unit) for p in patches}
                if len(values) != 1:
                    return _decision(state, 'invalid')
                quantity, unit = next(iter(values))
                patches = tuple(ItemPatch(position=p, quantity=quantity, unit=unit) for p in question.positions)
            return _edit(state, event, now, patches, individual=question.kind == 'quantity_single')
        cleared = _clear_review(state)
        positions = tuple(item.position for item in proposal.items)
        new = _scope(cleared, event, now, positions, candidate=answer)
        if question:
            new = _successor(new, question)
        return _decision(_state(cleared, proposal=cleared.snapshot.proposal, question=new, topic=cleared.topic))
    if isinstance(answer, ChangeCandidate):
        return _decision(state, 'clarify', text='Conserva el borrador. Cancélalo explícitamente antes de iniciar otra operación.')
    if isinstance(answer, ScopeCandidate):
        if answer.source_update_id != event.update_id or not set(answer.positions) <= {
                item.position for item in state.snapshot.proposal.items}:
            return _decision(state, 'invalid')
        cleared = _clear_review(state)
        new = _scope(cleared, event, now, tuple(item.position for item in state.snapshot.proposal.items),
                     candidate=question.candidate if question else None)
        if question:
            new = _successor(new, question)
        return _decision(_state(cleared, proposal=cleared.snapshot.proposal, question=new, topic=cleared.topic))
    if question:
        return _decision(state)
    return _advance(state, event, now)
