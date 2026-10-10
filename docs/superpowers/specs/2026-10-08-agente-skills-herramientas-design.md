# Agente de compras con skills y herramientas

Fecha: 2026-10-08. Estado: especificación escrita aprobada por el usuario;
adaptación de ejemplos externos aprobada posteriormente. Autoriza preparar el
plan, no todavía implementación, activación,
reinicio, publicación ni cambios en datos privados. Base: `feat/shop-assistant`,
commit `28af475`.

## 1. Intención y decisiones aprobadas

El usuario quiere hablar normalmente con un agente, no aprender un catálogo de
frases. Gemma debe interpretar consultas y peticiones de uno o varios productos;
unas skills breves explican cómo utilizar herramientas concretas. La aplicación
conserva la autoridad sobre persistencia, identidad y confirmaciones.

Decisiones aprobadas en conversación:
- Un agente local `gemma4:e4b-it-q4_K_M`, con skills precargadas y herramientas
  nativas. El modelo está descargado, pero no se ha activado en el bot.
- Todo cambio de la lista originado por el agente requiere una propuesta visible
  y confirmación explícita, incluidas altas nuevas y cantidades pendientes.
- Resultados operativos, selecciones, cantidades y resúmenes proceden directamente
  de la aplicación; el texto del agente no puede sustituirlos por éxito inventado.
- Compras, comandos explícitos y datos históricos mantienen sus protecciones.

Esto sustituye dos decisiones del diseño anterior: la gramática cerrada deja de
autorizar interpretaciones naturales y las altas naturales completas dejan de
guardarse inmediatamente. No sustituye las garantías de transacción y recuperación.

## 2. Evidencia y elección de arquitectura

Prueba desechable con Ollama local, herramientas simuladas y 16 casos por variante,
usando las mismas instrucciones, parámetros y expectativas:

| Variante | E2B | E4B |
| --- | ---: | ---: |
| Herramientas nativas, skill precargada | 10/16 | 15/16 |
| Decisión JSON y respuesta separada | 7/16 | 10/16 |
| Skill cargada por iniciativa del modelo | 5/16 | 8/16 |

Son resultados de acciones, argumentos y estado simulado, no de calidad global.
E4B nativo interpretó «qué lista tengo», arroz y carne, cantidades múltiples e
incrementos. Falló una condición y algunos textos afirmaron altas aún pendientes;
en un incremento omitió la selección de fila en su respuesta. La variante JSON
también inventó cantidades durante un saludo. No se conserva ese prototipo.

Se elige agente único con herramientas nativas y pocas skills precargadas. Se
rechazan más sinónimos programados, un framework multiagente, carga dinámica de
skills como requisito y SQL/terminal arbitrarios. Un modelo mayor no demuestra
por sí solo seguridad ni elimina errores de interpretación.

El equipo ejecutó la prueba E4B con contexto de 8192 tokens. La primera llamada
tardó unos 65 segundos e incluyó la carga del modelo; no se promete latencia estable. No aumentar
contexto, descargar más modelos ni modificar procesos para compensar resultados.

## 3. Componentes mínimos

**Skills locales versionadas:** cuatro guías cortas, cargadas por la aplicación
al preparar el contexto del agente: consultar; altas y cantidades; cambios e
incrementos; resolver o cancelar propuestas. Explican procedimientos y ejemplos,
no enumeran frases admitidas. Son instrucciones de la aplicación, no documentos
aportados por el usuario. No se cargan skills desde URLs o rutas elegidas por Gemma.

Reutilización aprobada: adaptar ejemplos de varios productos y aclaración de
`ajeenkya/shopping-list-skill`, licencia MIT, revisión
`e37617947cd8e8aa095c5a358c9005bb2ac1c6fd`. Incluir atribución y licencia de los
fragmentos adaptados. Escribir los procedimientos propios para nuestras herramientas
y confirmaciones; no precargar la skill original completa. Excluir escritura de
JSON por el agente, fusión automática, cantidades ausentes guardadas y archivo
automático. No instalar OpenClaw, AnyList, Trello ni sus CLIs. No se ha demostrado
compatibilidad con Gemma de los ejemplos adaptados hasta probarlos en el producto.

**Agente:** interpreta el mensaje original y el contexto conversacional acotado,
elige herramientas y propone argumentos. No concede permisos, confirma cambios,
ejecuta pagos ni redacta el resultado operativo definitivo.

**Herramientas:** funciones pequeñas con argumentos tipados y validación estricta.
Reutilizan el repositorio y las reglas actuales, sin copiar SQL en las skills.
El usuario/chat procede del inbox, nunca de argumentos de Gemma. Las referencias
de fila o propuesta deben existir en el contexto autorizado; no se aceptan IDs,
permisos o versiones inventados. Nombres y observaciones son datos no fiables,
no instrucciones nuevas. Se rechazan funciones y campos ajenos al contrato.
Catálogo funcional para esta versión:

