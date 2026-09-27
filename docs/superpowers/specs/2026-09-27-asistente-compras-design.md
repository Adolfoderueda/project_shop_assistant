# Asistente doméstico de compras por Telegram

Estado: documento aprobado por el usuario el 27 de septiembre de 2026.

## 1. Objetivo y alcance

Un único usuario podrá comunicarse por Telegram con un servicio alojado en su ordenador Windows para anotar necesidades del hogar y ordenar compras online. El servicio conservará las instrucciones y gestionará los pedidos hasta obtener confirmación de la tienda o solicitar intervención ante un paso que no pueda completar.

La compra familiar incluye alimentación, limpieza e higiene para tres integrantes. También se gestionarán fórmula infantil, pañales y pienso. La zona de entrega es 28023, Madrid. La dirección completa ya facilitada se configurará como dato privado local, no se reproduce en esta documentación.

La primera versión incluye texto, enlaces, lista editable, búsqueda de ofertas, ejecución de pedidos bajo petición y comunicación del resultado. No incluye ventas de artículos: aunque se mencionaron al presentar la idea, no se ha definido ningún flujo de venta. Recordatorios proactivos, cálculo de consumo y reposición automática pertenecen a una fase posterior.

El usuario ha solicitado dejar presupuesto, cantidades habituales y frecuencia para después de montar el flujo. No se inventarán límites ni cantidades predeterminadas. El servicio admitirá cantidades por orden; si son imprescindibles y faltan, las solicitará. Esa decisión no impide construir y verificar el circuito sin pagos.

## 2. Arquitectura aprobada

Un servicio local coordinará cinco componentes con responsabilidades separadas:

1. **Telegram:** recepción de mensajes, identificación del usuario, respuestas y avisos.
2. **Persistencia:** lista, restricciones, órdenes, intentos de ejecución y eventos duraderos.
3. **Coordinador:** interpretación de peticiones, preguntas de aclaración y transiciones de estado.
4. **Conexiones con tiendas:** búsqueda, validación de producto, gestión de carrito, compra y consulta de pedidos mediante navegador local o una interfaz disponible y verificada.
5. **Seguimiento:** confirmación del resultado y envío de avisos por Telegram.

Se recomienda trabajar con un conjunto reducido de tiendas verificadas frente a un navegador que intente comprar en cualquier comercio. Se pretende usar Mercadona para la compra familiar y seleccionar comercios compatibles para los productos restringidos. Todavía no se ha demostrado la automatización de compra de ninguna tienda; la investigación de precios no constituye esa prueba.

La implementación concretará lenguaje, bibliotecas, proveedor del modelo y mecanismo de inicio en Windows. Se priorizará una aplicación local sencilla y almacenamiento transaccional, sin introducir servicios distribuidos innecesarios. El bot utilizará recepción saliente de mensajes, sin requerir publicar un puerto del ordenador en Internet.

## 3. Identidad de los productos

Las restricciones se comprobarán mediante reglas explícitas antes de añadir al carrito y antes de finalizar el pedido; no dependerán únicamente de la interpretación de un modelo.

| Categoría | Restricción |
| --- | --- |
| Fórmula | Blemil tipo 1 Evolution, sin sustituciones de marca, gama ni etapa. La búsqueda encontró Blemil 1 Optimum Evolution de 800 g; falta cotejar la referencia comercial exacta con el envase o enlace del usuario antes de habilitar la compra de fórmula. |
| Pienso | Producto del enlace proporcionado: Alpha Spirit Wild Fish / Only Fish, 12 kg, código presente en la URL 8436586310295. La ficha lo describe como seco de pescado y prevalece sobre la descripción inicial de salmón semihúmedo. Sin sustituciones. Cotejar identificador y formato en cada tienda. |
| Pañales | Exclusivamente Dodot talla 3. Se permite elegir gama y formato buscando menor coste por pañal para la cantidad solicitada. |

Referencia de pienso confirmada por el usuario:
https://www.amascotados.com/alpha-spirit/2883-alpha-spirit-seco-only-fish-12-kg-8436586310295.html

Cuando no haya coincidencia exacta o disponibilidad, se avisará al usuario. No se reemplazará un producto restringido por una alternativa. Para productos generales ambiguos se solicitará aclaración en lugar de dar por aceptada una marca o formato.

## 4. Flujo de conversación y compra

1. Vincular el bot a un único usuario autorizado de Telegram. Los mensajes de otros usuarios no podrán consultar ni modificar información ni emitir órdenes.
2. Recibir texto o enlaces y registrar el identificador del mensaje para evitar procesarlo dos veces.
3. Interpretar acciones: añadir, quitar, modificar, consultar lista o comprar. Un enlace identifica un producto; por sí solo no autoriza una compra.
4. Guardar cada modificación antes de confirmarla por Telegram.
5. Ante una orden explícita de compra, crear una instantánea de las líneas y cantidades seleccionadas. Las ediciones posteriores de la lista no modificarán silenciosamente el pedido en curso.
6. Solicitar únicamente los datos imprescindibles que falten y buscar ofertas coincidentes en tiendas compatibles.
7. Comparar coste de producto, gastos de envío, disponibilidad y condiciones de descuentos. Distinguir ofertas generales de promociones condicionadas a primer pedido o suscripción. No contratar suscripciones ni aumentar cantidades para obtener portes gratuitos sin una instrucción que lo permita.
8. Preparar los carritos y validar de nuevo producto, cantidad y total vigente. Registrar el intento antes de enviar la acción final de compra.
9. Completar la compra cuando la tienda lo permita. Si requiere autenticación, verificación bancaria o intervención humana, conservar el estado y avisar por Telegram para continuar en el navegador local.
10. Confirmar el resultado con el número de pedido o evidencia de su creación en la tienda. Enviar tienda, importe y entrega prevista cuando se disponga de esos datos.
11. Marcar como compradas solamente las líneas efectivamente confirmadas. Un fallo en otra tienda no deshará ni repetirá pedidos ya completados.

