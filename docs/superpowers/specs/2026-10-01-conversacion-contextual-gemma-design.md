# Conversación contextual segura para lista y fichas

Estado: diseño conversacional aprobado el 01-10-2026; este documento queda
pendiente de revisión y aprobación del usuario antes de preparar el plan.

## 1. Objetivo y criterio de éxito

El usuario quiere conversar con su asistente de compras por Telegram sin repetir
una fórmula exacta en cada mensaje. La conversación observada funciona para
«necesito arroz», una respuesta de cantidad y «añade arroz integral», pero pierde
el hilo con «ahora arroz integral» y «añádelo a mi lista». Las confirmaciones son
genéricas, muestran IDs técnicos y pueden preguntar por otra línea pendiente.

La mejora debe entender continuaciones inequívocas, preguntar cuando haya varias
interpretaciones y confirmar exactamente lo que se guardó. SQLite sigue siendo
la fuente de verdad. Gemma propone interpretaciones, no decide qué modificar.
El éxito incluye reproducir la conversación completa y una sustitución confirmada,
sin duplicaciones accidentales, cambios por referencias caducadas ni órdenes.

Decisiones aprobadas en conversación:

- Producto repetido: preguntar antes de duplicar o cambiar cantidades; no sumar
  ni fusionar automáticamente.
- Incluir sustitución confirmada, además de añadir y ajustar cantidades.
- Contexto breve que caduque, cancelación, respuestas claras sin IDs largos en
  el diálogo habitual y pruebas aisladas antes de tocar el bot privado.

## 2. Alcance y límites

Incluye lista, menciones de productos, referencias al producto de la conversación,
preguntas de cantidad, detección conservadora de duplicados, selección de una línea
y sustitución explícitamente confirmada. Conserva las consultas de fichas y backlog.

No incluye chat general, scraping, navegación, carritos, pagos, nuevo proveedor,
instalaciones, cambios de permisos privados ni alteraciones del checkout. No
autoriza reiniciar el bot privado, cambiar configuración, hacer merge o push.
La nueva memoria nunca sirve para autorizar compras o reanudar órdenes.

No se añade soporte para kilos, litros, fracciones ni conversiones de piezas a
envases: las cantidades siguen siendo enteros positivos de envases. Los formatos
y pesos de un producto no se infieren de una conversación ni se inventan.

## 3. Enfoque elegido

Se elige un controlador de diálogo con estado estructurado acotado, sobre el flujo
duradero existente. No se envía el historial entero a Gemma ni se convierte al
modelo en un agente con herramientas de escritura.

Un cambio solo de prompt no conserva referencias entre mensajes ni demuestra qué
línea debe cambiar. Un historial libre aumenta consumo y permite que mensajes
antiguos parezcan instrucciones actuales. El estado estructurado identifica una
propuesta concreta y las preguntas que el programa todavía necesita resolver.

## 4. Estado de conversación

Persistir como máximo un foco y una pregunta activa por usuario/chat autorizado:

- Producto mencionado, con descripción íntegra y referencia al mensaje fuente.
- Tipo de pregunta: elegir añadir/sustituir, resolver duplicado, seleccionar
  línea, confirmar sustitución, elegir tratamiento de cantidad o dar cantidad.
- Acción propuesta, alternativas ofrecidas y candidatos concretos cuando existan.
- Línea destino con ID y revisión esperada; cantidad anterior cuando sea pertinente.
- Etiqueta de envase explícita o planteada en la pregunta, sin inferir peso/formato.
- Fechas UTC de actualización y caducidad.

No guardar un historial adicional de mensajes ni secretos en este estado. La
referencia al inbox existente permite comprobar el origen de la propuesta. Los
candidatos y IDs los obtiene el programa, nunca una invención del modelo.

El estado caduca a los **15 minutos de inactividad**. Cada respuesta válida al
diálogo renueva el plazo; un replay no lo renueva. Tras caducar, «2», «añádelo» o
«sí» no modifican la lista y el bot pide producto/acción explícitos. Un reinicio
conserva una pregunta vigente, pero nunca revive una pregunta caducada.

Una consulta de lista/ficha no responde automáticamente a una pregunta pendiente.
Si abre un tema distinto, el controlador invalida el foco anterior antes de aceptar
referencias a la nueva mención. Ante conflicto entre dos focos, pregunta en vez de
escoger por recencia. «Cancelar» abandona el diálogo sin deshacer cambios ya
confirmados; explica esa diferencia cuando una línea ya se añadió.

## 5. Flujo y autoridad de las acciones

Orden de procesamiento:

1. Verificar inbox duradero, usuario y deduplicación como hasta ahora.
2. Dar prioridad a comandos explícitos con `/` y a la autorización determinista
   de compras existente, sin consultar al modelo ni usar el foco como permiso.
