"""Deterministic operational replies. Reducer permission is not a saved result."""

from domain import Reply
from shopping_agent.contracts import AgentProposal, AgentSnapshot, ProposalDecision, ToolResult

MAX_REPLY = 4000
TOO_LONG = (
    "El resumen completo supera el límite de un mensaje. Necesitas reducir o dividir el lote "
    "para revisar todos los datos. Pendiente, sin guardar; no puedes confirmarlo todavía."
)

REASONS = {
    "cancelled": "Propuesta cancelada; la lista guardada no ha cambiado.",
    "rejected": "Propuesta rechazada; la lista guardada no ha cambiado.",
    "expired": "La propuesta ha caducado. Vuelve a formularla; no se ha guardado nada.",
    "stale": "La lista ha cambiado. Vuelve a revisar la propuesta; no se ha guardado nada.",
    "reserved": "Hay una línea reservada. No se ha guardado nada; revisa la lista.",
    "quantity_range": "La suma supera el rango permitido de envases enteros positivos.",
    "diaper_unit": "Indica explícitamente paquetes o envases de pañales.",
    "no_pending": "No hay una propuesta vigente para esa respuesta.",
    "invalid": "No se puede revisar esta propuesta. Resuelve los datos o divide el lote.",
    "condition": "La condición no está comprobada. Aclárala o retírala expresamente.",
    "confirmed": "Confirmación validada; pendiente de guardar por la aplicación.",
}


def proposal_text(proposal: AgentProposal, snapshot: AgentSnapshot, *, review: bool) -> str:
    """Full, untruncated content; the reducer checks this BEFORE enabling review."""
    rows = {line.id: line for line in snapshot.lines}
    parts = [f"Petición original: {proposal.original_text}", "Propuesta (fuera de la lista guardada):"]
    for item in proposal.items:
        unit = item.unit or "envases"
        quantity = str(item.quantity) if item.quantity is not None else "cantidad pendiente"
        origin = rows.get(item.target.id) if item.target else None
        name = origin.description if origin else item.description
        if item.kind == "add":
            label = "nueva línea separada" if item.duplicate_decision == "separate" else "alta nueva"
            if item.duplicate_decision == "set_total":
                label = f"cambiar cantidad total de {name} [{item.target.id if item.target else '?'}]"
            parts.append(f"{item.position}. {label}: {item.description}: {quantity} {unit}.")
        elif item.kind == "increment":
            parts.append(f"{item.position}. Incrementar {name}: {quantity} {unit}.")
            if item.additional_quantity is not None:
                parts.append(f"Adicional solicitado: {item.additional_quantity} {unit}.")
            if item.target is None and not item.candidates:
                parts.append("No hay coincidencia guardada; puedes proponer un alta nueva (otra línea).")
            elif item.target is not None and item.base_quantity is None:
                parts.append("Base desconocida; no es cero. Propón cambiar cantidad total explícita.")
            elif item.base_quantity is not None:
                delta = item.additional_quantity if item.additional_quantity is not None else "?"
                total = item.quantity if item.quantity is not None else "?"
                parts.append(f"Base + adicional = total: {item.base_quantity} + {delta} = {total} {unit}.")
        elif item.kind == "replace":
            parts.append(f"{item.position}. Sustituir {name} por {item.replacement}: {quantity} {unit}.")
        else:
            parts.append(f"{item.position}. Cambiar cantidad total de {name}: {quantity} {unit}.")
        if item.target:
            parts.append(f"Origen seleccionado: {item.target.id}, revisión {item.target.revision}.")
        # Include every offered saved row, even after a selection. Never hide alternatives.
        if item.candidates:
            parts.append("Candidatos/coincidencias guardadas:")
            for index, ref in enumerate(item.candidates, 1):
                row = rows.get(ref.id)
                description = row.description if row else "línea no disponible"
                count = str(row.quantity) if row and row.quantity is not None else "cantidad desconocida"
                parts.append(f"  {index}: {description} [{ref.id}, revisión {ref.revision}]: {count} envases.")
        destination = tuple(ref for ref in item.conflict_signatures if ref not in item.candidates)
        if destination:
            parts.append("Conflictos de destino guardados (no son índices de origen):")
            for ref in destination:
                row = rows.get(ref.id)
                description = row.description if row else "línea no disponible"
                count = str(row.quantity) if row and row.quantity is not None else "cantidad desconocida"
                parts.append(f"  {description} [{ref.id}, revisión {ref.revision}]: {count} envases.")
        if item.target is None and item.candidates and (
                item.kind != "add" or item.duplicate_decision == "set_total"):
            parts.append(f"Selecciona candidato para el producto {item.position} (índice ofrecido).")
        if item.quantity is None and (item.kind != "increment" or (
                item.base_quantity is not None and item.additional_quantity is None)):
            scope = "adicional" if item.kind == "increment" and item.base_quantity is not None else "total"
            parts.append(f"Indica cantidad {scope} y unidad para el producto {item.position}.")
        if (item.kind == "add" and (item.candidates or item.internal_conflicts)
                or item.kind == "replace" and (item.conflict_signatures or item.internal_conflicts)):
            if item.duplicate_decision == "separate":
                parts.append("Decisión de duplicado: línea separada; no se suman ni fusionan.")
            elif item.duplicate_decision == "set_total":
                parts.append("Decisión de duplicado: cambiar cantidad total de la línea seleccionada.")
            else:
                parts.append("Duplicado: decide nueva línea separada o cambiar cantidad total de una línea "
                             "(selecciona candidato); no se suman ni fusionan automáticamente."
                             if item.kind == "add" else
                             "Duplicado de destino: decide mantener una línea separada; no se fusionan.")
        if item.internal_conflicts:
            parts.append("Duplicados dentro del lote con posiciones: "
                         + ", ".join(map(str, item.internal_conflicts)) + ".")
    if proposal.condition:
        parts.append(f"Condición pendiente: {proposal.condition}. No verificada; retírala expresamente o aclara.")
    parts.append("Pendiente, sin guardar. ¿Confirmas?" if review else
                 "Pendiente, sin guardar. Completa los datos y decisiones antes de confirmar.")
    return "\n".join(parts)


def render_proposal(decision: ProposalDecision, snapshot: AgentSnapshot) -> Reply:
    prefix = REASONS.get(decision.reason, "")
    if decision.proposal is None:
        return Reply(text=prefix or REASONS["no_pending"])
    text = proposal_text(decision.proposal, snapshot,
                         review=decision.reason == "reviewed")
    if len(text) > MAX_REPLY:
        return Reply(text=TOO_LONG)
    if prefix:
        text = prefix + "\n" + text
    return Reply(text=text if len(text) <= MAX_REPLY else TOO_LONG)


def render_tool_results(results: tuple[ToolResult, ...]) -> Reply:
    """Only trusted application Reply objects, never model data/prose."""
    text = "\n\n".join(result.reply.text for result in results)
    order_ids = {result.reply.order_id for result in results if result.reply.order_id}
    if len(text) > MAX_REPLY:
        return Reply(text="Los resultados completos superan un mensaje. Consulta cada resultado por separado "
                     "o pide reducir o dividir la consulta; no se muestran resultados truncados.")
    return Reply(text=text or "No hay resultados operativos; no se ha guardado nada.",
                 order_id=next(iter(order_ids)) if len(order_ids) == 1 else None)
