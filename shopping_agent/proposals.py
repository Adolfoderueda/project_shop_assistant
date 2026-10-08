"""Pure batch reducer: model suggestions edit drafts, never saved list rows."""

import re
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from dialogue import (
    DIALOGUE_TTL,
    MAX_QUANTITY,
    DialogueAnswer,
    DialogueMutation,
    LineRef,
    canonical_name,
)
from domain import IncomingMessage, ListLine, utc
from interpreter import diaper_reference
from shopping_agent.contracts import (
    AgentProposal,
    AgentSnapshot,
    CompleteProposal,
    ItemPatch,
    ProposalDecision,
    ProposalItem,
    ProposeAdds,
    ProposeChange,
)
from shopping_agent.replies import MAX_REPLY, proposal_text


def _copy(model, **changes):
    # model_copy does not validate. Every reducer transition preserves strict invariants.
    return type(model).model_validate({**model.__dict__, **changes})


def _ref(line: ListLine) -> LineRef:
    return LineRef(id=line.id, revision=line.revision)


def _matches(description, lines, *, broad=False, exclude=None):
    key = canonical_name(description)
    return tuple(_ref(line) for line in lines if line.id != exclude and (
        canonical_name(line.description) == key or
        broad and set(key.split()).issubset(canonical_name(line.description).split())))


def _owned(message, snapshot):
    return (message.user_id, message.chat_id) == (snapshot.user_id, snapshot.chat_id)


def _live(message, snapshot, now):
    proposal = snapshot.proposal
    if not _owned(message, snapshot):
        return ProposalDecision(reason="invalid")
    if proposal is None:
        return ProposalDecision(reason="no_pending")
    if (proposal.user_id, proposal.chat_id) != (message.user_id, message.chat_id):
        return ProposalDecision(reason="invalid")
    if now >= proposal.expires_at:
        return ProposalDecision(reason="expired")
    return None


def _output_name(item, rows):
    if item.kind == "replace":
        return item.replacement
    if item.target and (item.kind != "add" or item.duplicate_decision == "set_total"):
        return rows[item.target.id].description
    return item.description


def _internal(items, rows):
    names = {item.position: canonical_name(_output_name(item, rows)) for item in items}
    return tuple(_copy(item, internal_conflicts=tuple(
        position for position, name in names.items()
        if position != item.position and name == names[item.position])) for item in items)


def _selected(item, target, rows):
    line = rows[target.id]
    changes = {"target": target}
    if item.kind == "increment":
        base = line.quantity
        delta = item.additional_quantity
        total = base + delta if base is not None and delta is not None else None
        changes.update(base_quantity=base, quantity=total if total is None or total <= MAX_QUANTITY else None)
    return _copy(item, **changes)


def _revalidate(proposal, snapshot):
    rows = {line.id: line for line in snapshot.lines}
    for item in proposal.items:
        refs = (*item.candidates, *item.conflict_signatures, *((item.target,) if item.target else ()))
        if any(ref.id not in rows or _ref(rows[ref.id]) != ref for ref in refs):
            return "stale"
        if item.target is not None and item.target not in item.candidates:
            return "invalid"
        matches = _matches(item.description, snapshot.lines, broad=item.kind != "add")
        if item.candidates != matches:
            return "stale"
        conflicts = (_matches(item.replacement, snapshot.lines,
                              exclude=item.target.id if item.target else None)
                     if item.kind == "replace" else matches)
        if item.conflict_signatures != conflicts:
            return "stale"
        if item.kind == "increment" and item.target and rows[item.target.id].quantity != item.base_quantity:
            return "stale"
        if item.target and item.target.id in {r.line_id for r in snapshot.reservations}:
            return "reserved"
    recomputed = _internal(proposal.items, rows)
    if any(new.internal_conflicts != old.internal_conflicts
           for new, old in zip(recomputed, proposal.items, strict=True)):
        return "stale"
    return None


def _status(proposal, snapshot):
    reason = _revalidate(proposal, snapshot)
    if reason:
        return reason
    targets = [item.target.id for item in proposal.items if item.target and (
        item.kind != "add" or item.duplicate_decision == "set_total")]
    if len(set(targets)) != len(targets):
        return "invalid"
    rows = {line.id: line for line in snapshot.lines}
    for item in proposal.items:
        if (item.kind == "increment" and item.base_quantity is not None
                and item.additional_quantity is not None
                and item.base_quantity + item.additional_quantity > MAX_QUANTITY):
            return "quantity_range"
        if diaper_reference(_output_name(item, rows)) and item.unit not in {"envases", "paquetes"}:
            return "diaper_unit"
        if item.kind == "replace" and item.duplicate_decision == "set_total":
            return "invalid"
    if proposal.condition is not None:
        return "condition"
    if not all(item.complete for item in proposal.items):
        return "pending"
    return "reviewed"


