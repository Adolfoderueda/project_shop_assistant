# Continuación — Gemma local, lista y fichas (30-09-2026)

## Dónde retomar

- Rama: `feat/gemma4-local`; worktree aislado: `.worktrees/gemma4-local` desde la raíz del repositorio. La rama contiene commits locales posteriores a `origin/feat/gemma4-local`; **no se ha hecho push ni merge**. Último commit de código antes de este documento: `027390c`.
- Especificación aprobada: `docs/superpowers/specs/2026-09-29-lista-fichas-gemma-design.md`; plan: `docs/superpowers/plans/2026-09-29-lista-fichas-gemma.md`.
- Ledger e informes de agentes: `.superpowers/sdd/2026-09-29-lista-fichas-gemma/` en el worktree (ignorado por Git). **Este documento versionado conserva los hechos indispensables si no se dispone del ledger.** No repetir las cuatro tareas ya implementadas.

## Avances comprobados

1. Ollama 0.34.4 instalado para este usuario y `gemma4:e2b` descargado (~7,2 GB). Servicio local observado en `127.0.0.1:11434`; GPU RTX 3060 de 12 GB. El bot privado **no** tiene el modelo activado por esta sesión; no se accedió a `private/` ni se modificó su proveedor.
2. Migración SQLite v5 y cuatro fichas estructuradas, fechadas, de productos públicos observados anteriormente (Amascotados, Charro, Nappy, Mercadona). Consulta limitada a fichas; precios y stock se presentan como **históricos**, no como ofertas ejecutables. La referencia de fórmula no se considera verificada por aparecer en una URL.
3. La lista sigue siendo la de SQLite. Se añadió consulta de fichas y una cola de productos ausentes, con nombre normalizado; backlog, respuesta, inbox y outbox comparten transacción. Los comandos deterministas conservan prioridad y las compras reales permanecen deshabilitadas.
4. Gemma recibe contexto acotado de lista y fichas relevantes; no tiene herramientas de SQL, red, tiendas ni pago. En una prueba **aislada** con Ollama real, texto inventado y SQLite temporal: «necesito arroz» añadió una línea sin cantidad, se respondieron consultas de lista y fichas, una consulta sin ficha generó un pendiente, y «no compres» no creó órdenes. Muestra pequeña en caliente, insuficiente para aceptación de Telegram o fiabilidad general. Ver `docs/superpowers/progress.md` y `docs/setup.md` para tiempos/VRAM y límites.
5. Flujo ejecutado con agentes: cada tarea tuvo revisión; se corrigieron tipos SQLite, stock desconocido, puntuación interna de consultas y separación documental de `/comprar`. La revisión global halló que una salida errónea del modelo podía convertir una pregunta en un alta; se corrigió en `027390c` y la revisión acotada confirmó ese punto.
6. Última verificación completa tras `027390c`: `.venv\Scripts\python.exe -m pytest -q` → **343 passed in 132.44s**; `.venv\Scripts\python.exe -m ruff check .` → **All checks passed!**. Los tests verdes **no** cubren aún los dos casos pendientes siguientes.

## Dos fallos pendientes — bloquear activación y merge

1. **Backlog genérico compuesto.** `¿qué productos disponibles vimos?` puede extraer `productos disponibles`, superar el filtro de palabras genéricas (`product_memory.py`) y quedar registrado como si fuera un producto faltante; la respuesta afirma erróneamente que se añadió al backlog. `¿qué productos vimos?` y `¿qué sabes de precio?` ya están cubiertos, pero el filtro actual solo rechaza ciertos nombres completos. Reproducir en tests con `FakeInterpreter` que proponga `Intent(action='product_query', lines=[IntentLine(description='productos disponibles')])`; comprobar **sin backlog y sin respuesta «pendiente»**. Diseñar un criterio conservador para categorías/atributos completos, sin bloquear «arroz integral» ni nombres de productos reconocibles. Comprobar tanto `Conversation` como `Repository.apply_intent` directo.
2. **Petición cortés rechazada.** `necesito arroz por favor` se rechaza en `Conversation._validate_model` aunque Gemma proponga añadir `arroz`. Admitir únicamente un sufijo cortés acotado tras una petición afirmativa inequívoca; seguir rechazando preguntas, condiciones, negaciones, productos alternativos y una salida del modelo que incluyera indebidamente `por favor` en el nombre. Regresión RED→GREEN en `tests/test_conversation.py`.

La revisión acotada tras `027390c` confirmó que el bloqueo de altas no solicitadas **sí está resuelto**, pero señaló los dos casos anteriores. Tratar ambos como trabajo nuevo y revisar sus pruebas antes de activación. Hallazgo menor diferido: la búsqueda de fichas se repite entre lectura previa para el modelo y respuesta transaccional (`storage.py`); hoy usan la misma regla/orden/límite, pero podrían divergir con cambios futuros.

## Límites para la próxima sesión

- No releer ni copiar secretos, direcciones, tokens o base privada al repositorio. No ejecutar `model-local enable`, parar el worker privado, usar Telegram real o subir la rama por inferencia: solicitar autorización específica y disponer de sesión privada antes de la aceptación. `docs/setup.md` describe el protocolo pendiente.
- No ejecutar `/comprar` durante pruebas de Gemma, ni navegar tiendas, scrapear, pagar o modificar el checkout para resolver estos fallos. Mantener `dry_run` y capacidades de compra real bloqueadas.
- Tras corregir ambos casos, repetir tests completos, Ruff y revisión independiente; después validar frases representativas con Ollama real en una base **de prueba**, incluyendo arranque en frío, preguntas genéricas, peticiones corteses y referencias restringidas. Si falla la calidad, mantener comandos sin activar el modelo.
