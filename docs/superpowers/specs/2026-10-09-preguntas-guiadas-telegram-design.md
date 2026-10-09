# Preguntas guiadas y respuesta libre en Telegram

Fecha: 2026-10-09. Estado: diseño conversacional aprobado; especificación escrita
pendiente de revisión humana. Autoriza documentación, no implementación, migración
privada, activación, reinicio ni publicación. Base de lectura: worktree
`feat/skills-agent`, `bd00337`. Complementa el diseño de agente de 2026-10-08;
no declara completada su aceptación pendiente.

## 1. Objetivo y decisiones aprobadas

Hablar normalmente con el asistente, sin aprender comandos. Cuando falte un dato
o una selección, la aplicación hace una pregunta concreta con opciones; escribir
una respuesta sigue siendo posible. No imponer un formulario desde el primer
mensaje ni volver a preguntar datos ya completos.

El usuario aprobó por secciones:
- Enfoque híbrido: botones solo cuando hagan falta, respuesta libre disponible.
- Preguntas persistentes, recuperación tras reinicios y rechazo de botones antiguos.
- Consultas que conservan lo pendiente y nuevos productos que no sustituyen el borrador.
- Elección explícita antes de incorporar nuevos productos a un borrador pendiente.
- Confirmación final separada y vinculada al resumen completo vigente.
- Reglas de duplicados, unidades, cancelación y aceptación de conversaciones completas.

La aplicación controla identidad, estado, preguntas, botones, resultados y escritura.
E4B interpreta y propone; no confirma, compra, decide permisos ni inventa éxito.
Se conserva un agente local, sin framework multiagente ni instalación de OpenCode.

## 2. Evidencia: qué funciona y qué no

Las simulaciones no son código de producción ni pruebas de integración Telegram.
Sus preguntas, botones e historial eran estado en memoria.

| Prueba | Resultado | Lectura válida |
| --- | --- | --- |
| A/B/C: actual frente a instrucciones breves/contexto legible | 21/27 frente a 12/27 y 12/27 | Acortar instrucciones no mejoró ese conjunto |
| D: pregunta y herramienta de respuesta acotada | Cantidades 15/15; ambigüedades 0/6 | Mejor interpretación, pero conjeturas inaceptables |
| E: alcance explícito y copia literal de referencia | Comparables: 12/27 frente a actual 21/27 | El filtro bloquea también respuestas válidas |
| E: productos adicionales | 6/6 | Reconocimiento prometedor; incorporación requiere elección |
| E: conversaciones libres completas | 0/15 | No se ha resuelto el diálogo libre; se detuvo cada secuencia al primer fallo |
| E: replay sin filtro literal | 33/45, con seis conjeturas ambiguas aceptadas | No adoptar el filtro relajado |
| Conversaciones guiadas, con correcciones naturales | 12/12 | Evidencia limitada favorable a fijar el alcance mediante elecciones |

Las repeticiones con temperatura cero comprueban estabilidad, no independencia
estadística. Las variantes cambiaron varios factores; no atribuir el resultado a
un componente aislado. Una aclaración genérica tras validación fallida no cuenta
como comprensión correcta del modelo. Confirmación final no vuelve aceptable una
interpretación inventada en el borrador.

Evidencia desechable conservada en el directorio temporal aprobado, carpetas
`shop-agent-ab-20261009`, `shop-question-spike-20261009` y
`shop-question-scope-20261009`. El registro de ejecución está en
`.superpowers/sdd/2026-10-08-agente-skills-herramientas/progress.md`.
No incorporar esos scripts directamente ni publicar conversaciones privadas.

## 3. Alternativas y enfoque elegido

1. **Híbrido guiado, elegido:** aplicación fija preguntas/alcance y E4B interpreta
   respuestas pequeñas; botones dan una vía inequívoca. Más estado duradero,
   pero conserva conversación y protege lo pendiente.
2. **Formulario obligatorio:** selección y cantidad por producto siempre.
   Menos interpretación, pero obliga a demasiados pasos incluso en peticiones claras.
3. **Texto libre con otro prompt:** menos interfaz, pero las pruebas actuales no
   sostienen su fiabilidad. No activar por una puntuación parcial favorable.

