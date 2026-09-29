# Task 2 — configuración y montaje del intérprete local

## Resultado

- `Settings` persiste `model_provider` (`commands_only`, `openai`, `ollama`) y el modelo local fijo `gemma4:e2b`. Las configuraciones antiguas sin selector infieren `openai` solo cuando contienen modelo y clave, sin modificar el archivo al leerlo.
- `model-local enable|disable|status` modifica exclusivamente la configuración privada existente bajo el bloqueo exclusivo del worker; `enable` exige que `/api/tags` en loopback confirme el modelo. La comprobación usa timeout, sin proxy ni redirects; errores, respuestas malformadas y ausencia del modelo fallan sin guardar. Ninguna acción llama a `configure` ni `bind_user`.
- `runtime.run` selecciona por proveedor sin fallback remoto; el adaptador Ollama abre/cierra su cliente en cada `parse` (Task 1), mientras que el cliente heredado OpenAI se cierra en `finally`. Sin modelo disponible el worker sigue procesando los comandos.
- README y setup documentan instalación/desinstalación **manual**, tamaño aproximado (7,2 GB), privacidad del puerto local, comandos de activación y las limitaciones de pruebas offline.

## Evidencia RED/GREEN

1. Añadidas pruebas de migración heredada, persistencia con SQLite/offset/lista/órdenes, cambio de proveedor, bloqueo ocupado y fallo del diagnóstico, rechazo de redirects/respuestas inesperadas/modelo ausente, ausencia de proxy, fallo Ollama con `/lista` posterior y cierre del cliente por llamada. RED: `python -m pytest tests/test_runtime.py -q` → **8 failed, 17 passed**; fallos debidos al selector/CLI/diagnóstico ausentes y al runtime sin ruta Ollama. Se corrigió un test-fixture que pasaba una cadena a `model_copy` para `SecretStr` (no era defecto de producción).
2. Implementación mínima en `config.py`, `cli.py` y `runtime.py`. GREEN: `python -m pytest tests/test_runtime.py -q` → **25 passed**. Ruff detectó únicamente orden de importaciones, corregido.
3. Añadida prueba específica de cierre del cliente HTTP heredado en cancelación. RED: `python -m pytest tests/test_runtime.py -q` → **1 failed, 25 passed** (`Client.closed == False`). GREEN después de cierre en `finally`: **26 passed**.
4. Verificación final: `.venv\Scripts\python.exe -m pytest -q` → **283 passed**; `.venv\Scripts\python.exe -m ruff check .` → **All checks passed**.

## Autorrevisión y límites

- Solo seis archivos de tarea y este reporte; no se instaló Ollama, descargó un modelo, usó Telegram real, accedió a datos privados ni intervino en tiendas. Diagnóstico con `httpx.MockTransport`, runtime con servidor falso 503.
- El cambio de configuración requiere detener el worker; no reinicia Telegram, y el nuevo proveedor surte efecto al reiniciar el worker. `status` también requiere bloqueo libre.
- La comprobación confirma la respuesta y etiqueta del servidor en el puerto loopback, pero no autentica la identidad del proceso local ni comprueba VRAM/latencia/calidad reales. Una descarga real requiere consentimiento aparte. Las pruebas no acreditan conectividad real.
- Las sesiones HTTP de Ollama son propiedad de cada llamada y se cierran dentro de `OllamaInterpreter.parse`; el runtime no mantiene ni cierra un cliente compartido Ollama.

## Revisión posterior: bloqueo con base de datos anidada

El bloqueo inicial del CLI usaba `private/worker.lock`, pero `runtime.run` usa
`settings.database_path.parent / "worker.lock"`; si la base de datos está en
`private/nested/`, ambos comandos podían ejecutarse simultáneamente. El CLI ahora
carga la configuración para localizar exactamente el lock del runtime, lo adquiere,
vuelve a leer la configuración bajo el lock y rechaza el cambio si el destino del
lock (ruta de base de datos) cambió entre ambas lecturas. No modifica el archivo si
el worker está activo o detecta esa carrera.

**RED:** Se agregaron dos tests en `tests/test_runtime.py`: uno invoca
`model_local(..., "disable")` durante el ciclo de `runtime.run` con base anidada;
el otro cambia el destino de base de datos antes de adquirir el lock y comprueba que
el nuevo proveedor no se sobrescribe. La primera versión del test de worker anidado
invocaba `cli.main` desde un event loop: el `asyncio.run` anidado devolvía error antes
de intentar bloquear y produjo un falso positivo; se corrigió el test para invocar
`await cli.model_local` directamente. RED correcto:
`.venv\Scripts\python.exe -m pytest tests/test_runtime.py -q` → **2 failed, 26 passed**:
worker anidado no lanzó `RuntimeError` y el cambio de destino devolvió éxito.

**GREEN:** Cambio focalizado en `cli.py`:
`.venv\Scripts\python.exe -m pytest tests/test_runtime.py -q` → **28 passed**.
Verificación final `.venv\Scripts\python.exe -m pytest -q` → **285 passed**;
`.venv\Scripts\python.exe -m ruff check .` → **All checks passed**.
No se usó Ollama real, Telegram ni recursos externos.
