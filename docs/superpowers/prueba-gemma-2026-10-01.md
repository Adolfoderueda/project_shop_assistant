# Gemma: prueba aislada del 01-10-2026

Dos secuencias de diez mensajes inventados, con `OllamaInterpreter` real,
`Conversation`, SQLite temporal y `dry_run`. Sin Telegram, configuración privada,
tiendas, scraping ni comandos de compra. No se instaló/descargó nada, se pararon
procesos ni se activó el proveedor del bot.

## Evidencia observada

- Antes de la primera secuencia `/api/ps` devolvió `models: []`; la primera
  interpretación «necesito arroz» tardó **25,549 s** y añadió arroz sin cantidad.
  Es una carga con modelo no residente, no un máximo de latencia ni prueba tras
  reiniciar el servicio/equipo.
- «necesito arroz integral por favor» añadió exactamente `arroz integral` sin
  cantidad en ambas secuencias (0,471 s y 0,448 s).
- La consulta de lista leyó las dos líneas persistidas. La consulta de arroz
  integral ausente dejó un único pendiente. La de pañales mostró las dos fichas
  históricas, fechadas, sin afirmar stock/precio actuales.
- «necesito Blemil etapa dos» y «necesito pienso de pollo» conservaron su
  descripción completa y `product_id=None`: no se sustituyeron por referencias
  permitidas ni se acreditó su verificación.
- «no compres» no mutó la lista. **Cero órdenes** en cada paso de ambas secuencias.
- La repetición comenzó con `gemma4:e2b` residente, contexto 4096, tamaño reportado
  por `/api/ps` de 1708392447 bytes. Latencias calientes: **0,448–0,801 s** en
  esa secuencia. GPU al finalizar: **5090/12288 MiB**, RTX 3060; instantánea de
  consumo total, no pico ni atribución exclusiva al modelo.

## Limitaciones detectadas: no aceptar todavía para uso cotidiano

- En ambas secuencias Gemma clasificó «¿qué productos disponibles vimos?» como
  `list` y mostró la lista de compras, no las fichas observadas. No creó backlog
  ni mutaciones, pero la respuesta no resuelve la pregunta. Los tests con intención
  `product_query` sí demuestran el rechazo de pendientes genéricos en código.
- Para «necesito arroz si hay oferta por favor» propuso incorrectamente `add`
  de arroz. El validador rechazó esa intención en ambas secuencias, sin mutar.
  La seguridad no depende de la fiabilidad del modelo.
- Tras varias altas sin cantidad, la respuesta pide cantidad de la primera línea
  pendiente (arroz), incluso al añadir otro producto. Comportamiento heredado,
  no corregido en este alcance; puede confundir al usuario.
- La primera ejecución completó los diez mensajes pero salió con error al limpiar
  la DB temporal: el arnés dejó una conexión SQLite abierta en Windows. Se cerró
  explícitamente esa conexión en el arnés; la repetición terminó con código 0.

Muestra pequeña y secuencial, no garantía de fiabilidad. **No habilitar Gemma por
estos resultados**. Próxima fase: acordar corrección de calidad de clasificación
y claridad de respuestas, repetir aceptación aislada y, solo con autorización
específica/sesión disponible, probar Telegram. Mantener el proveedor privado sin
cambios y usar comandos explícitos.