def _finish(proposal, message, snapshot):
    reason = _status(proposal, snapshot)
    # A full visible summary is a prerequisite, never a truncated preview.
    if len(proposal_text(proposal, snapshot, review=True)) > MAX_REPLY:
        reason = "invalid"
    if reason == "reviewed":
        proposal = _copy(proposal, reviewed_revision=proposal.revision,
                         reviewed_update_id=message.update_id)
    return ProposalDecision(proposal=proposal, reason=reason)


def prepare_proposal(message: IncomingMessage, args: ProposeAdds | ProposeChange,
                     snapshot: AgentSnapshot, *, now: datetime) -> ProposalDecision:
    utc(now)
    if not _owned(message, snapshot):
        return ProposalDecision(reason="invalid")
    rows = {line.id: line for line in snapshot.lines}
    items = []
    if isinstance(args, ProposeAdds):
        for position, source in enumerate(args.items, 1):
            matches = _matches(source.description, snapshot.lines)
            items.append(ProposalItem(position=position, kind="add", description=source.description,
                quantity=source.quantity, unit=source.unit, candidates=matches, conflict_signatures=matches))
    else:
        matches = _matches(args.query, snapshot.lines, broad=True)
        item = ProposalItem(position=1, kind=args.kind, description=args.query,
            quantity=args.quantity if args.kind != "increment" else None,
            additional_quantity=args.quantity if args.kind == "increment" else None,
            unit=args.unit, replacement=args.replacement, candidates=matches)
        if len(matches) == 1:
            item = _selected(item, matches[0], rows)
        conflicts = (_matches(args.replacement, snapshot.lines, exclude=item.target.id if item.target else None)
                     if args.kind == "replace" else matches)
        items.append(_copy(item, conflict_signatures=conflicts))
    proposal = AgentProposal(
        id=uuid5(NAMESPACE_URL, f"shopping-agent:{message.user_id}:{message.chat_id}:{message.update_id}"),
        revision=1, user_id=message.user_id, chat_id=message.chat_id,
        source_update_id=message.update_id, original_text=message.text,
        items=_internal(tuple(items), rows), condition=args.condition,
        updated_at=now, expires_at=now + DIALOGUE_TTL)
    return _finish(proposal, message, snapshot)


def _patch(item, patch, snapshot):
    rows = {line.id: line for line in snapshot.lines}
    if patch.candidate_index is not None:
        if patch.candidate_index > len(item.candidates):
            return None
        item = _selected(item, item.candidates[patch.candidate_index - 1], rows)
    changes = {}
    if patch.unit is not None:
        changes["unit"] = patch.unit
    if patch.duplicate_decision is not None:
        changes["duplicate_decision"] = patch.duplicate_decision
        if item.kind == "increment":
            if item.target is None and not item.candidates and patch.duplicate_decision == "separate":
                changes.update(kind="add", quantity=patch.quantity or item.additional_quantity,
                               base_quantity=None, additional_quantity=None)
            elif item.target and item.base_quantity is None and patch.duplicate_decision == "set_total":
                # The supplied quantity is explicitly a total, not the old delta.
                changes.update(kind="set_quantity", quantity=patch.quantity,
                               base_quantity=None, additional_quantity=None)
            else:
                return None
        elif item.kind == "add" and patch.duplicate_decision == "set_total":
            if item.target is None and len(item.candidates) == 1:
                changes["target"] = item.candidates[0]
            elif item.target is None and not item.candidates:
                return None
        elif item.kind not in {"add", "replace"}:
            return None
    item = _copy(item, **changes)
    if patch.quantity is not None:
        if item.kind == "increment":
            total = item.base_quantity + patch.quantity if item.base_quantity is not None else None
            item = _copy(item, additional_quantity=patch.quantity,
                         quantity=total if total is None or total <= MAX_QUANTITY else None)
        else:
            item = _copy(item, quantity=patch.quantity)
    if item.kind == "replace":
        item = _copy(item, conflict_signatures=_matches(item.replacement, snapshot.lines,
                     exclude=item.target.id if item.target else None))
    return item


def complete_proposal(message: IncomingMessage, args: CompleteProposal, snapshot: AgentSnapshot,
                      *, now: datetime) -> ProposalDecision:
    utc(now)
    invalid = _live(message, snapshot, now)
    if invalid:
        return invalid
    proposal = snapshot.proposal
    reason = _revalidate(proposal, snapshot)
    if reason:
        return ProposalDecision(reason=reason)
    items = {item.position: item for item in proposal.items}
    for patch in args.patches:
        if patch.position not in items:
            return ProposalDecision(proposal=proposal, reason="invalid")
        updated = _patch(items[patch.position], patch, snapshot)
        if updated is None:
            return ProposalDecision(proposal=proposal, reason="invalid")
        items[patch.position] = updated
    if not args.patches and not args.remove_condition:
        return ProposalDecision(proposal=proposal, reason="pending")
    rows = {line.id: line for line in snapshot.lines}
    proposal = _copy(proposal, items=_internal(tuple(items.values()), rows),
        condition=None if args.remove_condition else proposal.condition,
        revision=proposal.revision + 1, reviewed_revision=None, reviewed_update_id=None,
        updated_at=now, expires_at=now + DIALOGUE_TTL)
    return _finish(proposal, message, snapshot)