La primera versión implementa el ciclo duradero de preguntas y la vía guiada.
La respuesta libre conserva su disponibilidad, no una promesa de resolver todas
las frases automáticamente. Las interpretaciones cuyo alcance no pueda acreditarse
se presentan como una pregunta, no se aplican por confianza declarada por E4B.

## 4. Experiencia de conversación

### 4.1 Cantidades y destinatarios

Ejemplo: huevos, carne y atún, sin cantidades:

> ¿Qué cantidad quieres de huevos, carne y atún?
> Uno de cada / Misma cantidad / Cantidades diferentes / Escribir respuesta

- `Uno de cada`: asigna una unidad de compra a las posiciones ofrecidas, solo en
  el borrador; unidades obligatorias de productos especiales siguen pendientes.
- `Misma cantidad`: fija explícitamente ese grupo y pregunta su cantidad.
- `Cantidades diferentes`: pregunta por un producto concreto, conserva las respuestas
  previas y avanza a los restantes; no necesita elegir herramientas generales.
- `Escribir respuesta`: conserva el contexto; no inventa cantidades ni concede
  alcance colectivo. Puede contestarse por texto sin pulsar este botón.
- Si el destinatario no está resuelto, preguntar «¿De cuál o cuáles?» con productos
  y opción `Todos`; una selección conserva cualquier cantidad candidata todavía
  sin aplicar y pide aclararla si tampoco estaba resuelta.

Una selección de grupo o producto no guarda líneas. Cantidades positivas enteras
usan las reglas de unidad actuales; una cantidad desconocida no equivale a cero.
No completar todas las posiciones por deducir que una pregunta plural autoriza
una respuesta singular. La recuperación de una cantidad anterior requiere un
turno durable de esa conversación, no un antecedente inventado por el modelo.

### 4.2 Correcciones, consultas y nuevas peticiones

- Una corrección modifica solo las posiciones resueltas y vuelve a revisar el
  borrador completo. Si no se acredita la posición, preguntar por ella.
- Consultar lista/ficha no borra ni renueva las preguntas pendientes. Distinguir
  siempre lista guardada, borrador y observaciones históricas.
- Una petición de productos nuevos se conserva en un tema adicional separado,
  con su texto original, elementos y cantidades ausentes; no sustituye el borrador.
- Abrir ese tema suspende la confirmación final, aunque la revisión anterior
  estuviera completa. Tras añadirlo o rechazarlo se muestra el resumen vigente
  antes de volver a habilitar confirmación; no reutilizar un botón final antiguo.
- Preguntar `Añadir al borrador / Mantener sin añadir`. Mantener descarta solamente
  el tema adicional. Añadir preserva los elementos existentes y su procedencia,
  incorpora los nuevos, recalcula conflictos, invalida la revisión y ofrece lo pendiente.
- No ofrecer sustitución automática de borrador. El usuario puede cancelar
  explícitamente y empezar otra petición.
- Hay como máximo un tema adicional pendiente. Otra petición nueva mientras se
  decide no lo reemplaza silenciosamente: preguntar cuál resolver o descartar.
- Una petición distinta de altas se deriva al flujo existente tras conservar el
  borrador; si ese flujo lo reemplazaría, exigir cancelación explícita primero.

### 4.3 Resumen y controles

Al quedar completos los datos y decisiones, mostrar el resumen íntegro y
`Confirmar / Corregir / Cancelar`. Aceptar también los controles textuales existentes.
`Corregir` pregunta por el elemento y el dato, sin dar permiso al modelo para guardar.

El significado de `sí`/`no` depende de la pregunta vigente: aceptar un destinatario
o añadir un tema NO equivale a confirmar la lista. En la pregunta de tema, `no`
mantiene el borrador principal. `Cancelar` explícito descarta el borrador y sus
preguntas/tema, nunca elimina líneas guardadas. La negativa final descarta la
propuesta revisada conforme a los controles existentes.

Una expresión mixta como «sí, pero carne dos» es una edición, no una confirmación.
Hace falta nuevo resumen y confirmación posterior. Una pregunta incompleta no
puede transformarse en un botón de guardar mediante un `sí`.

## 5. Componentes y límites

