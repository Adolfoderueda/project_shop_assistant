"""Full application-owned guided text; opaque keyboards belong to storage."""

from domain import Reply
from shopping_agent.guided_contracts import GuidedQuestion, GuidedState
from shopping_agent.replies import MAX_REPLY, proposal_text


def review_fits(reply: Reply) -> bool:
    return len(reply.text) <= MAX_REPLY and len(reply.text.encode('utf-16-le')) // 2 <= 4000


def render_question(question: GuidedQuestion) -> Reply:
    if question.kind == 'review':
        return Reply(text=question.text)
    # A written quantity is not a menu index. These prompts offer labels only.
    options = '\n'.join(choice.label if question.kind in {'quantity_single', 'quantity_shared'}
                        else f'{index}. {choice.label}'
                        for index, choice in enumerate(question.choices, 1))
    candidate = ''
    if question.candidate:
        values = '; '.join(
            f'posición {patch.position}: '
            + (str(patch.quantity) if patch.quantity is not None else 'cantidad pendiente')
            + (f' {patch.unit}' if patch.unit else '') for patch in question.candidate.patches)
        candidate = f'\nInterpretación candidata, sin aplicar; destinatario por elegir: {values}.'
    return Reply(text=f'{question.text}{candidate}\n{options}\nPuedes escribir tu respuesta. Pendiente, sin guardar.')


def render_review(state: GuidedState) -> Reply:
    if state.snapshot.proposal is None:
        return Reply(text='No hay borrador pendiente.')
    return Reply(text=proposal_text(state.snapshot.proposal, state.snapshot, review=True)
                 + '\nConfirmar / Corregir / Cancelar')
