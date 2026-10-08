# Diálogo natural: saludos, altas pendientes e incrementos confirmados

Fecha: 2026-10-08. Estado: enfoque conversacional aprobado; especificación escrita
pendiente de revisión. No autoriza todavía implementación, reinicio ni cambios
en datos privados. Parte del código integrado en `feat/shop-assistant`, commit
`0add91f`, no de una rama remota supuesta.

## Intención y evidencia

El usuario quiere conversar con el asistente sin aprender comandos y sin
incorporaciones accidentales. La captura de aceptación muestra:
- «hols» pide aclarar un producto en lugar de saludar.
- «hola que tal» muestra una lista que no se pidió.
- «quiero mas arroz» crea un producto literal llamado «mas arroz».
- «cancelar» descarta la pregunta, pero deja esa entrada en la lista.
- Todas las respuestas comienzan «Aquí tienes el detalle».

Reproducción pura, sin datos privados: `literal_request('quiero mas arroz')`
devuelve `('add', 'mas arroz')`; `validate_model('hola que tal', Intent(action='list'), [])`
acepta la lista. El esquema del redactor permite solo cinco introducciones y
bloques de referencia; por eso una llamada al modelo no implica redacción libre.

Decisiones aprobadas por el usuario:
1. Un alta sin cantidad permanece fuera de la lista como propuesta pendiente.
   «Cancelar» la descarta, sin borrar entradas ya guardadas.
2. «Más» es un incremento: identificar entrada, pedir cantidad adicional y
   confirmar base + incremento = resultado antes de cambiar nada.
3. Revisar el flujo de diálogo, no añadir solo excepciones al texto; conservar
   validación de acciones y probar la secuencia completa con Gemma real.

## Objetivos y límites

Prioridad: impedir mutaciones equivocadas; después, claridad y naturalidad.
Saludar no consulta la lista. «Más» no forma parte del nombre capturado en una
petición de incremento. Cancelar una incorporación incompleta no deja una fila.
Las respuestas muestran preguntas sencillas y no una cabecera rutinaria.

La lista privada existente NO se limpia ni consolida automáticamente. «mas arroz»
y duplicados ya guardados se conservan hasta una petición de limpieza separada.
No se añade compra autónoma, conversión de unidades, sumas entre entradas,
autocorrección general de productos, asistente general ni conversación externa.
El proyecto sigue limitado a envases enteros positivos y variantes literales.

## Enfoque y responsabilidades

Separar interpretación, transición de diálogo y presentación:
- Gemma propone una intención tipada. La aplicación contrasta cada intención
  con el mensaje completo; una propuesta `list` ante un saludo se rechaza.
- El controlador decide si hay una propuesta pendiente, selección, cantidad o
  confirmación; no recibe permisos del texto redactado por el modelo.
- SQLite guarda solo mutaciones autorizadas y estado de diálogo; los trabajos
  de presentación siguen el prepare/finalize idempotente actual.
- Gemma compone respuestas a partir del resultado real y del acto conversacional.
  El hecho de llamar al modelo no se presenta como libertad de redacción total.

Alternativas rechazadas: parches de frases sin nuevos estados (seguirían creando
productos incompletos) y modelo autónomo con acceso de escritura (pierde control
de identidad, revisiones, reservas y compras).

## Saludos y límites de interpretación

Reconocer saludos completos y mensajes sociales breves: «hola», «hols», «buenas»,
«buenos días», «hola qué tal», «qué tal». «hols» es una equivalencia social
explícita, no permiso para corregir nombres de productos por semejanza.
Responder de forma breve y amistosa sobre el ámbito del asistente, sin incluir
la lista, productos privados, cantidades ni una operación que no se ha solicitado.
Un saludo no modifica ni renueva el contexto pendiente ni el TTL.

«Hola, necesito arroz» no es un saludo puro: conservar la petición de compras
después de un prefijo social inequívoco. No eliminar palabras internas de un
producto ni reinterpretar «Arroz Hola» como un saludo. Compras y comandos
explícitos mantienen prioridad; saludo + una compra no otorga nueva autorización.

Cada `list`, `add`, `mention_product`, `product_query` y nuevo incremento tiene
verificación específica del texto original. No basta que Gemma entregue JSON
válido. «Dame mi lista» y «qué hay en mi lista» son consultas; «hola qué tal» no.
Una interpretación incompatible pide aclaración, sin modificar la lista.
Esto debe funcionar también si el intérprete propone deliberadamente una acción
incorrecta. No incorporar una lista infinita de sinónimos sin tests.

## Altas pendientes

Una petición inequívoca de producto sin cantidad crea un borrador de diálogo,
no una fila `list_lines`. Se pregunta «¿Cuántos envases de arroz quieres añadir?».
La propuesta conserva descripción completa, unidad, identidad y procedencia del
mensaje; no tiene ID de fila inventado. La lista normal no incluye este borrador.