- **Contratos de dominio:** entrada discriminada `message`/`callback`, preguntas,
  opciones tipadas, temas adicionales y respuesta con teclado opcional. Los
  mensajes históricos y respuestas sin teclado siguen siendo válidos.
- **Controlador guiado**, dentro de `shopping_agent/`: decide la siguiente pregunta
  a partir del estado real, reduce selecciones y aplica controles. No usa red ni SQL.
- **Intérprete acotado E4B:** ve pregunta, elementos pertinentes, texto original y
  últimos turnos autorizados. Propone una respuesta o consulta/cancelación/nuevo tema.
  Los tokens de botones, permisos e identidades no forman parte de sus argumentos.
- **Repositorio:** valida procedencia, alcance/versiones y realiza una transacción
  de pregunta/propuesta/tema, resultado de inbox y respuesta de outbox.
- **TelegramIO:** autentica mensajes y callbacks, conserva cursor, entrega texto
  y teclados; no interpreta intenciones ni confirma cambios directamente.
- **Runtime:** procesa los dos tipos de evento en orden de update, sin dos workers.
  Conserva recuperación de pedidos y rutas de comandos sin mezclar sus permisos.

Archivos existentes afectados por una futura implementación: `domain.py`,
`storage.py`, `shopping_agent/{contracts,conversation,storage,proposals,replies,tools,ollama}.py`,
`telegram_io.py`, `runtime.py`, configuración/CLI y migraciones. Nuevos módulos
de preguntas/controlador se mantienen dentro del paquete existente. La división
concreta en tareas pertenece al plan posterior, no a esta autorización documental.

## 6. Estado duradero y procedencia

### 6.1 Pregunta vigente

Una pregunta vigente por propietario/chat. Contiene identificador generado por
aplicación, tipo, versión propia, propuesta y revisión de referencia, posiciones,
candidatos de filas con revisión, opciones tipadas, evento creador, texto visible,
estado, creación/caducidad y aviso de outbox asociado. Para nuevos productos incluye
tema y versión. Caduca a más tardar con el borrador: responder o consultar no
extiende una pregunta vieja sin una transición explícita.

Tipos: elegir alcance, cantidad compartida, cantidad individual, unidad,
duplicado, fila de origen, condición, tema adicional y revisión final. La aplicación
ofrece únicamente opciones válidas en ese estado. Seleccionar una opción consume
esa versión de pregunta aunque todavía no cambie la revisión del borrador.

Una edición invalida pregunta y revisión anterior; una consulta no. Estado
consumido conserva resultado y evento consumidor para replays. Si se caduca,
no reutilizar cantidades candidatas viejas: mostrar expiración y pedir nueva petición.

### 6.2 Propuesta y tema

No reconstruir la propuesta desde un botón perdiendo origen, condiciones,
candidatos, decisiones, unidades o incrementos. Incorporar un tema es una operación
del controlador sobre la propuesta completa: preserva ID, aumenta revisión,
añade posiciones nuevas sin renumerar anteriores y guarda la cadena de eventos
de origen de cada aportación. Recalcula duplicados internos/guardados y selecciones
afectadas; no suma. Si no puede preservar un estado, falla sin reemplazarlo.
El límite sigue siendo 20 elementos por propuesta. Si la incorporación lo supera,
mantener ambos estados sin aplicar y pedir dividir la petición; no quitar elementos
anteriores ni truncar los nuevos para encajar.

Extender el contrato persistido de propuesta de forma versionada para sus aportaciones
y el nuevo testigo de revisión. Las propuestas v1 se leen y mantienen con sus testigos
existentes hasta una transición que las actualice; no convertir su procedencia en
un texto sintético. Las líneas guardadas antiguas no se reescriben ni se limpian.

### 6.3 Inbox, outbox e historial

Siguiente migración v10 sobre la base v9, transaccional y con rollback de migración
fallida. Inbox añade tipo/payload validado para callback, manteniendo columnas y
semántica de mensajes existentes. Para callback, `text` vacío es compatibilidad
física, NO una frase ejecutable. `update_id` sigue siendo la clave/orden global.
Persistir también `callback_query_id` único y comprobar identidad de payload en
replays; un mismo ID con distinto contenido falla cerrado.

