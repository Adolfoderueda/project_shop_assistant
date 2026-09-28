# Capacidades observadas de las tiendas

Inspección: **2026-09-27**, Chromium local visible, primero en sesiones públicas
anónimas y después con `BrowserManager` y perfiles dedicados. Repetición pública
integrada de solo lectura y comprobación offline: **2026-09-28**. No credenciales,
altas de cuenta, dirección personal, pagos ni pedidos.

**Ninguna tienda tiene compra autónoma verificada.** Los cuatro adaptadores exponen
`search=True`, `quote=True` (cotización parcial), y `prepare=False`, `submit=False`,
`reconcile=False`, `live_verified=False`. Preparar exige intervención; submit no actúa;
reconciliar devuelve `unknown`. La ausencia de pedidos o de botones no prueba nada.

| Tienda | Producto / descubrimiento público | Cotización completa | Preparar / pagar | Historial |
|---|---|---|---|---|
| Amascotados | probada_sin_pago: producto y búsqueda pública | bloqueada: envío/destino y descuentos del carrito sin verificar | bloqueada: datos personales ausentes; regalo automático ajeno | bloqueada: muestra acceso |
| Charro | probada_sin_pago: referencia configurable; búsqueda general no resuelta | bloqueada: gastos contradictorios entre política y carrito sin dirección | bloqueada: datos personales / acceso | bloqueada: muestra acceso |
| Nappy | probada_sin_pago: listado y fichas de distintos formatos | bloqueada: envío según peso/destino; carrito no preparado | bloqueada: clic público de añadir no produjo línea en carrito | bloqueada: muestra acceso |
| Mercadona | probada_sin_pago: CP 28023, búsqueda Dodot y ficha talla 3 | bloqueada: falta dirección/entrega de usuario | no_comprobada: sin sesión; acceso público inspeccionado | no_comprobada: sin sesión |

No hay ninguna operación `probada_con_pedido_real`. La extracción de producto no
equivale a extracción de identidad del carrito ni del destino. El código no construye
un `PreparedCart` copiando la dirección solicitada.

## Amascotados

- Producto: <https://www.amascotados.com/alpha-spirit/2883-alpha-spirit-seco-only-fish-12-kg-8436586310295.html>.
- Búsqueda GET observada: <https://www.amascotados.com/buscar?controller=search&s=Alpha+Spirit>.
- Contenido `.cn_product_visited`: **Alpha Spirit Wild Fish 12 Kg**, marca Alpha
  Spirit, `unit_price=63.99`, `availability=instock`: 6399 céntimos, 12000 g.
- El código 8436586310295 está en la URL, no en un campo GTIN independiente de la
  captura. El adaptador devuelve `gtin=None`; las restricciones actuales rechazan
  esa oferta para compra. No se ha debilitado el catálogo.
- <https://www.amascotados.com/content/entrega>: transporte según peso, preparación
  generalmente dentro de 48 horas tras pago; no importe completo verificable.
- <https://www.amascotados.com/carrito> y <https://www.amascotados.com/pedido>:
  carrito vacío inicialmente. **Un solo clic de añadir el pienso añadió también
  Moments By Bocados Salmón 60 Gr**, con «Regalo Snack» -1,55 € y «Descuento
  Bienvenida Alpha Spirit» -5 €. Total mostrado 58,99 €, transporte Gratis, sin
  dirección verificada. No se adoptan esos descuentos ni el regalo como autorizados.
- `/pedido` mostró correo, dirección, teléfono y términos sin completar. No se
  pulsó «Realizar pedido». `/mi-cuenta` y `/historial-compra` mostraron acceso.

## Charro desde Casa

- <https://www.charrodesdecasa.com/leches/20209-blemil-optimum-evolution-1-800-gr-8426594127534.html>.
- `#product-details[data-product]`: **Blemil Optimum Evolution 1 800 gr**,
  precio 25.15, cantidad pública 2064, referencia interna 210234. Se extraen
  etapa 1 y 800 g del contenido, no de la regla solicitada.
- GTIN 8426594127534 aparece en la URL, no como campo independiente: `gtin=None`.
  La referencia de fórmula sigue **sin verificar** en el catálogo. No se habilita.
- <https://www.charrodesdecasa.com/buscar?controller=search&s=Blemil> se inspeccionó;
  no quedó implementado el buscador externo. Se admiten URLs locales configurables.
- <https://www.charrodesdecasa.com/content/8-envio-y-pago>: política publicada
  6,50 € bajo 50 € en península; superiores a 50 € gratis; 24–72 horas, tarjeta o
  transferencia. **El carrito anónimo mostró 3,99 €**, producto 25,15 € y total
  29,14 €. No se resuelve la contradicción inventando una tarifa.
- `/carrito`, `/carrito?action=show`, `/pedido`, `/mi-cuenta`, `/historial-compra`
  inspeccionados en `www.charrodesdecasa.com`. Un clic añadió una lata; `/pedido`
  se detuvo en datos personales, sin continuar ni crear cuenta. Historial exige acceso.

## Nappy

- <https://nappy.es/1087-talla-3>: 14 resultados, incluyendo lotes mixtos con
  toallitas/cremas, que el adaptador excluye. El listado también contiene enlaces
  de recomendaciones de otras tallas: la selección posterior aplica las restricciones.