| Herramienta | Función |
| --- | --- |
| `consultar_lista` | Leer entradas guardadas; distinguir pendientes si se muestran |
| `consultar_ficha` | Consultar observaciones de productos, sin afirmar stock actual |
| `consultar_propuesta` | Leer la propuesta vigente y lo que falta |
| `proponer_altas` | Preparar uno o varios productos, con cantidad ausente como pendiente |
| `completar_propuesta` | Incorporar cantidades o resolver selecciones, sin guardar entradas |
| `proponer_cambio` | Preparar incremento, cantidad total o sustitución de una entrada |
| `cancelar_propuesta` | Descartar pendientes, nunca borrar entradas guardadas |

No existe herramienta de confirmar, comprar, borrar filas, ejecutar SQL ni cambiar
configuración. La confirmación es una transición propia de la aplicación.

**Aplicación:** guarda borradores y resultados duraderos, presenta preguntas y
resúmenes, verifica la respuesta explícita y aplica el cambio de forma atómica.

## 4. Flujo, contexto y confirmación

1. Recuperar primero un resultado o trabajo ya preparado para el mismo mensaje.
   Nunca reinterpretar una operación comprometida antes de un fallo o reinicio.
2. Dar prioridad a comandos explícitos y a respuestas cerradas de control en un
   contexto válido: selección, confirmación, rechazo y cancelación.
3. Para el resto, enviar el texto original a Gemma con skills, herramientas y el
   mínimo contexto necesario. No convertir primero la petición a una intención
   decidida por expresiones regulares ni condicionar el esquema a la frase.
4. Validar y ejecutar las herramientas permitidas. Preparar o completar un
   borrador no cambia `list_lines`. Preguntar por datos o decisiones ausentes.
5. Cuando la propuesta esté completa, mostrar un resumen calculado por la
   aplicación, con la petición original y la pregunta explícita de confirmación.
6. Un «sí» o «confirmar» inequívoco se vincula exclusivamente a ese resumen vigente.
   La aplicación verifica sus condiciones y guarda; Gemma no interviene en el commit.

Cada propuesta pertenece a un usuario/chat, tiene versión, procedencia y estado
incompleto o listo para revisión. La versión incluye todos sus productos, datos,
selecciones y cambios. No se confirma mientras falten cantidad o selección.
Cualquier edición invalida el resumen anterior; se emite otro antes de confirmar.
No basta que el modelo devuelva un indicador `confirmed` ni cite un ID válido.

Mantener la caducidad de 15 minutos y la persistencia tras reinicio. Consultar o
saludar no cancela, modifica ni renueva el permiso pendiente. Un sí fuera de
contexto, ambiguo, caducado o perteneciente a otra propuesta no guarda nada.
Los turnos de herramientas tienen un límite finito y admiten como máximo una
operación de preparación/completado/cancelación de propuesta por mensaje; las
lecturas necesarias pueden precederla. Agotar el límite no aplica cambios de lista.

## 5. Productos, condiciones y guardado

- Separar todos los productos solicitados del contexto «para la semana»; conservar
  nombres, marcas y variantes. Cantidades ausentes permanecen ausentes. No estimar
  unidades ni interpretar talla, etapa o gramos como número de envases.
- Mantener envases enteros positivos, límites SQLite y requisitos actuales de
  pañales. No añadir conversión de kilos, precios, ofertas o unidades fraccionarias.
- Resolver respuestas por producto o por posición ofrecida; si son ambiguas,
  preguntar. No asignar cantidades a varios productos por conjetura.
- Los duplicados se muestran como decisiones explícitas, sin sumar ni fusionar.
  El resumen debe decir si crea otra entrada o cambia una existente.
- Un incremento requiere fila inequívoca y muestra base + adicional = total.
  Varias coincidencias exigen selección. Una base desconocida no se trata como cero;
  se ofrece proponer un total explícito. Sustituciones conservan su revisión de origen.
- Una petición negada no prepara un alta. Una condición no comprobada exige
  aclaración; no hay herramienta para verificar ofertas. Una condición señalada
  permanece bloqueada hasta que se resuelva o se retire expresamente. La confirmación
  de un resumen no convierte una condición pendiente en un hecho demostrado.

La interpretación semántica puede fallar, como mostró la prueba. La confirmación
obligatoria y la petición original visible evitan cambios silenciosos, pero no
demuestran que todas las condiciones hayan sido detectadas. No sustituir esa
limitación por una afirmación de seguridad absoluta ni reconstruir un parser de frases.

Al confirmar, revalidar usuario/chat, versión, cantidades completas, filas actuales,
revisiones, reservas y decisiones de duplicado. Si algo cambia, no aplicar nada y
presentar la revisión requerida. Un lote se guarda completo en una transacción o
no se guarda; nunca aplicar parcialmente una propuesta fallida.