El reductor recibe el evento tipado y su selección validada. No construir un
`IncomingMessage` sintético con «sí» o con el nombre del botón para ejecutar
parsers legacy. La procedencia v2 acredita los eventos callback auténticos y sus
opciones; los testigos de mensajes v1 conservan su validación original.

Outbox conserva `Reply` serializado y añade teclado opcional versionado; leer
avisos antiguos sin teclado. Tabla de entregas registra aviso, chat, ID del mensaje
Telegram y digest del contenido mostrado; no confundir aviso confirmado en SQLite
con mensaje efectivamente entregado. Owner checks incluyen todas las tablas nuevas.

Historial autorizado: los últimos tres pares usuario/respuesta completados de esa
conversación, más pregunta y estado actuales. Callback se representa al modelo
por su selección tipada validada, nunca por bytes de token. Si el contexto completo
supera el presupuesto, aclaración controlada sin truncar hechos o ejecutar cambios.
Mantener límites existentes: 24.000 bytes de mensajes+schemas, cuatro llamadas al
modelo, ocho herramientas por turno, temperatura 0, `think=False`, contexto 8192
y salida 512, sin aumentar recursos para ocultar fallos.

## 7. Botones Telegram, autenticación e idempotencia

Mantener `Bot` y long polling actuales; solicitar `message` y `callback_query`.
No introducir `Application`, `ConversationHandler`, cache de callbacks en memoria,
dependencias nuevas ni webhook. Usar teclado inline de cadenas simples.

Cada opción lleva token opaco `q:` más 22 caracteres base64url de 128 bits aleatorios.
Sus 24 bytes ASCII respetan el límite de 1–64 bytes de `callback_data`. La tabla
de tokens apunta a pregunta/version/opción/aviso; no codifica productos, SQL,
cantidades ni autorización elegida por el cliente.

Aceptar callback solo si usuario permitido no bot, chat privado permitido,
mensaje accesible y emitido por nuestro bot, payload string de formato válido,
token ofrecido en una pregunta persistida y entrega conocida de ese aviso/chat.
Rechazar modo inline, mensajes inaccesibles, game callbacks, otro propietario,
tokens desconocidos/caducados y payload manipulado. El texto/nombre de un botón
no acredita su opción. Mantener rechazo actual de mensajes reenviados/citados.

En una transacción: comparar versión de pregunta/propuesta/tema, validar opción,
consumir token/pregunta, reducir estado y registrar resultado+outbox. Repetición
del mismo update o callback devuelve su resultado. Otra pulsación de la opción
consumida por el mismo propietario devuelve el resultado registrado sin reaplicar.
Otra opción de la misma pregunta consumida devuelve «pregunta anterior», sin cambios.

Si un envío tuvo éxito pero se perdió la respuesta, el aviso puede duplicarse:
ambas copias comparten opciones y consumo único. Una copia cuyo ID no quedó
registrado no concede autoridad: mostrar aviso vigente de nuevo. Desactivar teclados
viejos es mejora visual, no requisito de seguridad ni motivo para fallar el runtime.

Responder rápidamente al callback para retirar el indicador de espera, después
de registrar la recepción. El acuse no significa operación realizada. Separar
su éxito/fallo del procesamiento duradero; una query ya caducada no hace repetir
el cambio ni bloquea entrega de avisos. No llamar a Telegram dentro de SQLite.
Inputs no autorizados se ignoran y no se conservan; el cursor avanza tras el lote
validado conforme al patrón actual.

Los tokens e historial quedan en almacenamiento privado con las protecciones
actuales. No registrar credenciales, tokens reutilizables ni conversación privada
en logs públicos; las evidencias compartibles usan propietarios y productos ficticios.

## 8. Resúmenes visibles y confirmación final

La revisión final tiene un testigo persistido: ID/revisión de propuesta, digest
del resumen completo, evento creador y entrega Telegram acreditada. Un botón
`Confirmar` referencia ese testigo, no una autorización genérica.

Mostrar resumen y teclado de revisión en UN mensaje que quepa en los límites
existentes de aplicación y en 4.000 unidades UTF-16 conservadoras. Si no cabe,
ofrecer reducir/dividir el lote; no truncar, no fragmentar una revisión habilitada
ni habilitar confirmación. Otros mensajes legacy mantienen su entrega por fragmentos.