El diseño no establece una aprobación adicional de presupuesto ni un importe máximo. Esas preferencias siguen aplazadas por petición del usuario. Las comprobaciones de identidad, integridad del pedido y resultado son parte del funcionamiento de la compra.

## 5. Datos y estados

Entidades mínimas:

- Usuario autorizado y configuración privada de entrega.
- Producto y restricciones de marca, variedad, etapa, talla, formato e identificadores conocidos.
- Línea de lista, cantidad si se ha indicado y mensaje de origen.
- Orden de compra con instantánea de líneas e identificador único.
- Subpedido por tienda, ofertas utilizadas, total y referencia externa.
- Intento de ejecución, evidencia del resultado y registro de eventos.
- Aviso pendiente de enviar por Telegram.

Estados orientativos de cada subpedido:

`pendiente_datos → buscando → preparado → enviando → confirmado`

Estados alternativos: `requiere_intervencion`, `resultado_incierto`, `fallido`, `cancelado`.

Cada transición se guarda de forma duradera. Una orden global puede quedar parcialmente completada. El usuario podrá consultar qué se compró y qué falta.

## 6. Errores, reintentos y reinicios

- Evitar ejecuciones simultáneas sobre el mismo subpedido o sesión de tienda.
- Los mensajes repetidos de Telegram no deben duplicar modificaciones ni crear una segunda orden.
- Reintentar fallos de lectura o notificaciones con límites; no repetir ciegamente la acción final de compra.
- Si se pierde la respuesta tras enviar el pedido, marcar resultado incierto y consultar el historial de la tienda. Si no se puede determinar qué ocurrió, pedir intervención antes de un nuevo intento.
- Al arrancar Windows, recuperar órdenes y avisos pendientes. Los pedidos que estaban enviándose se reconciliarán antes de continuar.
- Si cambia una web, un producto deja de coincidir o se invalida la sesión, detener ese subpedido con una explicación concreta.
- El inicio automático y la recuperación de órdenes no equivalen a disponibilidad durante suspensión, apagado o pérdida de Internet. La instalación comprobará esas condiciones y el acceso al navegador en la sesión de Windows elegida.

## 7. Sesiones y configuración local

El token de Telegram, la configuración del modelo y las sesiones de tienda se guardarán fuera del código y de los registros. La dirección completa tendrá el mismo tratamiento privado. El navegador usará un perfil dedicado al asistente para no interferir con la navegación habitual.

Los accesos iniciales a tiendas y los pasos bancarios se realizarán mediante sus interfaces originales. No se solicitarán contraseñas, números de tarjeta ni códigos bancarios a través de mensajes del bot. Se aprovecharán métodos de pago guardados en la tienda cuando estén disponibles.

El proveedor del modelo, si se emplea, se configurará durante la instalación. La aplicación enviará únicamente el contexto necesario para interpretar la petición; las credenciales no formarán parte de ese contexto. Los textos de páginas y fichas de producto se tratarán como datos, nunca como instrucciones que puedan cambiar el pedido.

## 8. Contrato de las conexiones con tiendas

Cada conexión deberá poder declarar qué capacidades tiene realmente implementadas:

- Buscar ofertas y devolver identidad, formato, disponibilidad, precio y condiciones.
- Calcular o consultar envío al destino configurado.
- Preparar y revisar el carrito.
- Enviar una compra e indicar si requiere intervención.
- Consultar el resultado e historial para reconciliar intentos inciertos.

Una conexión que únicamente encuentre precios o prepare un carrito no se presentará como capaz de comprar. Si Mercadona o una tienda bloquean la ejecución, se documentará la limitación concreta; no se sustituirá silenciosamente el objetivo de compra completa por una lista de enlaces.

## 9. Verificación y criterios de aceptación

La implementación deberá demostrar:

1. Un usuario autorizado puede añadir, consultar, modificar y quitar productos por Telegram.
2. Lista y órdenes sobreviven a un reinicio.
3. Un usuario distinto no puede usar el asistente.
4. La fórmula, el pienso y los pañales incorrectos se rechazan aunque sean más baratos.
5. La comparación incorpora portes y no presenta descuentos condicionados como universales.
6. El circuito completo se ejecuta en modo de prueba sin efectuar pagos y sin confundir resultados simulados con pedidos reales.
7. Mensajes duplicados, reinicios durante envío y respuestas perdidas no causan reenvíos ciegos de compras.
8. Se distingue el éxito parcial por tiendas y se informa de intervenciones necesarias.
9. Las conexiones reales se comprueban por separado hasta el punto de compra disponible. Una prueba de pago real requiere una orden concreta del usuario con productos y cantidades; la aprobación de este diseño no constituye esa orden.
10. El arranque automático en Windows recupera el servicio y sus avisos pendientes.

No se afirmará que una tienda permite compra autónoma hasta haberlo verificado. La entrega del proyecto debe identificar claramente conexiones probadas, capacidades disponibles y cualquier limitación pendiente.

## 10. Siguiente paso

El usuario revisa este documento. Tras su aprobación se redactará un plan de implementación con decisiones técnicas, configuración necesaria y comprobaciones por componente. Después se seleccionará el método de ejecución del plan. No se ha iniciado implementación ni se han realizado compras.
