# Respuestas conversacionales redactadas por Gemma

Fecha: 2026-10-08. Estado: especificación escrita aprobada por el usuario.
La aprobación autoriza preparar el plan, no implementarlo ni activar el bot.

## Objetivo y alcance aprobado

El usuario quiere que Gemma redacte la conversación, en lugar de recibir
plantillas rígidas y confusas. El ejemplo observado fue «Ya tienes arroz:
1 envases, 2 envases. 1: cambiar cantidad (total); 2: añadir otra línea».
Debe explicar las entradas existentes y preguntar de forma legible, sin
confundir cantidades con índices ni usar lenguaje interno como «línea».

Todas las respuestas de conversación natural del proveedor Ollama pasan por
redacción, incluidas respuestas a cantidades y confirmaciones cerradas, altas,
duplicados, selección, sustitución, cancelación, caducidad, consultas de lista
y consultas de productos. Los comandos que empiezan por `/` conservan sus
respuestas deterministas. Las autorizaciones de compra y avisos del checkout,
recovery y transporte quedan fuera de la generación. No se añade conversación
general ni un segundo proveedor. OpenAI y commands_only conservan su conducta.

Éxito: mensajes breves en español, datos y opciones inequívocos, con Gemma
redactando después de conocer el resultado real. No basta una suite offline:
se requiere probe aislado con el modelo existente y evidencia de claridad.
La aceptación en Telegram privado sigue siendo un paso aparte autorizado.

## Decisión arquitectónica

Seleccionado: ejecución controlada primero, redacción local después.
Alternativas descartadas: interpretar y responder antes de guardar (podría
anunciar una operación que fracasa), o parafrasear la plantilla confusa sin
estructura (perpetúa ambigüedades y pierde hechos/opciones).

1. La aplicación interpreta y revalida la petición como ahora.
2. Una transacción guarda cambios, contexto y un trabajo de presentación con
   una instantánea de hechos confirmados y una respuesta de respaldo.
3. Fuera de esa transacción se pide a Gemma una redacción de esa instantánea.
4. Se valida la propuesta; una transacción corta guarda la respuesta definitiva,
   completa el inbox y crea el outbox. Solo entonces puede enviarse a Telegram.

El texto del modelo nunca llega a `Intent`, al reducer, a SQL de la lista ni
a checkout. El nuevo redactor no decide qué preguntar ni qué opción existe.

## Hechos de presentación y contrato

Un contrato tipado e inmutable, versionado, describe:
- Resultado: consulta, alta, cantidad establecida, sustitución, cancelación,
  solicitud de aclaración o ausencia de cambios.
- Productos y cantidades realmente guardados; cantidad desconocida explícita,
  sin convertirla a cero ni sumar entradas.
- Entradas relevantes ordenadas y distinguibles; ordinales de presentación
  no ambiguos y separados de las cantidades.
- Pregunta activa y opciones autorizadas, con claves estables y orden vigente.
- Origen/destino para sustitución y decisión de cantidad aún pendiente.
- Observaciones de productos realmente consultadas y sus límites históricos.

La instantánea se produce en la misma transacción que el resultado, no mediante
una nueva lectura posterior que podría describir otro estado. Internamente
puede contener referencias necesarias para auditar y recuperar, pero la
serialización al modelo las elimina. No se envían UUID, revisiones, user/chat,
credenciales, confirmaciones internas, configuración, rutas, URLs privadas ni
historial completo. Se envía solo el contexto mínimo de presentación; no es
necesario reenviar el mensaje libre del usuario ni su conversación.

Las descripciones de productos y observaciones son datos no fiables. El
prompt no interpreta instrucciones incrustadas en ellas. Los hechos obligatorios
no se truncan silenciosamente: si la instantánea excede el presupuesto, se usa
el respaldo íntegro o una presentación paginada determinista, sin omitir
opciones que el controlador espera. El plan fijará límites exactos y tests.

## Redacción y verificación

Gemma recibe un esquema de salida estructurada con texto y referencias de
presentación a hechos/opciones permitidos. Las referencias son índices locales
a esa solicitud, no IDs internos ni permisos. El contrato separa explicación,
hechos y pregunta/opciones para verificar su cobertura y orden.

La aplicación comprueba estrictamente el esquema, límites de longitud, ausencia
de campos extra, referencias válidas, hechos obligatorios, cantidades/unidades,
distinción entre entradas y presencia de todas las opciones autorizadas. Los
nombres y valores críticos se insertan desde la instantánea mediante referencias,
no desde copias inventadas del modelo. La salida no puede aportar un nuevo
producto, cantidad, URL, opción, destino de sustitución ni acción ejecutable.

Se comprueba además consistencia con el resultado: no anunciar una modificación
en una pregunta pendiente ni una compra, no sugerir suma automática, no convertir
una cantidad total en incremento y no presentar observaciones como stock actual.
Estas comprobaciones deben ser conservadoras: ante una formulación no verificable
se usa el respaldo, no otro modelo como juez. Las pruebas deben incluir
negaciones e inversiones («no he añadido»/«he añadido»), omisión de opciones,
cantidades falsas y texto malicioso en nombres.