Confirmación textual igualmente exige revisión vigente entregada y posterior al
evento de revisión, sin edición entre ambas. Confirmación durante otro tipo de
pregunta no guarda, aunque una revisión antigua existiera. Si la entrega no se
acredita, reenviar resumen antes de habilitar confirmación. No prometer que Telegram
demuestra lectura humana: demuestra entrega de la versión, más acto explícito.

Al confirmar, validar de nuevo cantidad/unidad, condiciones, duplicados, reservas
y revisiones de filas dentro de la transacción de guardado. Éxito operativo se
redacta desde el resultado real. Confirmación repetida no crea nuevas líneas.

## 9. Interpretación libre y manejo de incertidumbre

No portar el prompt/contrato de E ni relajar su filtro literal como solución.
No crear listas de frases aceptadas ni parsers de variantes de «uno de cada».

El controlador concede alcance determinista cuando el usuario elige producto/grupo
o contesta a una única posición. E4B entonces interpreta datos dentro de ese alcance.
Fuera de ese caso propone una interpretación candidata: aplicación comprueba
referencias y reglas, y pregunta por destinatario cuando no puede acreditarlo.
La candidatura no modifica el borrador mientras no exista alcance seleccionado:
ofrecer la selección concreta derivada, conservar su cantidad candidata sin aplicar
y resolverla con la respuesta a esa pregunta. Una respuesta textual que coincide
con una opción ofrecida se trata como selección de esa pregunta, no como permiso
para otra operación. No confiar en que mencionar un nombre en el texto demuestre
por sí solo una asignación correcta ante negaciones o referentes múltiples.
Una clasificación de confianza de E4B o una cita coincidente por sí sola NO concede
alcance. Las referencias naturales colectivas no acreditadas se convierten en
elección de grupo, sin aplicar cantidades a todos; también puede responderse a
esa elección por texto a través del intérprete acotado y controles de selección.

Las preguntas de selección muestran productos/alcance reales, no solo «acláralo».
Una respuesta libre inválida no pierde datos ni provoca «lista no cambiada» como
sustituto de la pregunta necesaria: se vuelve a ofrecer el dato concreto pendiente.
Nunca enviar libremente la prosa del modelo, ni dar por completado un fallo de
interpretación porque el usuario podría corregirlo al confirmar.

Elegir schemas breves de respuesta y escape separados, sin herramienta de guardar
o confirmar y sin posiciones inventadas para productos nuevos. Su forma final se
evalúa antes de activar: no afirmar que estos experimentos ya validaron el decodificador
de producción. La selección explícita por botones es la vía determinista obligatoria
como alternativa, pero no se exige usarla en mensajes cuyo contexto ya esté resuelto.

## 10. Compatibilidad, activación y rollback

- Añadir opción experimental de preguntas guiadas, desactivada por defecto y válida
  solo con `skills_agent`. Mantener modelo, engine y comandos legacy existentes.
- Un cambio de engine/flag con worker parado invalida preguntas/tokens/temas y
  revisiones no confirmadas; conserva datos guardados. No mover preguntas al legacy.
- La migración no importa ni transforma la lista privada para esta prueba. Antes
  de usar una base real se necesita autorización y respaldo local consistente.
- El rollback operativo usa el NUEVO código con el flag apagado, no ejecutar código
  v9 contra base v10 ni bajar la versión de schema. Restauración de respaldo solo
  con autorización y sin descartar cambios posteriores.
- La primera prueba Telegram usa base separada, perfiles de tiendas sin abrir y
  bloqueo de buy/resume/checkout también en comandos explícitos. `dry_run` solo
  no basta para cumplir la promesa de compras bloqueadas.
- Un solo worker/bot; coordinar stop/start autorizado y mantener el lock original
  mientras dure el experimento. No reiniciar la instancia actual al escribir el diseño.

Fuera de alcance: compras nuevas, limpieza de productos, otros modelos, despliegue,
instalación OpenCode/AnyList/OpenClaw, memoria ilimitada y migración privada automática.

## 11. Criterios de aceptación y pruebas

**No son suficientes** los tests unitarios verdes ni las 12 conversaciones guiadas
anteriores. Congelar entradas, expectativas y parámetros antes de evaluar el código
final; guardar peticiones/respuestas crudas, herramientas, validaciones, preguntas,
versiones, avisos entregados y estado resultante en datos sintéticos.

