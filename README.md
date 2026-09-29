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
