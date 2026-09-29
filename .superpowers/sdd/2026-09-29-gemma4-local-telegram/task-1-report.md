# Task 1 — Intérprete local Ollama

## Cambios

- `ollama_interpreter.py`: adaptador asíncrono de `Intent` que da prioridad a `parse_command`, envía únicamente mensaje actual y campos mínimos de líneas por `POST /api/chat` a `127.0.0.1:11434`, con esquema Pydantic, `think=false`, `stream=false`, `num_ctx=4096`, sin redirecciones ni proxies de entorno y con límite total de 60 segundos (`asyncio.timeout`, además del timeout HTTP). Devuelve `clarify` ante errores, respuestas malformadas, rechazos y roles inesperados, sin exponer contenido/error del proveedor.
- `pyproject.toml`: dependencia directa de `httpx` y registro del módulo en `py-modules`. `requirements.lock` ya incluía `httpx==0.28.1`, sin cambios.
- `tests/test_ollama_interpreter.py`: transporte HTTP simulado sin servidor; verifica comandos sin red, destino, contenido mínimo, contrato Ollama, errores, rechazo, plazo global y ausencia de seguimiento de redirecciones.
- `tests/test_conversation.py`: comprueba que propuestas destructivas del modelo, negación y pérdida de calificador no mutan lista ni crean órdenes.

## Evidencia RED / GREEN

1. RED inicial: `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py tests/test_conversation.py -q` → error de importación `ModuleNotFoundError: No module named 'ollama_interpreter'`, salida 1; sin conexión externa.
2. GREEN inicial: mismo comando → `74 passed in 5.23s`.
3. RED rechazo explícito: `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py -q` → `1 failed, 11 passed`; `test_explicit_model_refusal_cannot_become_an_addition`: `add` en vez de `clarify`.
4. GREEN rechazo: `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py tests/test_conversation.py -q` → `75 passed in 8.50s`; Ruff → `All checks passed!`.
5. RED rol inesperado: `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py -q` → `1 failed, 12 passed`; `test_non_assistant_response_cannot_propose_intent`: `list` en vez de `clarify`.
6. GREEN final: `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py tests/test_conversation.py -q` → `76 passed in 6.58s`.
7. Ruff final: `.venv\Scripts\python.exe -m ruff check ollama_interpreter.py tests/test_ollama_interpreter.py tests/test_conversation.py` → `All checks passed!`.
8. Batería completa final: `.venv\Scripts\python.exe -m pytest -q` → `274 passed in 104.57s (0:01:44)`; ejecución completa previa antes del último cambio → `273 passed in 86.81s`.

## Revisión y riesgos

- Revisados los cambios y el alcance: no se modificaron `private/`, tiendas, repositorio de almacenamiento, runtime ni CLI; no se instaló Ollama ni se descargaron modelos. `git diff --check` sin errores (advertencias de conversión LF/CRLF del entorno).
- En vez de inyectar un cliente HTTP configurable que pudiera apuntar fuera de loopback, solo se permite inyectar un transporte para pruebas; el cliente real siempre fija `base_url` local, `trust_env=False` y `follow_redirects=False`. Como con cualquier dependencia arbitraria, un transporte inyectado malicioso puede ejecutar sus propios efectos externos: no inyectar transportes no confiables en producción.
- El plazo global usa cancelación asíncrona de Python: cubre esperas normales de HTTP y carga fría, pero una implementación de transporte que suprima deliberadamente la cancelación puede impedir el retorno puntual. No se hizo prueba real de Ollama ni Telegram; depende de las tareas posteriores y del consentimiento para instalación/modelo.
