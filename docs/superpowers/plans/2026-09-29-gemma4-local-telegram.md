# Gemma 4 local en Telegram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir interpretación local opcional de mensajes libres en español al bot existente mediante Gemma 4 E2B, sin API de pago ni cambios en compras reales.

**Architecture:** Ollama expone una API de chat en loopback. Un adaptador independiente traduce respuestas JSON a `Intent`; `Conversation` sigue siendo el único validador de acciones y `parse_command` mantiene prioridad. La configuración optativa del proveedor se cambia sin volver a vincular Telegram ni tocar pedidos previos.

**Tech Stack:** Python 3.12, Pydantic 2, `httpx.AsyncClient`, API local de Ollama `/api/chat`, modelo `gemma4:e2b`, contexto `num_ctx=4096`, pytest/Ruff, Windows RTX 3060 12 GB.

**Spec:** `docs/superpowers/specs/2026-09-29-gemma4-local-telegram-design.md`

## Global Constraints

- «Esta mejora **no** habilita compras reales, no modifica las restricciones de fórmula, pienso o pañales».
- «El proveedor recomendado es Ollama local con `gemma4:e2b` y `num_ctx=4096`».
- «Los comandos interpretados por `parse_command` tienen prioridad y funcionan sin modelo».
- «No recibe credenciales, dirección completa ni herramientas para tiendas o pagos».
- «Una caída de Ollama no debe romperlos» [los comandos].
- «Solo una orden de compra **explícita y determinista** puede iniciar la orquestación».
- «No se reenvía el mensaje a un proveedor externo como fallback ni se escriben cuerpos de mensajes privados en logs».
- «La instalación de Ollama y la descarga del modelo afectan al ordenador fuera del repositorio y requieren aviso/consentimiento explícito antes de ejecutarlas».
- Conservar identidad del bot, usuario autorizado, base de datos y offset de Telegram al cambiar proveedor.
- No instalar ni descargar como efecto de importar módulos, `doctor`, arrancar el bot o ejecutar tests. No tocar el perfil de tiendas.

## Review Focus

1. Ollama parado o primera carga lenta → comandos disponibles; mensaje libre pide aclaración sin perder inbox ni bloquear indefinidamente el worker (tareas 1 y 2).
2. JSON correcto en forma pero con acción `buy`/`remove` o referencia sustituta → validador rechaza y no altera lista/órdenes (tarea 1).
3. Cambio a modelo local con bot ya vinculado → mantiene token, ID autorizado, Telegram offset, líneas y órdenes (tarea 2).
4. Configuración/entorno de proxy adverso → cliente solo conecta a `127.0.0.1:11434`, no a red pública ni sigue redirecciones (tarea 1).
5. Modelo usa VRAM de más o interpretación española falla → reportar medida/fallos, dejar comandos como alternativa; nunca sustituir automáticamente por otro modelo o API externa (tarea 3).

---

## Archivos y contratos

- Crear `ollama_interpreter.py`: adaptador `OllamaInterpreter(client: httpx.AsyncClient, model: str = 'gemma4:e2b', context_size: int = 4096)` con `async parse(text: str, lines: list[ListLine]) -> Intent`; consume `Intent`, `ListLine`, `parse_command`, `clarify` y el validador de `Conversation` sin duplicarlo. La única URL aceptada es `http://127.0.0.1:11434/api/chat`; no permitir base URL tomada de mensajes/configuración externa.
- Modificar `config.py`: `Settings.interpreter_provider: Literal['commands_only','openai','ollama'] = 'commands_only'` y `Settings.ollama_model: Literal['gemma4:e2b'] = 'gemma4:e2b'`; `ollama_context_size: Literal[4096] = 4096`. Compatibilidad con `settings.json` previo: cuando `openai_model` y `openai_api_key` estén presentes sin `interpreter_provider`, conservar comportamiento OpenAI; de otro modo conservar comandos. Validar estados incoherentes y nunca escribir token/clave/dirección en excepciones.
- Modificar `runtime.py`: construir un único intérprete según `Settings`, conservar ruta de comandos y cerrar `httpx.AsyncClient` en `finally`; no abrir servidor local ni cambiar checkout. Si falla Ollama durante un mensaje libre, `parse` devuelve `clarify` sin reintentos peligrosos.
- Modificar `cli.py`: añadir `model-local enable|disable|status`; cargar y actualizar settings existentes sin nuevo token, nonce, vinculación ni dirección. `enable` comprueba endpoint/identidad del modelo antes de habilitar; `disable` vuelve a comandos; `status` imprime proveedor y disponibilidad sin secretos. Requerir parar worker manual antes de cambiar configuración; error claro si `ProcessLock` está ocupado, no matar procesos.
- Modificar `docs/setup.md`, `README.md`: manual para instalar/desinstalar Ollama con consentimiento y descarga opcional del modelo, comandos de diagnóstico, cómo detener el servicio, coste de disco y la limitación de compra. No guardar archivos descargados en Git.
- Añadir `tests/test_ollama_interpreter.py` y ampliar `tests/test_runtime.py`, `tests/test_conversation.py` para los contratos anteriores, sin necesidad de descargar modelo ni usar Telegram real.

