"""Seven native tools: untrusted suggestions, application-owned authority."""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Annotated

from pydantic import Field

from domain import IncomingMessage, Model, Reply, utc
from shopping_agent.contracts import Description, ProposalDecision, ToolCall, ToolResult
from shopping_agent.proposals import _revalidate
from shopping_agent.replies import render_proposal
from shopping_agent.storage import OPERATION_CONTRACTS, EmptyArguments, _raw_json
from storage import Repository


class FicheArguments(Model):
    query: Annotated[Description, Field(min_length=1)]


READ_CONTRACTS = {
    'consultar_lista': EmptyArguments,
    'consultar_ficha': FicheArguments,
    'consultar_propuesta': EmptyArguments,
}
CONTRACTS = {**READ_CONTRACTS, **OPERATION_CONTRACTS}
DESCRIPTIONS = {
    'consultar_lista': 'Consultar todas las líneas guardadas y sus reservas.',
    'consultar_ficha': 'Consultar observaciones históricas, no disponibilidad actual.',
    'consultar_propuesta': 'Consultar el borrador y todos sus candidatos pendientes.',
    'proponer_altas': 'Proponer un lote de altas sin guardar líneas.',
    'proponer_cambio': 'Proponer incremento, cantidad total o sustitución sin guardar.',
    'completar_propuesta': 'Completar posiciones e índices ofrecidos del borrador.',
    'cancelar_propuesta': 'Descartar el borrador sin cambiar líneas guardadas.',
}


def tool_definitions() -> list[dict]:
    def exposed_schema(contract):
        schema = contract.model_json_schema()
        definitions = schema.pop('$defs', {})

        def inline(value):
            if isinstance(value, list):
                return [inline(item) for item in value]
            if not isinstance(value, dict):
                return value
            if '$ref' in value:
                # Our fixed, acyclic contracts only use local model definitions.
                reference = value['$ref']
                if not reference.startswith('#/$defs/'):
                    raise ValueError('Only local tool schema references are supported')
                return {**inline(definitions[reference.removeprefix('#/$defs/')]),
                        **inline({key: item for key, item in value.items() if key != '$ref'})}
            return {key: inline(item) for key, item in value.items()}

        return inline(schema)

    return [{'type': 'function', 'function': {
        'name': name, 'description': DESCRIPTIONS[name],
        'parameters': exposed_schema(contract),
    }} for name, contract in CONTRACTS.items()]


def _validate(call: ToolCall) -> ToolCall:
    if (type(call) is not ToolCall or type(call.name) is not str
            or call.name not in CONTRACTS or type(call.arguments) is not dict
            or not _raw_json(call.arguments)):
        raise ValueError('Unknown tool or invalid JSON arguments')
    encoded = json.dumps(call.arguments, allow_nan=False)
    CONTRACTS[call.name].model_validate_json(encoded)
    # Copy raw JSON, not contract defaults or Python-coerced arrays/quantities.
    return ToolCall(name=call.name, arguments=json.loads(encoded))