Límite explícito: ni un prompt ni comprobaciones léxicas prueban la verdad de
cualquier texto libre. El texto generativo se mantiene subordinado a bloques
de hechos y opciones controlados; se documentará exactamente qué se verifica
y qué riesgo residual queda. No se afirmará infalibilidad ni se relajarán
validadores para aumentar la tasa de mensajes generados. Si el probe muestra
que una clase de respuesta no puede verificarse de manera útil, se informa al
usuario antes de ampliar la libertad del modelo o excluir esa clase del alcance.

Estilo: español claro, breve, sin jerga técnica ni UUID. Unidades en singular
o plural correcto. Duplicados y selecciones en entradas separadas, con pregunta
comprensible; numeración solo cuando la selección la necesita. Cancelación
visible cuando esté permitida. Confirmar productos y cantidades reales, sin
afirmar haber comprado ni dar disponibilidad no observada.

## Respaldo y recursos

El respaldo se mejora antes de activar la generación; no se conserva el texto
confuso del ejemplo. El usuario siempre obtiene una respuesta correcta y legible
si hay timeout, proveedor caído, JSON inválido, contenido rechazado o presupuesto
de contexto excedido. No se expone la excepción ni se menciona un cambio exitoso
si no ocurrió. No se realizan reintentos de redacción en bucle.

Se reutilizan las protecciones de Ollama: loopback explícito, sin proxies del
entorno, sin redirects, no streaming, cliente cerrado y errores saneados.
El redactor tendrá presupuesto total propio y acotado, independiente del de
interpretación; el plan fijará el valor y medirá espera añadida. No se descarga
modelo, se reinicia servicio ni se fuerza unload. La generación no renueva el
TTL del diálogo; este comienza cuando se guarda su transición de aplicación.

## Persistencia, recuperación y replay

La migración siguiente añade trabajos durables de presentación por update,
sin modificar listas, pedidos, snapshots, reservas, offsets ni respuestas
históricas. El payload interno y el estado del trabajo se validan estrictamente.
La comprobación de propietario incluye estos trabajos, sin depender únicamente
del inbox. Deben rechazarse propietarios o mensajes discordantes.

Antes de aplicar cualquier acción, `Conversation.handle` comprueba si ya hay
un trabajo preparado para ese update. Si existe, recupera la presentación sin
llamar de nuevo al reducer ni ejecutar la acción. El inbox sigue pendiente
hasta finalizar la presentación; el trabajo preparado marca durablemente que
la operación ya ocurrió. No existe outbox enviable para la respuesta provisional.

Si el proceso cae después del primer commit, retoma el trabajo desde su
instantánea. Puede repetir la redacción no finalizada, nunca la mutación. Si
cae después del commit final, devuelve exactamente el Reply guardado, sin una
nueva generación, renovación de TTL ni outbox duplicado. Una cancelación antes
de finalizar deja un trabajo recuperable; timeout/error ordinario finaliza con
respaldo. La finalización es idempotente y exige un único outbox para el update.

No se mantiene una transacción SQLite abierta durante HTTP. El worker sigue
procesando mensajes secuencialmente; no se introduce paralelismo de diálogo.
Los comandos y los proveedores sin redactor mantienen su transacción actual.
El modo de recuperación considera trabajos preparados aunque el proveedor se
deshabilite: en ese caso finaliza con respaldo, no reaplica la acción.

## Componentes afectados

- Contratos de presentación y validador, separados de `Intent` y del reducer.
- Redactor Ollama independiente, reutilizando transporte seguro y configuración
  local existente, sin ampliar el contexto del intérprete.
- `dialogue_replies.py`: hechos a partir del resultado confirmado y respaldo.
- `dialogue_storage.py`/`storage.py`: preparación/finalización y migración.
- `conversation.py`: ruta de redacción y recuperación; comandos sin cambios.
- `runtime.py`: inyección del redactor cuando el proveedor es Ollama.
- Tests, probe inventado, documentación y evidencia.

No se modifica la autorización de compras, catálogo, tiendas ni recuperación
de pagos. No se mezcla el texto generado con snapshots de pedidos.

## Pruebas y aceptación

1. Caso exacto del usuario: dos entradas de arroz de 1 y 2 envases, sin suma,
   alternativas correctas y texto sin ambigüedad entre índices y cantidades.
2. Altas/cantidades/sustitución confirmadas solo después del guardado; preguntas
   pendientes no afirman éxito. Singular/plural y cantidad desconocida correctos.
3. Todas las clases de conversación natural pasan por el redactor; comandos,
   compras y avisos siguen deterministas. Providers legacy conservan APIs.
4. MockTransport inspecciona payload real sin datos privados/control; modelo
   hostil/incompleto/malformado falla a respaldo sin afectar la lista.
5. Caídas/cancelación antes y después de ambos commits, replay, fallo de outbox,
   propiedad extranjera y reinicio con redactor ausente: cero dobles mutaciones,
   cero outbox duplicados y TTL intacto por presentación.
6. Suite completa, Ruff y revisión independiente antes de declarar completado.
7. Probe con Ollama existente y SQLite temporal: calidad textual, cobertura de
   hechos/opciones, frecuencia de respaldo y tiempos separados de interpretación
   y redacción. Se conserva también evidencia de fallos, sin debilitar validación.

Las pruebas no acceden a `private/`, no envían Telegram real ni tráfico a tiendas,
no crean compras y no reinician procesos. La actualización de la PR existente,
push y aceptación privada necesitan autorización separada; la aprobación del
diseño no autoriza esas operaciones.