### Task 1: Intérprete local seguro y aislado

**Files:** crear `ollama_interpreter.py`, `tests/test_ollama_interpreter.py`; modificar `pyproject.toml` y `requirements.lock` solo para dependencia directa `httpx` si el entorno no la declara; ampliar `tests/test_conversation.py` con invariantes de modelo local.

**Interfaces:** produce `OllamaInterpreter.parse(text: str, lines: list[ListLine]) -> Intent` asíncrono para `Conversation.handle`. Consume el validador ya existente; no llama `Repository` ni tiendas.

- [ ] **Step 1: Test RED.** Crear fake `httpx.MockTransport` y probar: `parse_command('/lista')` no llama HTTP; «necesito arroz» envía únicamente texto y líneas a `127.0.0.1:11434`, `stream=false`, `format=Intent.model_json_schema()`, `options.num_ctx=4096` y devuelve `Intent(action='add', ...)`; timeout/JSON inválido/modelo que rehúsa generan `clarify`; una redirección 3xx hacia otro host no se sigue. Añadir en `tests/test_conversation.py` que `buy`, `remove`, `set_quantity` del modelo, una negación y «necesito pienso de pollo» no mutan lista ni crean orden.
- [ ] **Step 2: Ejecutar RED.** `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py tests/test_conversation.py -q` → fallos por `OllamaInterpreter` ausente, sin tocar servidor externo.
- [ ] **Step 3: Implementar adaptador.** `async OllamaInterpreter.parse(...) -> Intent` usa `httpx.AsyncClient(base_url='http://127.0.0.1:11434', trust_env=False, follow_redirects=False, timeout=httpx.Timeout(60.0, connect=2.0))`, POST `/api/chat` con esquema de `Intent`, `think=False`, `stream=False`, `options={'num_ctx':4096}` y solo lista mínima; valida `response.message.content` con Pydantic. No registrar cuerpo. `parse_command` antes de HTTP. Respuestas/modelos no válidos generan `clarify` comprensible. Un timeout total de 60 s permite carga fría pero no espera infinita.
- [ ] **Step 4: Ejecutar GREEN.** Mismo comando → PASS; ejecutar Ruff en módulos tocados → sin errores.
- [ ] **Step 5: Commit.** `git add ollama_interpreter.py tests/test_ollama_interpreter.py tests/test_conversation.py pyproject.toml requirements.lock` (solo si cambian) y commit `feat: add local Ollama intent interpreter`.

### Task 2: Configuración sin reiniciar Telegram y conexión del runtime

**Files:** modificar `config.py`, `cli.py`, `runtime.py`, `tests/test_runtime.py`, `docs/setup.md`, `README.md`.

**Interfaces:** consume `OllamaInterpreter` de Task 1; `load_settings(root: Path) -> Settings` / `save_settings(root: Path, settings: Settings) -> None` mantienen el contrato; `model-local enable|disable|status` opera sobre la misma instalación. La construcción de intérprete conserva `OpenAIInterpreter` como opción heredada, no envía mensajes a ese proveedor por fallback.

