# Aceptación real después de la revisión final — run3

Base de código: `84430e1` (correcciones sobre `b59a090`). **REAL PASS**, exit0.
La evidencia nueva es [run3 JSONL](natural-dialogue-real-2026-10-08-run3.jsonl);
run1/run2 y su informe histórico permanecen intactos, sin sobrescrituras.

Se ejecutó el script existente, sin modificar expectativas ni sustituir proveedores:

```powershell
$env:PYTHONPATH=$PWD.Path
powershell.exe -NoProfile -File scripts/Probe-NaturalDialogue.ps1 -Python ../../.venv/Scripts/python.exe
```

Gemma `gemma4:e2b` real, servicio loopback existente; ambas llamadas reales:
12 interpretaciones compatibles (`add`, `increment`, `list`), 33/33 drafts
aceptados, 0 respaldos; 34/34 pasos, cero órdenes, limpieza temporal confirmada.
Interpretación total7,043s, writer56,384s, turnos76,927s. Cada registro conserva
input, propuesta, estado/filas, snapshot, respuesta, HTTP raw y tiempos.
El reloj avanza, incluido replay y caducidad900s, igual que en run2.

Las correcciones finales tienen pruebas SQLite temporales adicionales:
- Incrementos rechazados (condición, cantidad no admitida, ambigüedad) no se
  convierten en altas literales; una propuesta válida anterior se conserva.
- Saludos no llaman `list_lines` ni `_lines`, no cambian el JSON persistido ni
  timestamps tras cambios externos de revisión/reserva o caducidad. El siguiente
  `sí` sigue rechazado por las guardas originales, sin mutación.
- `/anadir más arroz`, nombres entre comillas y `Arroz Más` conservan alta literal.

Verificación: **150 focused passed**, suite plain **935 passed in282,13s**,
Ruff limpio, `git diff --check` limpio (solo avisos normales LF/CRLF de Windows).
Estos casos nuevos son evidencia offline, no se atribuyen al modelo real. El probe
real conserva las secuencias sintéticas aprobadas y sus guardas independientes.

No se leyó DB/config privada, ni Telegram, tiendas, compras, instalación, descarga,
reinicio, control de procesos, ACL, unload, merge o push. Redacción acotada por
acto/variantes, no prosa factual libre. Muestra pequeña, no garantía de calidad
general; aceptación de Telegram privado sigue separada y no autorizada aquí.