Al recibir una cantidad válida, crear la entrada y completar estado/inbox/outbox
una sola vez. No hace falta otra confirmación para un producto nuevo solicitado
claramente; para duplicados se conserva la elección explícita previa. La cantidad
preguntada para una nueva entrada no suma a ninguna entrada existente.

Si aparecen duplicados entre preguntar y responder, revalidarlos en la transacción
final y pedir elección antes de guardar. Si cambian candidatos ofrecidos, se pierde
la autorización anterior y se vuelve a preguntar. No elegir por orden o por tener
cantidad pendiente. Diapers mantienen requisito de paquetes/envases explícitos.

«Cancelar» descarta el borrador sin fila que borrar. Caducidad después de 15 minutos
de inactividad lo invalida; «2» después de caducar no crea nada. Reinicio conserva
un borrador vigente. Una petición nueva completa sustituye el borrador anterior;
un saludo o consulta de lista no lo descarta ni renueva. No sumar ni fusionar
propuestas múltiples silenciosamente.

Las altas que ya traen cantidad válida, como «añade 2 arroz», siguen pudiendo
guardarse inmediatamente tras validación/duplicados. `/anadir` sin cantidad también
se vuelve pendiente: mismo criterio de no guardar un producto incompleto, aunque
su respuesta sea determinista. `/anadir` con cantidad conserva el flujo actual.
Las filas antiguas sin cantidad siguen visibles; responder su cantidad puede
actualizarlas cuando la referencia está autorizada, sin convertirlas a borradores.

## Incrementos: «quiero más arroz»

«Quiero más arroz» y «añade más arroz» representan deseo de aumentar un producto,
no un alta literal. El modificador se reconoce solo en la posición/forma de esa
petición, preservando el resto del nombre y sus variantes. No quitar «más» de
marcas, nombres entre comillas o productos que no cumplen esa gramática.

El controlador busca entradas por descripción completa normalizada, conservando
variante, marca y talla. Arroz integral no equivale a arroz. No usa semejanza para
elegir. Con varias coincidencias, pregunta cuál de ellas mostrando sus cantidades.
Con ninguna, explica que no está guardado y ofrece iniciar un alta pendiente
mediante elección explícita; no crea un producto nuevo automáticamente.

Una vez elegido el destino:
1. Preguntar cantidad ADICIONAL de envases, sin escribir.
2. Calcular un total exacto solo si la base es conocida y ambas cantidades están
   dentro del rango SQLite firmado64; no convertir ni redondear piezas/kg/l.
3. Mostrar origen, base, adicional y total: «Tenías 1 envase de arroz. Añadir 2
   dejaría 3. ¿Confirmas?».
4. Solo un sí/confirmación compatible con esa pregunta autoriza la mutación.

Si la base es desconocida, no tratarla como cero: ofrecer establecer una cantidad
TOTAL y continuar el flujo de cantidad total, sin una confirmación aritmética falsa.
Si el destino está reservado, bloquear incremento; no borrar reservas ni tocar
snapshots. En confirmación, revalidar ID, revisión, cantidad base y reserva dentro
de la transacción. Si cambió la base, cancelar el permiso anterior y pedir selección
o propuesta nueva; no recalcular y guardar bajo el sí antiguo.

«Cancelar» antes de confirmar deja la lista idéntica. «No» en confirmación rechaza
el incremento y descarta esa propuesta. Confirmación repetida/replay no vuelve
a sumar. La mutación aplica una cantidad total calculada y revision+1, no SQL
aditivo sin comparación de revisión. La aritmética es de aplicación, no del modelo.

## Redacción: menos ceremonia, más contexto

Eliminar la cabecera genérica por defecto, no simplemente sustituirla por otra
frase que se repita. Saludos reciben un saludo; cancelar recibe una cancelación
breve; una consulta de lista recibe la lista, sin «Aquí tienes el detalle».

El redactor recibe un acto de presentación explícito (saludo, alta pendiente,
selección, incremento pendiente, confirmación, resultado, lista, aclaración).
Solo incluir datos necesarios para ese turno. Evitar «línea», «revisión», UUID y
«no un incremento» como frase recurrente cuando no hay ambigüedad.

Para la captura, las respuestas esperadas serían equivalentes a:
- «¡Hola! ¿En qué te ayudo con tu lista?»
- «Tienes dos entradas de arroz: una con 1 envase y otra con 2. ¿Cuál quieres aumentar?»
- «¿Cuántos envases más quieres añadir a la primera?»
- «Tenías 1; añadir 2 dejaría 3. ¿Confirmas?»
- «Cancelado. No he cambiado tu lista.»