- <https://nappy.es/dodot/6035-panales-talla-3-bebe-seco-dodot.html>:
  186 unidades, talla 3, 4687 céntimos, `availability=in_stock`.
- <https://nappy.es/dodot/6473-panales-dodot-sensitive-extra-talla-3-56-unidades.html>:
  56 unidades, talla 3, 3125 céntimos, **`availability=unavailable`**. Fixture real
  de falta de existencias; no se inventaron capturas equivalentes para otras tiendas.
- Recorrido real del adaptador descubrió también 372/558/744 unidades por
  9373/14062/18749 céntimos; Sensitive 56 por 2295; paquete 62 por 1690.
  Son observaciones de esa fecha, no precios constantes del programa.
- <https://nappy.es/content/1-entrega>: peso/destino, gratis para superiores a 65 €
  en península; 24/48 horas laborales con condiciones. No tarifa inferior verificable.
- <https://nappy.es/content/5-pago-seguro>: tarjeta Redsys con identificación del
  titular, transferencia, PayPal con posible comisión, Bizum, seQura. Esto es
  **texto informativo**, no una prueba bancaria ni autorización de financiación.
- `/carrito`, `/pedido`, `/mi-cuenta`, `/historial-compra` inspeccionados. Tras un
  clic público en añadir, el carrito siguió vacío; causa no determinada, sin reintentar.
  `/pedido` devolvió contenido del carrito vacío. Historial mostró acceso.

## Mercadona, CP 28023

- <https://tienda.mercadona.es/>: rechazo de cookies opcionales; entrada de 28023
  en `input[name=postalCode]`, Enter. El contenido identificó la zona mediante
  `aria-label="Entregar en código postal 28023"`. No es evidencia de dirección completa.
- <https://tienda.mercadona.es/search-results?query=Dodot>: seis productos, tallas
  1–6; talla 3 Sensitive, paquete 56 unidades, precio actual 16,95 € (anterior 20,95 €).
- Al abrir el producto desde el resultado:
  <https://tienda.mercadona.es/product/52879/panales-bebe-talla-3-6-10-kg-dodot-sensitive-paquete>.
- <https://tienda.mercadona.es/authenticate-user/>: opciones de acceso Apple/email,
  no sesión. La portada pide identificarse y añadir dirección para conocer entrega.
- El gestor inicialmente bloqueó recursos del buscador. Se observó la petición a
  `tornillos.mercadona.es`; permitir **ese dominio exacto como recurso**, junto con
  `farolas.mercadona.es`, `featureflags.mercadona.es`, `prod-mercadona.imgix.net`,
  permitió reproducir búsqueda y ficha con el gestor real. Ninguno obtiene permiso
  de navegación. Analytics, reCAPTCHA y alternativas Algolia permanecen bloqueados;
  no hay bypass global, pagos ni intentos de evadir retos.
- El 28 de septiembre se repitió el recorrido integrado con el código final:
  verificación estricta de región, descubrimiento genérico, ficha y recotización de
  solo lectura. Resultado: 56 unidades, 1695 céntimos, envío y total desconocidos.
  No se volvió a añadir a ningún carrito ni a intentar acceso o pago.

## Fixtures y límites

`tests/fixtures/stores/*.html` son fragmentos de capturas reales, no sitios ficticios.
Se conservaron exclusivamente nodos de producto/resultado; el JSON de producto se
redujo a campos de nombre, precio, disponibilidad, formato y condiciones. Se quitaron
reseñas, personas, sesiones, formularios, tokens y scripts. Las modificaciones negativas
en tests están señaladas expresamente como sintéticas.

No se ha observado un pago, una referencia de pedido, una pantalla real 3DS, un
CAPTCHA resuelto, ni prueba inequívoca de no envío. Los tests de las operaciones
inhabilitadas comprueban su negativa a actuar, **no un flujo de checkout implementado**.

Las cotizaciones releen producto/precio; envío, total y entrega siguen `None`.
No se interpreta el total de un carrito sin dirección como precio entregado en 28023.
La búsqueda es parcial y configurable; no demuestra el precio mínimo global.

## Integración pendiente

El checkout observado se bloquea por datos personales/sesión ausentes, identidad
GTIN independiente pendiente y/o carrito no verificado. El controlador debe obtener
la intervención local del usuario; nunca pedir contraseñas en código o registros.

El controlador confirmó el 28 de septiembre la estructura plana: `stores/` y módulos
en raíz. No se ha realizado una migración de arquitectura.

### Uso local de las conexiones

`stores.connections.registrations()` devuelve registros explícitos, no abre navegadores.
Crear `StoreRegistry(registrations())`, después `BrowserManager(private_profiles, registry)`;
asignar `registry.get(id).adapter.context = await manager.open(id)` una vez por tienda.
Cerrar el gestor en `finally`. No reutilizar los perfiles anónimos de inspección como
carritos preparados. El constructor de cada adaptador permite `product_urls` y
`listing_urls` de configuración local confiable; no modifican precios ni restricciones.

Estado de esta entrega: **DONE_WITH_CONCERNS**, conexiones públicas parciales;
checkout autónomo bloqueado. Verificación final: 47 tests de tiendas y 220 totales
correctos; Ruff sin incidencias. Los tests offline no elevan capacidades en vivo.