Los mismos `update_id` y confirmación no repiten altas ni sumas. Estado, mutaciones,
resultado e inbox/outbox deben comprometerse conjuntamente. Ninguna llamada a
Ollama ni espera de red ocurre dentro de la transacción SQLite.

## 6. Respuestas y fallos

Después de una herramienta, la aplicación construye el resultado operativo y lo
envía directamente; se descartan afirmaciones libres de Gemma que lo sustituyan.
No usar otra llamada de redacción para decidir si algo quedó guardado.

Los borradores dicen «pendiente, sin guardar». Las preguntas incluyen todos los
datos o selecciones necesarios. El resumen incluye todas las operaciones, variantes,
cantidades y aritmética relevantes. Solo un commit confirmado genera «guardado».
No repetir una cabecera genérica ni mostrar una propuesta como parte de la lista.

Gemma puede mantener conversación social breve, pero sin afirmar cambios, pedidos
o datos privados no consultados. El canal social no sustituye preguntas ni resultados
operativos. Los saludos completos conocidos conservan su ruta sin lectura de filas;
no expandir ese atajo hasta volver a clasificar todas las peticiones con una gramática.

Una herramienta desconocida, argumentos inválidos, JSON malformado, timeout o fallo
del modelo no modifica la lista ni concede permisos. Mostrar una aclaración o fallo
honesto. Si ya se preparó un borrador válido, recuperar su estado real; no afirmar
que desapareció por un error de red. Con el agente indisponible siguen utilizables
los comandos, sin reenviar texto natural al parser antiguo como fallback oculto.

## 7. Compatibilidad y alcance de integración

Conservar base de datos, listas históricas, fichas, pedidos, reservas, offsets,
inbox/outbox y trabajos de presentación v1/v2. Los trabajos antiguos se finalizan
según su acción ya comprometida, sin convertirlos retroactivamente en propuestas.

Una transición al nuevo formato puede invalidar solo contexto conversacional
incompatible, con aviso de volver a formular; no limpia productos ni otros registros.
La activación del agente no debe dejar coexistir dos propuestas incompatibles con
permiso de confirmar para un mismo usuario/chat.

Los comandos con barra conservan sus reglas y respuestas. Una continuación de
un comando pendiente se trata según su origen determinista, no como permiso creado
por Gemma. Alias naturales como «añade 2 arroz» pasan por el agente y requieren
confirmación. Compras y continuación de pedidos mantienen exclusivamente las
rutas explícitas actuales; no entran en su catálogo de herramientas.

Configurar el agente de forma opt-in y conservar la vía anterior para rollback.
Desactivar el agente no autoriza propuestas pendientes ni reaplica acciones.
No activar, reiniciar, cambiar el modelo del bot, acceder a datos privados o
publicar como consecuencia de aprobar este documento.

Implementar posteriormente en un worktree nuevo desde la rama integrada, sin
reutilizar prototipos como código de producto ni modificar el código en ejecución.
No introducir frameworks de agentes, vector DB, multiagentes, descarga dinámica
de skills ni una segunda capa de interpretación de lenguaje natural.

## 8. Aceptación

Pruebas con repositorio temporal y llamadas reales a E4B, sin parser o intérprete
falso en los casos que se anuncien como interpretación real. Separar resultados
de interpretación, herramientas, estado, texto operativo y latencia.

Casos obligatorios:
1. Saludos y «qué lista tengo», incluida consulta durante una propuesta pendiente.
2. «Necesito arroz y carne para la compra de la semana»: dos productos, cantidades
   pendientes y ninguna fila nueva. Completar cantidades produce resumen, no commit;
   solo la confirmación guarda ambas entradas, o pide resolver duplicados.
3. Frases nuevas para consultas y varios productos con cantidades explícitas.
4. Negaciones y condiciones: ninguna escritura; aclaración antes de revisión.
5. Incrementos con selección, base desconocida, cancelación y confirmación aritmética.
6. Cambio de propuesta después del resumen: el permiso anterior queda invalidado.
7. Confirmación caducada, fila cambiada, reservada o eliminada: no aplicar el lote.
8. Reinicio, fallo de envío y replay: estado duradero y ninguna operación duplicada.
9. Propuestas/modelo maliciosos: sin SQL, compras, confirmación autónoma ni permisos
   de otro usuario; error real sin mensajes falsos de éxito.
10. Recuperación de trabajos v1/v2 y comandos con agente desactivado.

No entregar basándose en «15/16» de acciones mientras existan resultados operativos
incorrectos o guardados sin confirmación. La aceptación Telegram y la activación
real se autorizan después y no se sustituyen por pruebas simuladas.

## 9. Siguiente puerta de aprobación

Especificación revisada y aprobada en conversación; reutilización híbrida aprobada
con «ok lets do it». Se prepara el plan de implementación para revisión y elección
del método de ejecución. Todavía no hay tareas de producto ejecutadas para este diseño.