### Repositorio y controlador
- Migración 0→10 y 9→10, historial de comandos/pedidos/respuestas antiguo y rollback
  de migración interrumpida; ninguna fila de lista modificada por migrar.
- Estado/pregunta/outbox atómicos; fallo antes/después de cada commit y reinicio.
- Aportaciones nuevas preservan todas las propiedades y procedencia del borrador;
  conflictos internos para ambas posiciones, sin fusión ni pérdida de condición.
- Scope compartido/individual, respuestas parciales, cantidades desconocidas,
  unidades obligatorias, incrementos base+adicional=total, sustituciones y reservas.
- Tema nuevo, negativa que conserva borrador, cancelación explícita, consulta y
  comandos que invalidan versiones incompatibles sin dejar procedencia huérfana.
- Revisión íntegra, oversized Unicode, entrega acreditada, edición tras revisión,
  confirmación prematura/mixta/duplicada y no escritura en respuestas intermedias.

### Telegram simulado, sin red ni credenciales
- Mensajes y callbacks mezclados con cursor duradero y autenticación completa.
- Token/payload falsificado, usuario/chat incorrecto, mensaje inaccesible/inline,
  mensaje no emitido por bot, entrega desconocida, versión/tema caducado.
- Mismo update/query/pulsación reentregados, opción diferente tras consumo, reinicio
  tras aplicar antes de enviar, envío incierto y fallo al editar teclado antiguo.
- Reply histórico sin teclado, límites byte/UTF-16 y acuse de callback no operativo.

### E4B real y conversaciones completas
- Repetir mínimo tres veces los casos previos y variantes nuevas no incluidas como
  ejemplos del prompt. Mantener mediciones de comprensión separadas de fallback.
- Incluir «Los 3 es uno de cantidad», «Uno de cada uno», cantidades reordenadas,
  cantidades parciales, «dos de carne y uno del resto» y respuestas ambiguas.
- Un caso ambiguo debe preguntar SIN asignar destinatarios/cantidades. Rechazar una
  conjetura cuenta como seguridad conservada, no como comprensión del modelo.
- Una respuesta válida debe completarse, o resolver una pregunta específica y
  completar el flujo sin bucle. La mera ausencia de escrituras no la hace correcta.
- Probar nuevas altas durante cantidad/revisión, consulta seguida de respuesta,
  negativa a tema nuevo, correcciones, cancelación y confirmación final, con y sin botones.
- Evaluar selección libre de producto después de pedir aclaración; conservar la
  cantidad candidata solo con su procedencia durable y dentro de la misma pregunta.
- Resolver también los fallos anteriores de consultar lista y duplicados internos;
  el nuevo diseño no los exime ni da por completada la Task 7 original.

Umbral de la primera versión: todas las invariantes de seguridad pasan; cero
asignaciones ambiguas aplicadas y cero escrituras sin confirmación; todas las
conversaciones del conjunto guiado y de respuestas libres acotadas terminan con
el estado esperado. Interpretación colectiva libre que no pase permanece en
aclaración guiada, explícitamente etiquetada como limitación. Sin alcanzar esos
criterios no activar el candidato en Telegram. Después de aceptación, probarlo
con el usuario en la lista separada bajo autorización de lanzamiento.

## 12. Documentación consultada y siguiente etapa

Dependencia declarada: `python-telegram-bot>=22.5,<23`. Se consultó Context7 para
v22.5 y la documentación oficial de CallbackQuery. No se necesita el extra de
arbitrary callback data: los tokens son cadenas y su registro vive en SQLite.

- https://docs.python-telegram-bot.org/en/v22.5/telegram.callbackquery.html
- https://docs.python-telegram-bot.org/en/v22.5/telegram.inlinekeyboardbutton.html
- https://docs.python-telegram-bot.org/en/v22.5/telegram.bot.html

Siguiente etapa: revisión humana de ESTA especificación escrita. Solo tras su
aprobación preparar el plan con writing-plans y revisarlo antes de elegir cómo
implementar. No ejecutar tareas del plan anterior ni integrar simulaciones mientras
se decide este cambio. No confundir aprobación del diseño con permiso de despliegue.