Gemma podrá elegir formulaciones apropiadas al acto, no solo una de cinco
introducciones intercambiables. Los hechos críticos, la aritmética y las opciones
permanecen anclados a la instantánea validada. Ampliar la redacción no significa
permitir prosa factual arbitraria: la gramática verificada será por acto, con
referencias literales y equivalencias autorizadas. El plan fijará el contrato y
las variantes verificables; si no consigue naturalidad útil, se informa al usuario
antes de abrir texto libre o usar otro modelo para validar semántica.

No afirmar una garantía de verdad de texto libre. Nada que escriba el redactor
es ejecutable. Se rechazan números/nombres nuevos, opciones no ofrecidas,
afirmaciones de éxito prematuro y negaciones que inviertan el resultado. Fallback
claro específico al acto, no prosa repetitiva. No ocultar su uso en la evidencia.

La lista natural mantiene entradas separadas y cantidades (incluidas pendientes
antiguas), sin sumarlas. Puede usar viñetas; ordinales solo si hay selección activa.
No mostrar un alta aún pendiente como producto guardado. `/lista` conserva IDs
técnicos necesarios para comandos. El plazo HTTP, recursos, límite de contexto y
prepare/finalize actuales se preservan salvo cambios explícitos en el plan.

## Persistencia y compatibilidad

Nuevos estados distinguen alta pendiente, cantidad de entrada guardada e incremento
pendiente de cantidad/confirmación. Estos roles no dependen de si existe una fila
con quantityNULL. Guardar propuesta de incremento con destino ID/revisión, base y
delta; esos datos no son permisos del modelo ni se exponen como control al redactor.

La migración siguiente (v8) preserva todas las filas existentes, pedidos, reservas,
observaciones, offsets, inbox/outbox y trabajos de presentación. Invalida el contexto
de diálogo anterior, sin borrar productos, porque preguntas antiguas pueden tener
significados distintos; avisar de que tras actualizar hay que repetir la petición.
Un trabajo de presentación v7 ya preparado implica una acción guardada: se recupera
y finaliza con su instantánea compatible, nunca se convierte retroactivamente a
alta pendiente ni se deshace su mutación. Las respuestas completadas siguen idénticas.

Nuevos contratos tipados/versionados rechazan estados incoherentes y propietarios
extraños. Se puede leer la presentación v1 previa y redactar/usar respaldo sin
perder comandos de aplicación. No borrar trabajos antiguos ni cambiar hechos
históricos para hacerlos parecer compatibles con el flujo nuevo.

No HTTP durante transacciones. Preparación de pregunta pendiente puede cambiar
solo estado; el commit final de alta o incremento tiene lista/estado/instantánea
en una transacción, seguida de generación y finalización idempotente como ahora.
Generación/replay/saludo/consulta no renuevan el TTL; solo transiciones válidas de
propuesta/respuesta lo hacen. Recuperación funciona con redactor deshabilitado.

## Pruebas y aceptación

- Reproducir la conversación del usuario con Gemma real para interpretación y
  redacción; no atribuir resultados de un intérprete fake al modelo.
- Saludos y saludo+petición; modelo hostil que propone list ante un saludo.
- «Quiero más arroz» con cero/una/dos coincidencias, variantes distintas,
  base desconocida, cantidades desbordadas, destino reservado o modificado.
- Alta sin cantidad -> lista sin alta -> cancelar -> lista idéntica; alta ->2
  guarda una vez; reinicio/caducidad/cancelación; duplicates aparecidos después.
- Incremento -> cantidad adicional -> no/cancelar, o confirmar -> total exacto;
  replay del sí, revision cambiada y fallo de outbox nunca suman dos veces.
- Preservación v7->v8 y prepared presentation antiguo, propietario/procedencia,
  contratos corruptos, no caída del worker por cantidades enormes.
- Nuevas frases naturales, gramática por acto, datos literales maliciosos,
  provider caído, salida incoherente y respaldo sin mutación falsa.
- Suite completa, Ruff, revisión por tarea y global. Probe real publica input,
  interpretación propuesta, transición guardada, respuesta, accepted/fallback y
  tiempos de ambas llamadas, con expectativas independientes del propio sistema.

El probe usa SQLite nueva con arroz1/arroz2 y arroz integral sin cantidad como
fixture heredada, para reproducir el estado inicial sin leer la DB privada. Un
saludo no debe consultar datos privados para responder. Cero órdenes; sin Telegram
ni tiendas reales, downloads, reinicios, cambios de permisos o unload forzado.

## Entrega y autorización

Implementar en aislamiento respecto al checkout principal, que puede alimentar
el bot actualmente activo. No repetir tareas ya integradas ni tocar su configuración.
La aprobación de esta especificación permite escribir el plan; la del plan y su
método permite implementarlo. Merge/push/PR y actualización del bot son decisiones
separadas. La limpieza de entradas privadas requerirá permiso explícito posterior.
