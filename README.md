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
