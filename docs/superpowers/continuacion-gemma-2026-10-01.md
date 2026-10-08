# Reanudación — correcciones Gemma (01-10-2026)

Alcance: los dos defectos del handoff `continuacion-gemma-lista-2026-09-30.md`.
No repetir Tasks 1–4. Especificación: `specs/2026-09-29-lista-fichas-gemma-design.md`.
Worktree existente `feat/gemma4-local`, base `93b40d9`, limpio.
Baseline: 343 tests pasaron en 166,19 s.

## Plan y registro

- [x] Reproducir consultas genéricas compuestas en Conversation y Repository directo;
  corregir el criterio compartido sin bloquear nombres concretos.
- [x] Reproducir petición afirmativa con sufijo `por favor`; permitir solo ese sufijo,
  manteniendo rechazo de negaciones, condiciones, preguntas y nombres contaminados.
- [x] Suite completa, Ruff, diff check y revisión independiente de las correcciones.
- [x] Prueba Ollama con mensajes inventados y SQLite aislada; documentar calidad,
  tiempos y límites. No parar procesos ajenos para simular arranque en frío.

Pre-flight: ambos caminos de consulta usan `identifiable_product_name`; la corrección
de cortesía es independiente y conserva la igualdad exacta del producto del modelo.
Hipótesis: `disponibles` cuenta como identificador porque no está en el vocabulario
genérico; `por favor` se rechaza en cualquier posición, incluido el sufijo afirmativo.

Sin acceso a private/, Telegram, tiendas, checkout, activación, merge ni push.
Menor previamente diferido: duplicación de selección de fichas; fuera del alcance.

## Resultados

- Consultas genéricas: RED 12 fallos por backlog indebido (dos rutas, seis nombres);
  GREEN tras ampliar el vocabulario compartido de atributos/categorías. Tres nombres
  concretos siguieron generando pendientes correctamente.
- Cortesía: RED cuatro fallos (los cuatro prefijos afirmativos); GREEN tras eliminar
  únicamente el sufijo final ` por favor` antes de validar la petición/producto.
  Nueve casos adversos permanecen rechazados. Enfocados: **143 passed in 15.10s**.
- Suite completa: `.venv\Scripts\python.exe -m pytest -q` → **371 passed in 153.98s**.
  Ruff: **All checks passed!**; `git diff --check` sin errores (avisos LF/CRLF).
- Revisión independiente del diff desde `93b40d9`: sin hallazgos Critical/Important;
  el revisor ejecutó los dos módulos afectados, **137 passed**. Su observación menor
  sobre el registro incompleto se atiende con esta entrega documental ya planificada.
- Dos secuencias con Ollama real: consultar `prueba-gemma-2026-10-01.md`. Cortesía
  correcta y cero órdenes; primera carga 25,549 s, repetición caliente 0,448–0,801 s.
  Modelo confundió pregunta genérica con lista y propuso un alta condicional que
  el validador bloqueó. No se considera aceptación de calidad ni de Telegram.

## Decisiones de alcance y siguiente paso

- Revisión declinó juzgar Telegram/configuración/activación o rama completa: quedan
  pendientes, sin inferir permiso; coste de aceptarlo sin probar: fallo del bot privado.
- Revisión declinó garantizar fiabilidad general y cobertura lingüística abierta:
  mantener comandos/proveedor sin cambios; el vocabulario conservador no es análisis
  semántico universal. Coste de asumir lo contrario: respuestas erróneas o pendientes
  genéricos no cubiertos. Nuevos casos requieren pruebas/corrección separadas.
- Revisión no repitió suite/Ruff completos: la evidencia arriba es del ejecutor;
  no atribuirla al revisor. Coste de confundirlo: falsa verificación independiente.

Los dos fallos del handoff anterior están corregidos; no repetir estas tareas.
El primer intento de commit falló con `Author identity unknown`. El usuario
proporcionó después nombre y correo de autor; se configuraron solo en este
repositorio para reintentar el commit pendiente. No se cambió configuración global
ni se asumió identidad a partir de commits anteriores.
Antes de habilitar, acordar una fase de calidad para la clasificación genérica y la
respuesta de cantidad de la primera línea pendiente, repetir aceptación aislada y
solicitar autorización específica para Telegram. No merge/push/activación en esta fase.

## Seguimiento: atasco de permisos al probar Telegram

El usuario pidió interactuar por Telegram y después aprobó corregir la activación
lenta sin rebajar la protección. Se observó `model-local enable` durante más de
tres minutos con un hijo PowerShell ejecutando ACL; Ollama respondía sin modelos
cargados. Solo se contaron metadatos de perfiles/logs: 728 archivos y 236 carpetas
en perfiles. No se leyeron tokens, dirección, mensajes ni base privada.

- Causa: `_private_tree` iniciaba `whoami` y dos PowerShell por ruta, repetido por
  las cargas/guardado de configuración. Ahora hay un `whoami` y un PowerShell por
  árbol; se reutilizan los scripts de aplicación/lectura y se verifica cada DACL.
- Conserva propietario, FullControl exclusivo, protección contra herencia,
  herencia correcta en directorios y propagación cero. Preflight de todo el árbol
  antes de mutar, sin descender en enlaces/junctions; recheck por ruta en PowerShell.
  Informes incompletos, permisos incorrectos o fallos del comando bloquean la operación.
- RED real Windows: 12 PowerShell para seis rutas en vez de uno, y mutación del
  padre antes de rechazar una junction. GREEN con lectura ACL independiente.
- Revisión independiente: un Important por no comprobar propagación en el lote;
  regresión RED (no rechazaba `InheritOnly`) → GREEN al exigir propagación cero.
  También se corrigió UTF-8 en la lectura independiente del test con nombre Unicode;
  el código de producción recibe nombres en JSON escapado y devuelve solo un resumen.
- Verificación final: **379 passed in 93.07s**; Ruff limpio y diff check limpio.
- Benchmark aislado, sin Telegram/configuración del bot: 728 archivos y 236
  directorios de perfiles inventados; árbol **5,142 s / un PowerShell**. Enable
  completo de esa configuración temporal, comprobando Ollama local existente:
  **23,898 s / seis PowerShell**. No es un máximo ni medición del bot privado.
- La revisión no evaluó reemplazos concurrentes del sistema de archivos ni el
  bot privado: no se promete defensa por handles contra carreras TOCTOU ni
  aceptación de Telegram. No se arrancó/paró un bot, ni hubo merge/push/compras.

Próximo paso del usuario: reintentar `model-local enable` con la rama del worktree
y raíz original (ver `docs/setup.md`), arrancar un solo worker y probar `/lista`
y preguntas seguras. No enviar `/comprar`. Sigue siendo una prueba experimental.
