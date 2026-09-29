# Interpretación local de mensajes con Gemma 4

Estado: documento revisado y aprobado por el usuario el 29 de septiembre de 2026.

## Objetivo y límites

Permitir que el usuario ya vinculado al bot de Telegram añada y consulte necesidades domésticas en español natural sin pagar una API de lenguaje por mensaje. El bot conserva sus comandos explícitos como ruta fiable y el modo `dry_run` actual. Esta mejora **no** habilita compras reales, no modifica las restricciones de fórmula, pienso o pañales y no instala un agente de navegación autónomo.

El entorno comprobado es Windows con NVIDIA GeForce RTX 3060 de 12 GB (12 288 MiB). El proveedor recomendado es Ollama local con `gemma4:e2b` y `num_ctx=4096`. El tamaño de descarga indicado por Ollama ronda 7,2 GB; el uso real de VRAM, velocidad y calidad deberán medirse en el equipo. El contexto limitado no reduce los pesos descargados. `gemma4:12b` cuantizado es una alternativa posterior, no un cambio automático.

## Componentes y fronteras

- **Transporte y almacenamiento existentes:** `telegram_io.py`, `conversation.py` y `storage.py` mantienen autorización de usuario, recepción duradera, lista, órdenes y avisos. No se rehace su flujo.
- **Interfaz de intérprete existente:** `Interpreter.parse(text, lines) -> Intent` continúa como frontera. Los comandos interpretados por `parse_command` tienen prioridad y funcionan sin modelo.
- **Intérprete local nuevo:** solicita a Ollama únicamente una propuesta `Intent` en JSON conforme al esquema permitido. No recibe credenciales, dirección completa ni herramientas para tiendas o pagos. Usa un endpoint de bucle local (`127.0.0.1:11434`), sin publicar el servicio en la red doméstica o Internet.
- **Validación determinista existente:** `Conversation` comprueba la procedencia del mensaje, IDs, producto, cantidades y autorización de compra. La salida del modelo nunca omite características para reemplazar un producto ni ejecuta acciones irreversibles.
- **Configuración:** la selección del proveedor `commands_only`, `openai` (ya existente) u `ollama`, y del modelo/contexto, se guarda en la configuración privada local. La configuración ya existente del bot, su usuario autorizado, la base de datos y el offset de Telegram se conservan. No se exige clave OpenAI para Ollama ni se confunde la suscripción a otra aplicación con una clave de API.

## Mensajes y seguridad

1. Los comandos `/lista`, `/anadir`, `/cantidad`, `/quitar`, `/comprar` y `/estado` conservan su comportamiento actual. Una caída de Ollama no debe romperlos.
2. Una frase no reconocida por comandos pasa al intérprete local con un esquema restringido. Se limita el contexto a la frase actual y a las líneas necesarias de la lista; no se envía la dirección, el token ni el historial completo de Telegram.
3. El resultado se valida sintáctica y semánticamente. Negaciones, citas, referencias incompletas, productos incompatibles, cantidades ambiguas o salidas malformadas generan una pregunta de aclaración sin mutar la lista.
4. Solo una orden de compra **explícita y determinista** puede iniciar la orquestación. El modelo no puede iniciar `buy`, `resume`, `remove` o `set_quantity` a partir de suposiciones. La compra real sigue deshabilitada por los adaptadores de tienda.
5. Un fallo, tiempo de espera o respuesta inesperada del servidor local muestra una explicación breve e indica que se pueden usar comandos. No se reenvía el mensaje a un proveedor externo como fallback ni se escriben cuerpos de mensajes privados en logs.
6. Limitar el servidor a loopback y no aceptar URLs de modelo recibidas por Telegram. El tamaño de contexto se fija en 4096 y se controla el tiempo de espera para la primera carga del modelo; ninguna llamada de red local bloquea indefinidamente el worker.

## Instalación y validación

La instalación de Ollama y la descarga del modelo afectan al ordenador fuera del repositorio y requieren aviso/consentimiento explícito antes de ejecutarlas. No instalar ni descargar como efecto secundario de importar módulos, arrancar el bot o ejecutar pruebas. Antes de intervenir se documentan tamaño esperado, espacio requerido y cómo parar/desinstalar el servicio local.

Orden de verificación:

1. Confirmar instalación y capacidad de respuesta de Ollama en loopback; descargar `gemma4:e2b` solo con consentimiento.
2. Probar de forma aislada frases de lista y adversariales, y medir latencia/VRAM con contexto 4096. Si la GPU no basta o el resultado no es fiable, conservar `commands_only` y reportar la limitación; no cambiar de modelo silenciosamente.
3. Añadir pruebas unitarias del adaptador local con respuestas válidas, inválidas, caídas y tiempos de espera; probar que el validador rechaza sustituciones (Blemil etapa 2, pienso distinto, Dodot talla 4) y una compra negada.
4. Repetir la batería de pruebas existente y probar con el Telegram ya vinculado: añadir una necesidad con lenguaje natural, consultar la lista y probar un fallo simulado del modelo. Confirmar que comandos y estado persisten tras reiniciar el worker. No enviar `/comprar` para probar el modelo ni efectuar cargos.

La prueba de aceptación consiste en obtener respuestas correctas y seguras en Telegram, manteniendo funcionamiento solo con comandos cuando Ollama no está disponible. No se afirmará que el modelo funciona en la RTX 3060 hasta medirlo realmente, ni que el bot realiza compras reales.

## Referencias

- [Requisitos aproximados de memoria de Gemma 4](https://ai.google.dev/gemma/docs/core): las cifras de pesos no incluyen toda la memoria del contexto/servidor.
- [Variantes Gemma 4 de Ollama](https://ollama.com/library/gemma4): `gemma4:e2b`.
- [API de chat con salida estructurada de Ollama](https://docs.ollama.com/api/chat): formato JSON Schema y opciones de generación.
