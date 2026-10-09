# Diagnóstico E4B: no hay corrección de producción demostrada

Base `c657a79`; solo diagnóstico sintético local, sin modificar producto/configuración
ni activar Telegram. Continúa pendiente la aceptación del agente guiado.

## Experimento congelado

18 inferencias: nueve pares baseline/ablación; siete entradas sintéticas, repetición
de petición individual y cantidades reordenadas, orden de brazos invertido al repetir.
Solo se retiró el bloque de procedimiento legacy de completar propuestas del system.
No cambiaron herramientas/schemas, mensajes/contexto, modelo ni recursos.

- Modelo `gemma4:e4b-it-q4_K_M`, digest
  `dc35e8d9c6061baa6f0fa870975ab6932e2542b579b13ea0f199fa4bb7300c9c`.
- Ollama0.35.1 anuncia tools y renderer/parser gemma4; observar herramientas nativas
  en algunos casos descarta falta total de soporte, no garantiza comprensión.
- Temperatura0, thinkFalse, num_ctx8192, num_predict512, timeout120s.
- 10.218–15.081 bytes de mensajes+schemas, dentro del límite24.000.
- Prerregistro SHA256
  `b5e690dbc61a827a6247d2bb2dc980deddb18087ec894484fa158e3d73fbf2f6`.
- Respuestas crudas SHA256
  `7165fb42b53842f64872a9bb34c5d9242c2b2e8cd4d0fbfb9e970da3f01f349b`.
  `.gitattributes` local conserva exactamente los bytes originales sin convertir
  finales de línea de estos dos artefactos y reconoce su CRLF al comprobar whitespace.
- 18/18 llamadas HTTP200; no reintentos, instalación, descarga, reinicio ni parser de prosa.

## Resultados

| Métrica /9 | Baseline | Sin bloque legacy |
|---|---:|---:|
| Envoltorio nativo |5|5|
| Herramienta ofrecida y schema válido |3|5|
| Operación/argumentos correctos según oráculo congelado |2|3|
| Fallback de decodificación |6|4|
| Nativo válido, semántica incorrecta |1|2|

Las dos respuestas con `completar_propuesta` no ofrecida pasaron a `proponer_altas`
válida, pero equivocada: abriría tema nuevo en lugar de corregir el borrador.
La petición individual, duplicados y corrección mixta siguieron devolviendo contenido,
no llamadas nativas. La cantidad con foco mejoró en un solo par, insuficiente para
generalizar. Consulta e incremento control conservaron sus resultados correctos.

**No adoptar esta ablación como arreglo.** Explica una contribución de instrucciones
incompatibles, no la causa general ni una solución. Válido no equivale a correcto.
La menor longitud y el contenido retirado no se aislaron entre sí en esta prueba.
Repeticiones con temperatura0 no son muestras estadísticamente independientes.

## Verificación y límites

Revisión independiente aprobó evidencia y recomputó semántica desde respuestas crudas,
oráculos congelados y bytes. Verificación del controlador:18 replays del decodificador,
hashes, factor único y reductores puros sin mutaciones pasan. El verificador local suma
flags semánticos registrados: esa limitación no valida por sí sola los scores; el
revisor los recalculó por separado. No se ejecutó almacenamiento/diálogo completo,
holdout no visto, aceptación real nueva ni pruebas Telegram.

Artefactos originales, scripts desechables y reporte completo:
`.superpowers/sdd/2026-10-09-e4b-native-quality/`. Prerregistro y18 respuestas se
conservan también en esta carpeta como evidencia, no como integración de producto.
No se registran inventario completo de modelos, conversaciones ni settings privados.

## Siguiente etapa propuesta — requiere aprobación

Un spike desechable que compare el contrato nativo actual con salida estructurada
validada, manteniendo el mismo modelo y permisos. La aplicación debe seguir fijando
foco/operaciones admisibles y confirmar por separado; schema correcto tampoco prueba
comprensión. Entradas/oráculos nuevos congelados, presupuesto pequeño y resultados
por semántica, ambigüedad y seguridad. Esto no está autorizado ni implementado por
escribir el diagnóstico; si se quiere conservar un contrato nuevo, requiere diseño
arquitectónico, revisión de spec y plan antes de integrar.
