# Configuración local (Windows)

El repositorio usa módulos Python planos en raíz, empaquetados con `pyproject.toml`.
Desde la raíz en una consola local interactiva:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m shop_assistant configure
.\.venv\Scripts\python.exe -m shop_assistant doctor
.\.venv\Scripts\python.exe -m shop_assistant run
```

`configure` pregunta **en esta consola** el token oculto de BotFather; lo valida con Telegram
y muestra un nonce para enviar `/start <nonce>` **solo en chat privado** con el bot.
Ignora actualizaciones antiguas. Hasta completar esa vinculación no guarda configuración
ni procesa órdenes. Introducir dirección completa y CP 28023 en el prompt local, jamás
en Telegram ni en el repositorio. Modelo y clave OpenAI son opcionales: sin ellos solo
se interpretan comandos explícitos (`/lista`, `/anadir`, `/cantidad`, `/quitar`,
`/comprar`, `/estado`, `/continuar`); `doctor` lo indica. El modo inicial es siempre
`dry_run`. `private/settings.json`, SQLite, perfiles y logs permanecen excluidos de Git;
el archivo se escribe con ACL del usuario local (o permisos de propietario en Unix).
Guardar una copia segura de `private/` si se necesita recuperación tras pérdida de disco.
La configuración no permite vincular el mismo directorio de datos a otro usuario:
si se intenta cambiar de propietario, se bloquea antes de sobrescribirla. El worker
también rechaza historiales, pedidos o avisos conservados de otro usuario antes de
reconciliar o procesar órdenes; requieren revisión manual y un directorio privado nuevo.
Los archivos existentes bajo `private/` (SQLite, perfiles, logs y rotaciones) se
aseguran con ACL exclusiva y comprobación posterior; un fallo de ACL bloquea el arranque.

## Interpretación local opcional (Ollama)

La selección del intérprete no vuelve a pedir el token ni revincula Telegram: conserva
el bot, usuario autorizado, lista, órdenes y offset existentes. Antes de cambiar de
proveedor, detén el worker (`Ctrl+C` o `scripts/Stop-ShopAssistant.ps1`); si su bloqueo
está ocupado, la operación se rechaza. No vuelvas a ejecutar `configure` para esto.
Ollama es una instalación **separada**, no realizada por este repositorio. Instálalo
manualmente desde https://ollama.com/download/windows solo con consentimiento explícito,
verifica que escucha **exclusivamente** en `127.0.0.1:11434` (no en la red local) y
dispón de unos 7,2 GB para el modelo más el espacio del servicio. Tras aceptar la
descarga, en la consola local ejecuta `ollama pull gemma4:e2b`; esta instrucción nunca
se ejecuta automáticamente. La RTX 3060 de 12 GB, velocidad y VRAM reales están por
verificar; el contexto de inferencia es 4096. Si no responde o no está descargado,
`enable` falla sin modificar la configuración. No se necesita clave de OpenAI.

```powershell
.\.venv\Scripts\python.exe -m shop_assistant model-local status
.\.venv\Scripts\python.exe -m shop_assistant model-local enable
.\.venv\Scripts\python.exe -m shop_assistant model-local disable
```

Reinicia el worker tras `enable` o `disable` para aplicar el cambio. `disable` deja
solo comandos explícitos; si Ollama se cae tras habilitarlo, los comandos siguen
funcionando y las frases libres piden aclaración, **sin fallback a OpenAI**. `doctor`
indica si el modelo local responde, pero no impide arrancar por su ausencia. Para
retirarlo, deshabilita el proveedor, detén Ollama desde su aplicación o servicio,
ejecuta `ollama rm gemma4:e2b` solo si deseas borrar los pesos, y desinstala Ollama
desde Aplicaciones instaladas de Windows si no lo necesitas. Ninguna de estas acciones
borra la configuración privada ni los datos de Telegram.

`doctor` no compra ni abre tienda: revisa SQLite, API Telegram, instalación de Chromium,
capacidades declaradas. Para abrir sesión manual visible en perfil dedicado:
`.\.venv\Scripts\python.exe -m shop_assistant login --store mercadona` (también `amascotados`, `charro`,
`nappy`). Introducir credenciales solo en la web visible, nunca en mensajes o CLI.
Si el perfil está ocupado por el worker, detenerlo primero; luego cerrar login y
reanudar el worker. Para la fórmula, cotejar físicamente etiqueta de **Blemil Evolution 1**
y referencia independiente del fabricante antes de ejecutar
`.\.venv\Scripts\python.exe -m shop_assistant verify-product --id formula`; un producto «Optimum Evolution»
no se equipara automáticamente. El cotejo local no verifica precio, tienda ni compra.

Con el chat privado vinculado, probar `/anadir 2 sacos de pienso`, `/lista`,
`/cantidad <id> 3`, `/comprar` (solo en `dry_run`), reiniciar el servicio y consultar
`/estado <id>`. Con los adaptadores actuales, **no esperar necesariamente un aviso
simulado**: las cotizaciones carecen de envío/total/entrega completos y la identidad
GTIN independiente puede faltar, por lo que la orden puede quedar
`requiere_intervencion` con aviso de bloqueo. Si hay una cotización completa y
compatible, el resultado `simulado` tampoco es un recibo real. La recepción de
aviso simulado después del reinicio solo se demostró en el test offline con tienda
falsa de cotización completa.
No se han ejecutado estas pruebas con el Telegram del usuario ni se ha probado el
inicio de sesión de Windows. Los tests offline usan Bot, intérprete y tienda falsos.

## Arranque automático opcional (NO instalado por este repositorio)

Solo **después** de `configure`, pruebas locales y consentimiento explícito, ejecutar
en PowerShell de la sesión del usuario:

```powershell
.\scripts\Install-ShopAssistant.ps1 -Consent
```

El script vuelve a ejecutar `doctor`, solicita `REGISTER`, registra `ShopAssistantLocal`
con principal interactivo **del usuario actual**, ruta absoluta entrecomillada y
directorio de trabajo explícito, privilegios mínimos, reinicio al fallar y sin límite
de duración. No lo registramos automáticamente. Para parar:
`.\scripts\Stop-ShopAssistant.ps1`; para retirar la tarea (no elimina datos):
`.\scripts\Uninstall-ShopAssistant.ps1 -Consent`. Tras parar, ejecutar el script
`Start-ShopAssistant.ps1` desde la sesión visible para prueba manual. El worker toma
un bloqueo de proceso, recupera intentos pendientes antes de procesar pedidos nuevos,
y conserva inbox/outbox ante interrupción. La tarea **no arranca antes del inicio de
sesión**, no activa autologin ni cambia suspensión; no garantiza servicio 24/7 si el
usuario cierra sesión, apaga/suspende Windows o no tiene red.

Para arrancar manualmente: `.\scripts\Start-ShopAssistant.ps1`; parar manualmente
con Ctrl+C. Si se instaló la tarea con consentimiento, iniciarla con
`Start-ScheduledTask -TaskName ShopAssistantLocal`, detenerla con
`.\scripts\Stop-ShopAssistant.ps1` y desinstalarla con
`.\scripts\Uninstall-ShopAssistant.ps1 -Consent`. Estos comandos son instrucciones,
**no** indican que la tarea haya sido registrada ni probada en este equipo.

## Bloqueos de compra autónoma

Actualmente todas las tiendas exponen `prepare=False`, `submit=False`,
`reconcile=False`, `live_verified=False`, cotización parcial sin envío/total/destino
completos. `dry_run` no compra; puede requerir intervención al faltar referencia,
identidad GTIN, sesión o cotización. Consulta `docs/store-capabilities.md`; no se ha
observado ningún pago real ni se puede prometer comparación global de precio mínimo.
No cambiar a modo live para probar este despliegue.