3. Resolver respuestas cerradas a una pregunta vigente mediante el controlador.
   Reconocer aquí referencias como «añade eso» antes de que un alias español de
   alta pudiera guardar literalmente `eso`; si falta foco, pedir el producto.
   Luego aplicar los aliases deterministas no contextuales existentes.
4. Para el resto del texto libre, enviar a Gemma contexto mínimo de lista, foco,
   pregunta y fichas pertinentes; validar la propuesta contra texto y estado.
5. Persistir cambio, nuevo estado, respuesta y outbox en una sola transacción.

Gemma puede proponer mencionar/añadir/consultar un producto o pedir aclaración.
No puede ordenar una escritura, elegir por sí solo una línea arbitraria, modificar
cantidades, sustituir, quitar, comprar ni continuar pedidos. Las respuestas como
«añádelo», «sustitúyelo», «conserva los 2» o una cantidad solo se ejecutan cuando el
controlador puede vincularlas a una pregunta concreta y vigente.

Se amplía la especificación anterior únicamente para esas respuestas contextuales
validadas: una confirmación del usuario, no un `set_quantity`/`replace` del modelo,
habilita el cambio. Negaciones, citas, condiciones, alternativas y pérdida de
marca/variante siguen sin autorizar mutaciones. No se corrigen automáticamente
erratas en nombres de productos ni se interpretan términos desconocidos como
cortesía prescindible.

Las respuestas cerradas y comandos funcionan aunque Ollama esté detenido. Un
timeout/salida inválida no crea foco ejecutable, backlog ni cambios de lista.

## 6. Altas, duplicados y cantidades

«Necesito arroz» añade una línea si no existe otra equivalente y confirma el
producto, sin cantidad inventada. La siguiente pregunta se ancla a esa línea,
no a la primera línea sin cantidad de toda la lista.

Para duplicados, comparar descripción completa normalizada (acentos, mayúsculas
y espacios), sin quitar calificadores, tamaños, marcas o etapas. No equiparar
«arroz» y «arroz integral», «pienso» y «pienso de pollo», o tallas diferentes. Un
mismo `product_id` no basta si se han conservado descripciones distintas.

Si ya existe arroz:

> Ya tienes arroz: 1 envase. ¿Quieres cambiar su cantidad o añadir otra línea?

«Cambiar cantidad» abre una pregunta por el nuevo **total**, no un incremento.
«Añadir otra línea» autoriza duplicar explícitamente la propuesta. Una intención
ambigua o un «sí» ante varias alternativas no elige ninguna. Duplicados antiguos
no se fusionan: si hay varias líneas candidatas, el usuario selecciona una mediante
opciones cortas generadas por el bot.

Esta protección se aplica también a `/anadir` cuando detecta una repetición. La
sintaxis y prioridad de los comandos se conservan; esta confirmación ante duplicados
es el cambio deliberado de comportamiento. `/cantidad <id> <n>` sigue fijando un
total explícito, sin pasar por el modelo.

Una cantidad responde solo al producto preguntado. La respuesta confirma nombre,
nuevo total y etiqueta de envase sustentada en esa pregunta/respuesta. No asumir
que un número significa piezas de pañal: para pañales sigue siendo obligatorio
escribir paquetes/envases explícitos, incluso si hay contexto («2 paquetes»).

## 7. Menciones, referencias y sustitución

Una mención identificable como «ahora arroz integral» crea una propuesta, no una
mutación. Si hay un producto anterior relevante, preguntar:

> ¿Quieres añadir arroz integral o sustituir el arroz del que hablábamos?

«Añádelo a mi lista» se refiere a esa propuesta y sigue el flujo de alta/duplicado.
No se guarda como producto la frase completa «añádelo a mi lista».

Para sustituir, confirmar origen y destino con una pregunta concreta:

> ¿Confirmas sustituir arroz por arroz integral?

Solo una confirmación inequívoca responde a esa pregunta. Si el origen tiene
cantidad, preguntar después si conservarla o indicar otra; no copiarla por defecto.
Una cantidad completa explícita en la propia petición puede resolver ese paso,
pero no elimina la confirmación de origen/destino. Si falta, preguntar por una
cantidad antes de ejecutar; no eliminar el origen durante una propuesta incompleta.

Antes de sustituir, comprobar también si el destino generaría una repetición. En
ese caso explicar el conflicto y pedir confirmación para mantener líneas separadas;
no sumar ni fusionar cantidades automáticamente.

La sustitución se ejecuta atómicamente sobre la línea confirmada: conserva su ID,
incrementa revisión y recalcula `product_id` con las restricciones existentes. Una
referencia no permitida permanece sin resolver; nunca se cambia por otra permitida.
Si la línea desapareció, cambió de revisión o está reservada por una orden, no
sustituir: invalidar la propuesta y explicar que hace falta revisar la lista.
Las instantáneas de pedidos previos no se modifican.

## 8. Respuestas y presentación

Respuestas deterministas basadas en el resultado transaccional, no en texto libre
del modelo. Ejemplos:

- «He añadido arroz integral. ¿Cuántos paquetes/envases quieres?»
- «Arroz integral: 2 paquetes» si la etiqueta está establecida explícitamente.
- «Arroz: 2 envases» cuando no haya una etiqueta más concreta sustentada.
- «He sustituido arroz por arroz integral: 2 envases» tras confirmación y cantidad.
- «No he cambiado la lista. ¿Quieres añadirlo o sustituir el arroz?»

No mostrar UUID en altas/preguntas/confirmaciones normales. Para seleccionar entre
varias líneas usar opciones numeradas vinculadas al estado, no índices reutilizados
tras cambiar la lista. La consulta natural de lista utiliza descripciones y
cantidades; `/lista` conserva IDs como vía técnica para comandos explícitos.

Una aclaración sobre lista no sugiere `/comprar`. La ayuda de comandos técnicos
puede conservar su referencia a comandos existentes, pero no presentarla como
solución a una pregunta conversacional no entendida. Las fichas siguen siendo
históricas, con fechas y ausencia explícita de atributos no observados.

## 9. Persistencia, compatibilidad y seguridad

- Añadir una migración idempotente para el estado de diálogo; lista, pedidos,
  offset, bot y propietario existentes no se sustituyen ni se reinicializan.
- Migrar una aclaración antigua solo si identifica una línea vigente y una
  acción compatible; no convertir candidatos de quitar en permisos contextuales.
  Si no hay fecha fiable, descartar la aclaración sin modificar datos de lista y
  pedir una nueva pregunta, en lugar de concederle vida indefinida.
- Se comprueban ID/revisión/candidatos dentro de la transacción de aplicación.
  Un rollback del outbox revierte también estado y cambios de lista.
- Replay del mismo update devuelve la respuesta original y no duplica altas,
  confirmaciones, backlog, revisiones ni renovaciones del plazo.
- El nuevo estado se limita al usuario/chat autorizado. El modelo no recibe
  dirección, credenciales, historial completo ni herramientas de SQL/red/tiendas.
- Ollama permanece en loopback, sin proxy/redirecciones/fallback externo y con
  timeout finito. No registrar cuerpos privados ni respuestas del modelo en logs.
- El contexto no sirve de autorización para `buy`, `resume` o pagos. La ruta
  determinista de compras existente y sus restricciones permanecen sin ampliar.

## 10. Verificación y aceptación

Pruebas TDD mínimas, usando Repository/Conversation reales y dobles solo para
transporte/modelo externos:

1. Conversación de la captura: alta arroz → cantidad 2 → mención arroz integral
   → «añádelo a mi lista» → cantidad; nombres/objetivo correctos y cero órdenes.
2. Cortesía al final, variantes conservadas y una mención que no autoriza alta.
3. Pregunta de cantidad sobre la línea recién añadida con otras pendientes previas.
4. Repetición de arroz: sin cambio hasta elegir modificar total o duplicar; suma
   automática prohibida; mismas reglas para `/anadir` y duplicados preexistentes.
5. Sustitución: sin cambio antes de confirmar; elección explícita de cantidad;
   mismo ID/revisión incrementada; destino repetido, origen reservado/desaparecido
   o modificado, y calificaciones restringidas que no pueden perderse.
6. Pronombre con uno/varios candidatos, «sí» ambiguo, cancelación, cambio de tema,
   caducidad con reloj controlado y reinicio con contexto vigente/caducado.
7. Replay y rollback inyectado: no duplicar ni dejar estado/lista/outbox inconsistentes.
8. Modelo que inventa IDs, propone sustituciones/cantidades/compras, borra variantes,
   falla o intenta usar texto de ficha como instrucciones: ninguna mutación indebida.
9. Etiquetas y cantidades: enteros positivos de envases; no pesos/fracciones ni
   piezas de pañales; ausencia de UUID y confirmaciones con el resultado guardado.
10. Migración de datos previos, comandos, offset/autorización y consultas/backlog
    siguen conservados; suite completa y Ruff en el árbol final.

Después, probar varias secuencias representativas con Ollama real y SQLite
temporal, incluyendo mensajes encadenados, ambigüedades y fallos del modelo.
Registrar latencias y aciertos/fallos sin prometer fiabilidad por una muestra corta.
No descargar otro modelo ni reiniciar servicios ajenos para forzar una carga fría.

La aceptación en el bot privado se realiza únicamente con autorización específica,
worker detenido/reiniciado por el usuario y una sola instancia. No usar `/comprar`,
ni abrir tiendas. Este documento no es permiso para modificar esa sesión.

## 11. Condición para preparar implementación

El usuario debe revisar y aprobar este documento. Después se prepara un plan con
tareas de contratos/estado, migración/transacciones, controlador, contexto Ollama,
respuestas, regresiones y prueba aislada. El plan se revisa y el usuario elige cómo
ejecutarlo antes de empezar a modificar código del producto.
