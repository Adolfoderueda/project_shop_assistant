# Punto de continuación — Telegram (28 de septiembre de 2026)

## Comprobado con el usuario

- Repositorio privado: `https://github.com/Adolfoderueda/project_shop_assistant`, rama `feat/shop-assistant`.
- El usuario ejecutó `configure` en su consola local y vinculó su bot mediante el código temporal. La configuración privada está en `private/`, excluida de Git. **No copiar tokens, claves, dirección ni la base de datos al repositorio.**
- El usuario mostró la salida de `doctor`: `SQLite: OK`, `Telegram API: OK`, Chromium instalado; modelo no configurado (modo solo comandos). Las cuatro tiendas tienen búsqueda y cotización parcial, pero ninguna tiene `prepare`, `submit`, `reconcile` ni compra real verificados.
- Se descubrió que inicialmente había procesos `configure` activos y ningún proceso `run`; después de indicar el arranque manual, el usuario recibió respuestas por Telegram a `/lista`, `/anadir arroz` y `/lista`.
- El usuario envió `/cantidad <id> 1`, recibió «Lista actualizada» y confirmó que `/lista` devolvió cantidad 1. La base de datos local mostró una línea `arroz` con cantidad 1 en lectura de solo lectura.
- No se probó reiniciar el worker para comprobar persistencia con el bot; los tests automatizados sí cubren recuperación. No se ha instalado la tarea programada de Windows ni se ha efectuado compra real.
- El usuario preguntó por el coste de la API OpenAI. Se explicó que se cobra aparte y que, por ahora, los comandos explícitos funcionan sin ella. No solicitar ni suponer autorización para contratarla.

## Próximo paso acordable

1. Probar persistencia real con Telegram: detener solo el `run` manual con Ctrl+C, arrancarlo de nuevo en una única consola con `.\.venv\Scripts\python.exe -m shop_assistant run` desde la raíz y enviar `/lista`; confirmar que sigue `arroz: 1`.
2. Elegir junto con el usuario si basta el modo comandos o si quiere lenguaje natural. La API OpenAI conlleva coste separado; no activarla sin elección explícita. Si se activa, introducir credenciales solo en la consola local y fijar un límite de gasto en el proveedor.
3. **Después**, planificar la integración de preparación del carrito de Mercadona para un paquete Dodot talla 3, detenida antes de pagar. El usuario aprobó explorar este recorrido, no una orden real ni un cargo. El adaptador actual de Mercadona no prepara carritos ni envía pedidos. No cambiar a `live` ni pulsar comprar.

## Referencias

- `docs/setup.md`: configuración/arranque local.
- `docs/store-capabilities.md`: limitaciones verificadas por tienda.
- `docs/superpowers/specs/2026-09-27-asistente-compras-design.md`: diseño aprobado.

Sin secretos, dirección postal completa ni credenciales en este documento.