- [ ] **Step 1: Test RED.** Con base SQLite existente, token privado simulado, bot ID y offset conocidos, habilitar modelo local y confirmar que esos datos, lista, órdenes y offset permanecen idénticos; `disable` vuelve a comandos; sin Ollama `enable` no cambia settings; configuración heredada de OpenAI conserva su proveedor, comandos existentes funcionan si Ollama cae; servidor inesperado, redirect, proxy o lock ocupado → fail closed sin sobrescribir secretos. Testear que `runtime.run` cierra cliente HTTP al salir y que la falta de modelo no mata el bot.
- [ ] **Step 2: Ejecutar RED.** `.venv\Scripts\python.exe -m pytest tests/test_runtime.py -q` → fallos de opción/configuración aún ausentes.
- [ ] **Step 3: Implementar.** Añadir selección del proveedor con migración retrocompatible en `Settings`/`load_settings`, CLI que opera sobre archivo privado existente solo con lock disponible, diagnóstico de modelo por loopback y montaje del intérprete en `runtime.run`. No llamar `configure()` ni `bind_user()` al cambiar proveedor. Cerrar recursos en `finally`. Documentar instalación y desinstalación de Ollama como instrucciones, nunca ejecutarlas como side-effect.
- [ ] **Step 4: Ejecutar GREEN y suite.** Tests específicos y `.venv\Scripts\python.exe -m pytest -q` y `.venv\Scripts\python.exe -m ruff check .` → PASS. No afirmar conectividad real por tests fake.
- [ ] **Step 5: Commit.** Añadir archivos de esta tarea y commit `feat: select local interpreter without rebinding Telegram`.

### Task 3: Comprobación voluntaria en este equipo y entrega

**Files:** actualizar `docs/setup.md` y `docs/superpowers/progress.md` solo con evidencia observada; tests pueden ampliarse si la ejecución real revela un defecto (activar `systematic-debugging` antes de reparar). Nunca escribir modelo, dirección o tokens en Git.

**Interfaces:** `python -m shop_assistant model-local enable|disable|status`, comandos Telegram ya existentes; ninguna interfaz nueva. Solo ejecutar instalación y descarga tras autorización explícita sobre efecto fuera del repositorio.

- [ ] **Step 1: Verificar sin instalar.** `nvidia-smi` debe mostrar RTX 3060 12 GB; `ollama --version` puede indicar no instalado. Documentar que la descarga de `gemma4:e2b` ronda 7,2 GB y requiere espacio adicional de disco/VRAM; solicitar consentimiento antes de `winget install` u otro instalador y de `ollama pull`.
- [ ] **Step 2: Tras consentimiento, instalar/probar.** Ejecutar instalación oficial Ollama para usuario actual, `ollama pull gemma4:e2b`, `ollama list`; medir respuesta local española con `num_ctx=4096`, tiempo y VRAM (`nvidia-smi`). Si el equipo no soporta el modelo o no hay consentimiento, marcar la comprobación en vivo como pendiente; conservar modo comandos.
- [ ] **Step 3: Activación y Telegram (solo con sesión disponible).** Parar worker manual, ejecutar `model-local enable`, reiniciar y enviar en chat privado «necesito arroz», «no compres», «necesito Blemil etapa dos»; verificar alta segura/clarificación, reinicio y `/lista`; comprobar `/anadir` cuando Ollama está parado. No usar `/comprar` como prueba ni acceder a tiendas.
- [ ] **Step 4: Verificación final.** Ejecutar suite completa y Ruff sobre árbol final, `git status --short`; documentar resultados medidos frente a pruebas falsas y bloqueos. Si hubo código de corrección, red/green y commit separado.
- [ ] **Step 5: Entrega.** Anotar en `docs/superpowers/progress.md` estado real, instrucciones de parada/desinstalación, commit y (solo con autorización de publicación vigente) subir a la rama privada. No declarar terminado el uso local si solo hubo pruebas fake.

## Autoevaluación

Cobertura: objetivo/modelo/contexto en Tasks 1/3; frontera de validación y errores en Task 1; configuración y conservación de bot en Task 2; instalación, medición y Telegram en Task 3. Cinco riesgos de `Review Focus` tienen pruebas asignadas. La compra real permanece explícitamente fuera de alcance. El plan no requiere secretos en tests ni presupone autorización de instalar software externo o cargar modelos.