class AgentTools:
    def __init__(self, repo: Repository, message: IncomingMessage, *, now: datetime):
        self.now = utc(now)
        self.repo = repo
        durable, _ = repo.message_result(message.update_id)
        if durable != message:
            raise ValueError('Tool context must match the durable inbox message')
        self.message = durable
        self.snapshot = repo.agent_snapshot(durable.update_id, now=now)
        self._pending: tuple[ToolCall, ...] = ()
        self._reads = {
            'consultar_lista': self._list,
            'consultar_ficha': self._fiche,
            'consultar_propuesta': self._proposal,
        }

    def validate_calls(self, calls: tuple[ToolCall, ...]) -> tuple[ToolCall, ...]:
        """Validate an entire model response BEFORE executing even its first read.

        execute consumes this batch in order; callers must submit the whole
        response, not repeatedly validate individual calls from a response.
        """
        self._pending = ()
        if type(calls) is not tuple or len(calls) > 4:
            raise ValueError('A response permits at most four calls')
        validated = tuple(_validate(call) for call in calls)
        mutators = [i for i, call in enumerate(validated) if call.name in OPERATION_CONTRACTS]
        if len(mutators) > 1 or mutators and mutators[0] != len(validated) - 1:
            raise ValueError('Only one mutator is permitted, as the last call')
        # Keep a separate deep copy so returned nested dictionaries cannot alter
        # the approved batch after validation.
        self._pending = tuple(call.model_copy(deep=True) for call in validated)
        return validated

    def execute(self, call: ToolCall) -> ToolResult:
        call = _validate(call)
        if not self._pending or call != self._pending[0]:
            raise ValueError('Validate the whole batch and execute it in order')
        self._pending = self._pending[1:]
        if call.name in OPERATION_CONTRACTS:
            proposal = self.snapshot.proposal
            return self.repo.apply_agent_operation(
                self.message.update_id, call.name, call.arguments,
                proposal.revision if proposal else None, now=self.now)
        return self._reads[call.name](call)

    def _refresh(self):
        self.snapshot = self.repo.agent_snapshot(self.message.update_id, now=self.now)
        return self.snapshot

    def _list(self, call):
        snapshot = self._refresh()
        data = snapshot.model_context()
        data['untrusted_data'] = True
        reservations = {r.line_id: r.order_id for r in snapshot.reservations}
        parts = ['Lista guardada (las propuestas no están guardadas):']
        for line in snapshot.lines:
            quantity = str(line.quantity) if line.quantity is not None else 'cantidad desconocida'
            reserved = f'; reservada para pedido {reservations[line.id]}' if line.id in reservations else ''
            parts.append(f'{line.description} [{line.id}, revisión {line.revision}]: {quantity} envases{reserved}.')
        if not snapshot.lines:
            parts.append('La lista está vacía.')
        return ToolResult(name=call.name, data=data, reply=Reply(text='\n'.join(parts)), terminal=False)

    def _proposal(self, call):
        snapshot = self._refresh()
        proposal = snapshot.proposal
        data = snapshot.model_context()
        data['untrusted_data'] = True
        if proposal:
            for item in data['proposal']['items']:
                for index, candidate in enumerate(item['candidates'], 1):
                    candidate['candidate_index'] = index
            # A read never marks or renews a review. Show the persisted status.
            if self.now >= proposal.expires_at:
                reason = 'expired'
            else:
                reason = _revalidate(proposal, snapshot) or (
                    'reviewed' if proposal.reviewed_revision == proposal.revision else 'pending')
        else:
            reason = 'no_pending'
        data['reason'] = reason
        reply = render_proposal(ProposalDecision(proposal=proposal, reason=reason), snapshot)
        return ToolResult(name=call.name, data=data, reply=reply, terminal=False)

    def _fiche(self, call):
        query = call.arguments['query']
        observations = self.repo.find_products(query)
        parts = ['Observaciones históricas: no acreditan precio, stock ni disponibilidad actuales.']
        for product in observations:
            price = (f'{product.price_cents // 100},{product.price_cents % 100:02d} €'
                     if product.price_cents is not None else 'precio no observado')
            stock = ('stock no observado' if product.availability is None else
                     'stock observado disponible' if product.availability else 'stock observado no disponible')
            parts.append(f'{product.title} — fuente {product.store_id} ({product.url}); '
                         f'observado {product.observed_on}; precio observado {price}; {stock}; '
                         f'{product.format_note or "sin detalle de formato"}.')
        if not observations:
            parts.append(f'No tenemos ficha observada de {query}; no se ha registrado ninguna solicitud.')
        return ToolResult(name=call.name, data={
            'query': query, 'observations': [asdict(product) for product in observations],
            'historical_only': True, 'untrusted_data': True,
        }, reply=Reply(text='\n'.join(parts)), terminal=False)