def _question(proposal):
    unresolved = [item for item in proposal.items if not item.complete or (
        diaper_reference(item.replacement or item.description) and item.unit not in {"envases", "paquetes"})]
    if len(unresolved) != 1:
        return None, None
    item = unresolved[0]
    if item.target is None and item.candidates and (
            item.kind != "add" or item.duplicate_decision == "set_total"):
        return item, "select"
    if item.kind == "increment" and not item.candidates:
        return item, "missing"
    if item.kind == "increment" and item.target and item.base_quantity is None:
        return item, "unknown"
    if item.kind == "add" and (item.candidates or item.internal_conflicts) and item.duplicate_decision is None:
        return item, "duplicate"
    if item.kind == "replace" and (item.conflict_signatures or item.internal_conflicts) and item.duplicate_decision is None:
        return item, "replacement_duplicate"
    if item.quantity is None or (
            diaper_reference(item.replacement or item.description) and item.unit not in {"envases", "paquetes"}):
        return item, "quantity"
    return None, None


def parse_control(text: str, proposal: AgentProposal | None, *, now: datetime) -> DialogueAnswer | None:
    utc(now)
    if proposal is None or now >= proposal.expires_at:
        return None
    clean = canonical_name(text)
    if clean in {"si", "confirmo", "confirmar"}:
        return DialogueAnswer(kind="confirm")
    if clean == "no":
        return DialogueAnswer(kind="reject")
    if clean == "cancelar":
        return DialogueAnswer(kind="cancel")
    item, question = _question(proposal)
    if question == "select" and re.fullmatch(r"[1-9][0-9]{0,18}", clean):
        index = int(clean)
        if index <= len(item.candidates):
            return DialogueAnswer(kind="select", selection=index)
    if question in {"missing", "duplicate", "replacement_duplicate"} and clean == "anadir otra linea":
        return DialogueAnswer(kind="add")
    if question in {"unknown", "duplicate"} and clean == "cambiar cantidad":
        return DialogueAnswer(kind="change_quantity")
    if question == "quantity":
        match = re.fullmatch(r"([1-9][0-9]{0,18})(?: (envases|paquetes|botes|sacos))?", clean)
        if match and int(match[1]) <= MAX_QUANTITY:
            return DialogueAnswer(kind="quantity", quantity=int(match[1]), unit=match[2])
    return None


def answer_proposal(message: IncomingMessage, snapshot: AgentSnapshot, *, now: datetime) -> ProposalDecision:
    utc(now)
    invalid = _live(message, snapshot, now)
    if invalid:
        if invalid.reason == "expired" and canonical_name(message.text) not in {
                "si", "confirmo", "confirmar", "no", "cancelar"}:
            # Unrelated/social/read turns do not discard even an expired draft.
            return ProposalDecision(proposal=snapshot.proposal, reason="expired")
        return invalid
    proposal = snapshot.proposal
    answer = parse_control(message.text, proposal, now=now)
    if answer is None:
        # Social/read turns never edit state or renew its expiry/review.
        return ProposalDecision(proposal=proposal, reason="pending")
    if answer.kind in {"cancel", "reject"}:
        return ProposalDecision(reason="cancelled" if answer.kind == "cancel" else "rejected")
    reason = _status(proposal, snapshot)
    if reason in {"stale", "reserved"}:
        return ProposalDecision(reason=reason)
    if answer.kind != "confirm":
        item, _ = _question(proposal)
        patch = ItemPatch(position=item.position, quantity=answer.quantity, unit=answer.unit,
                          candidate_index=answer.selection,
                          duplicate_decision="separate" if answer.kind == "add" else
                          "set_total" if answer.kind == "change_quantity" else None)
        return complete_proposal(message, CompleteProposal(patches=(patch,)), snapshot, now=now)
    if (reason != "reviewed" or proposal.reviewed_revision != proposal.revision
            or proposal.reviewed_update_id is None or message.update_id <= proposal.reviewed_update_id
            or len(proposal_text(proposal, snapshot, review=True)) > MAX_REPLY):
        return ProposalDecision(proposal=proposal, reason=reason if reason != "reviewed" else "pending")
    rows = {line.id: line for line in snapshot.lines}
    mutations = []
    for item in proposal.items:
        kind = "set_quantity" if item.kind == "add" and item.duplicate_decision == "set_total" else item.kind
        mutations.append(DialogueMutation(kind=kind,
            description=_output_name(item, rows), quantity=item.quantity,
            target=item.target if kind != "add" else None, unit=item.unit or "envases",
            expected_base=item.base_quantity if kind == "increment" else None,
            additional_quantity=item.additional_quantity if kind == "increment" else None))
    return ProposalDecision(proposal=proposal, reason="confirmed", mutations=tuple(mutations))
