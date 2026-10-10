# Aceptación aislada de diálogo natural — 08-10-2026

**REAL PASS**, sin aceptación de Telegram privado. Base `0eb4f13`.
Se usaron los proveedores reales `OllamaInterpreter` y `OllamaReplyWriter`,
Conversation y Repository con seis SQLite temporales inventadas. No se cargaron
settings ni DB privados; no hubo Telegram, tiendas, compras, control de procesos,
ACL, instalación, descarga, reinicio ni unload. El servicio loopback ya existía.

## Evidencia y método

- [run1 JSONL](natural-dialogue-real-2026-10-08-run1.jsonl): primer PASS real,
  conservado íntegro; reloj sintético fijo (no demuestra renovación de TTL).
- [run2 JSONL](natural-dialogue-real-2026-10-08-run2.jsonl): PASS del script final,
  con reloj avanzado entre turnos, replay 30 segundos después y límite TTL900.
  Cada captura contiene texto original, propuesta del intérprete, estado v2,
  filas, snapshot v2, respuesta, requests/contexto, JSON raw exacto de ambos
  proveedores, HTTP status y latencias separadas/total. UTF-8 con BOM.
- Ambos: **34/34 pasos**, 12 llamadas reales de interpretación compatibles,
  **33/33 drafts aceptados, 0 respaldos**, cero órdenes en todos los pasos,
  cobertura obligatoria `add`, `increment`, `list`, exit0, limpieza confirmada.
  No hay fallos reales nuevos ocultados ni reparación del modelo en este task;
  los fallos históricos de probes anteriores siguen en sus informes originales.
- Modelo `gemma4:e2b`, digest
  `7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e`,
  Q4_K_M, contexto cargado4096. `/api/ps` y `/api/tags` iniciales se conservaron.
  Run2 empezó con el modelo cargado; no se fuerza frío ni se garantiza latencia.

Las expectativas se transcribieron de la brief aprobada **antes** del script:
no se calculan a partir de respuestas generadas ni del respaldo. Los tests
subprocess también comprueban secuencia/filas/aritmética/TTL de forma independiente.
El gate exige propuesta correcta y llamada real + draft aceptado en cada petición
natural obligatoria; exige aceptación en todos los actos redactados. Un respaldo
seguro o una propuesta `buy` inyectada no pueden fabricar PASS de calidad.

## Secuencias exactas e inspección de las respuestas reales

Cada caso empieza con `arroz=1`, `ARROZ=2`, `arroz integral=NULL`, sin órdenes.
Mayúsculas permiten dos entradas canónicamente iguales sin fusionarlas.

**A:** `hols → hola que tal → quiero mas arroz → cancelar → dame mi lista`.
Siempre tres entradas; nunca se añade un producto «mas arroz». Los dos saludos
son interpretación determinista sin consulta accidental; Gemma elige una variante
social: «¡Hola! ¿Qué necesitas para tu lista?». La petición incremental sí llama
al intérprete: propone `increment/arroz/quantity=null`. La respuesta ofrece solo
las dos entradas arroz, selección y cancelación. Cancelar responde «Propuesta
cancelada; no he deshecho entradas ya guardadas». La última lista muestra las
tres cantidades originales y «cantidad pendiente» para integral.

**B:** `necesito avena → dame mi lista → hola → cancelar → necesito avena → 2 →
dame mi lista`. Ninguna avena guardada antes del último `2`; después una única
avena de2. El primer y quinto turnos llaman al intérprete real (`add/avena/null`).
Gemma conserva «¿Cuántos envases de avena quieres añadir? Todavía no está en la
lista». Lista y saludo intermedios no renuevan el TTL ni guardan un alta incompleta.
Tras `2`, el resultado dice «He añadido avena: 2 envases», y la lista final la incluye.

**C:** `quiero más arroz → 1 → 2 → no → quiero más arroz → 1 → 2 → sí → dame mi
lista`. Hasta `sí`, arroz1 sigue1. La confirmación expresa explícitamente guardada1,
adicional2, total3 y «Todavía no lo he añadido». `no` cancela sin mutar. Se recrea
Conversation entre cantidad y confirmación; `sí` guarda arroz1=3 una vez y responde
«He añadido 2 envases a arroz: de 1 envase a 3 envases». Replay del mismo update
30s después devuelve idéntica respuesta/estado, ninguna llamada a modelo ni cambio
de TTL. arroz2=2 e integralNULL permanecen intactos; la lista final muestra el3.

**Guardas separadas:** tras selección y cantidad, `sí` exactamente a900s de la
última transición válida no guarda; tampoco guarda tras reservar sintéticamente
rice1 o aumentar su revisión. Se crea solo una fila de reserva de fixture en DB
temporal (FK desactivada deliberadamente), **no una orden ni `/comprar`**. Los tres
mensajes finales explican caducidad/reserva/lista cambiada, sin éxito inventado.

## Qué genera Gemma y qué no

Interpretación real acotada por gramática derivada de fuente: acción/nombre/cantidad
nula o aclaración. El reducer y SQLite conservan autoridad; incluso una propuesta
incompatible no otorga compra. Incremento reconocido en fuente puede iniciar su
pregunta independientemente de la propuesta, pero guardar requiere selección,
cantidad y confirmación explícitas. Saludos, cierres, números y `sí` son decisiones
deterministas etiquetadas; que haya writer no los convierte en intent del modelo.

Redacción v2 por acto: saludo social exacto, viñetas de lista/selección/opciones,
referencias agrupadas/separadas y «Puedes cancelar» aprobado. Los hechos,
cantidades, preguntas, opciones y resultados son de aplicación, no prosa factual
inventada por Gemma. En run2 se observaron viñetas y variantes de cancelación; los
raw demuestran drafts genuinos, incluso cuando el render coincide con fallback.
No hay cabecera genérica de v1 ni libertad de prosa abierta.

Migración v8/presentación v1 ya preparada: cubierta por regresiones aisladas de la
suite, no por las seis DB nuevas de este probe. Una presentación histórica se
finaliza compatible sin volver a ejecutar una acción. La lista privada existente
**no se limpia ni consolida automáticamente**. Cancelar nunca revierte filas guardadas.

## Reproducción autorizada, solo muestra sintética

```powershell
$env:PYTHONPATH=$PWD.Path
powershell.exe -NoProfile -File scripts/Probe-NaturalDialogue.ps1 -Python ../../.venv/Scripts/python.exe
```

Default Python busca primero `.venv`, después el entorno compartido `../../.venv`;
invoca Python con `-P`. Exit0=PASS,1=expectativa/calidadFAIL,2=servicio/modelo ausente
(PENDIENTE, no se intenta activarlo). `-Offline` usa fixture de transporte, **no es
evidencia del modelo**; `-Offline -FailExpectation` y `-TestUnavailable` prueban las
salidas fallidas. Tests inyectan transporte HTTP local en modo REAL sin sustituir
los codecs de proveedores, respuesta incompatible y excepción anterior a medir
órdenes (`orders=null`), audit de sentinel privado y limpieza de temp.

Run2: interpretación0,446–0,602s (total6,236s), writer0,597–1,733s (total36,997s),
turnos0,0069–2,521s (suma48,186s; excluye migración/preflight). La prueba comparte
recursos locales: no ejecutarla durante trabajo sensible. Es una muestra pequeña,
no garantía general ni autorización para configurar/reiniciar el bot.

Verificación: subprocess **7 passed in68.25s**; suite plain **910 passed in294.99s**;
Ruff `All checks passed!`; diff sin errores. Telegram privado sigue pendiente de
autorización y prueba independientes.
