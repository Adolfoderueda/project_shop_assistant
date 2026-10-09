# Asistente de compras local

Bot de Telegram de un solo usuario en Windows; por defecto **dry_run** (sin compras).
Configuración privada y consentimiento para tarea programada: [docs/setup.md](docs/setup.md).
Capacidades reales y bloqueos de las tiendas: [docs/store-capabilities.md](docs/store-capabilities.md).

En PowerShell desde la raíz: `py -3.12 -m venv .venv`,
`.\.venv\Scripts\python.exe -m pip install -e '.[dev]'`,
`.\.venv\Scripts\python.exe -m playwright install chromium` y
`.\.venv\Scripts\python.exe -m shop_assistant configure` **solo en consola local**.
Ejecutar `doctor` antes de `run`. No enviar tokens, direcciones ni datos bancarios
por chat. Sin configuración privada, `doctor` falla. Los tests end-to-end son
offline con fakes: no producen recibos reales ni verifican pagos.

Para añadir interpretación local opcional con Ollama `gemma4:e2b` sin revincular Telegram,
consulta [instalación y selección del modelo](docs/setup.md#interpretación-local-opcional-ollama).
`model-local enable|disable|status` opera sobre la configuración existente; no instala
ni descarga Ollama automáticamente y no reemplaza los comandos cuando falla el modelo.

## Agente local de skills (opt-in)

El motor predeterminado sigue siendo `legacy` y su modelo Ollama sigue siendo
`gemma4:e2b`. Tener instalado E4B no activa el agente. Instala por separado
`gemma4:e4b-it-q4_K_M` en Ollama; la aplicación nunca descarga modelos.

Con el worker detenido, desde el directorio del proyecto:

```powershell
python -m shop_assistant agent-local status
python -m shop_assistant agent-local enable
python -m shop_assistant doctor
```

La activación selecciona explícitamente `skills_agent` y Ollama, sin cambiar el
modelo legacy, el vínculo Telegram ni el modo de compra. Reinicia el worker para
aplicar la configuración. El texto libre propone lotes; guardar exige revisar el
resumen completo y confirmar explícitamente. Los comandos slash y compras
explícitas siguen el camino determinista; las herramientas del agente no compran.

Rollback: detén el worker y ejecuta `python -m shop_assistant agent-local disable`.
Conserva el proveedor y vuelve a legacy. Cada enable/disable revoca los permisos
agent previos bajo el lock del worker, incluso sin mensajes entre cambios o si
después falla guardar la configuración. `model-local disable` también vuelve a
legacy y desactiva el proveedor; `model-local enable` no activa el agente.
Los trabajos ya comprometidos se recuperan antes de invalidar memoria incompatible;
el descarte genera un aviso independiente y durable en Telegram para volver a
formular la petición, sin alterar respuestas anteriores ni entradas guardadas.
Status no modifica permisos y doctor no descarga ni genera texto.

## Preguntas guiadas experimentales (sin aceptación para activar)

`guided_questions=False` por defecto; solo es válido con `skills_agent`. La aplicación
controla preguntas persistentes, alcance, tema adicional y confirmación del resumen
íntegro entregado. Seleccionar producto/grupo o añadir un tema **no guarda**. Consultas
conservan el borrador; duplicados no se suman y cantidades desconocidas no son cero.
Texto libre sigue disponible, pero un fallback no demuestra comprensión de E4B.

La [matriz y evidencia sintética](docs/superpowers/evidence/2026-10-09-preguntas-guiadas/results.md)
mantiene la aceptación bloqueada. No activar ni reiniciar Telegram con este candidato.
El probe no lee configuración privada ni lanza Telegram; usa bases temporales aisladas,
bloqueo de compras y recibos de un transporte simulado. `real` requiere el E4B existente
en localhost; no instala ni descarga nada. Desde la raíz, con la venv **ya existente**:

```powershell
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -P scripts/probe_guided_questions.py --mode offline --output offline.jsonl --repetitions 3
.\.venv\Scripts\python.exe -P scripts/probe_guided_questions.py --mode real --output real.jsonl --repetitions 3
.\.venv\Scripts\python.exe -P scripts/probe_guided_questions.py --verify real.jsonl
```

Cada salida es inmutable; elegir una ruta nueva. `--verify` no llama al modelo y
devuelve nonzero si faltan pasos, hay fallos, cambian hashes o expectativas no coinciden.
Botones simulados/etiquetas ofrecidas no cuentan como comprensión del modelo.
El verificador v3 revalida la evidencia v2 inmutable contra su commit Git archivado y
`archive-v2.json` (bytes/fin de línea exactos), separando el intérprete ejecutado del
verificador actual. Requiere esos objetos Git locales; no descarga nada ni exime hashes
de código. Revalidar historia no demuestra aceptación del runtime actual.

Para administración futura autorizada: `python -m shop_assistant questions-local status`
no cambia permisos; `enable|disable` requiere el lock del worker detenido. Rollback:
usar **código nuevo**, `questions-local disable`; revoca preguntas/tokens/temas/revisión
pendientes y conserva filas guardadas. La base permanece en schema10: no downgrade a v9
ni restauración de backup sin autorización. No se ejecutaron esos comandos aquí.
Una futura prueba Telegram exige autorización separada, base vacía independiente,
perfiles de tiendas sin abrir, bloqueo explícito buy/resume/checkout y un único worker;
`dry_run` por sí solo no basta. La aceptación anterior del agente sigue abierta.
