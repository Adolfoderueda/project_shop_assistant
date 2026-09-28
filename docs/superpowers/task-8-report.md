# Task 8 — verificación integrada (2026-09-28)

Estado: **DONE_WITH_CONCERNS**. Sin operación bancaria, credenciales, inicio de sesión
real ni compras; ninguna tarea programada instalada por esta tarea.

## RED / GREEN

- RED: `.\.venv\Scripts\python.exe -m pytest tests/test_end_to_end.py -q` →
  `1 failed, 2 passed` (`IndexError` en `start_order`: el arnés difería también el alta
  y todavía no había línea). Corrección del **arnés**: dos ciclos para procesar el
  alta; un ciclo para dejar cantidad/compra en inbox antes del reinicio. Los primeros
  tres tests ya pasaban antes de endurecer este escenario: no se observó defecto de
  producción ni se atribuye ese RED a uno.
- GREEN: `.\.venv\Scripts\python.exe -m pytest tests/test_end_to_end.py -q` →
  `3 passed in 5.30s`.
- `.\.venv\Scripts\python.exe -m pytest -q` → `251 passed in 51.05s`.
- `.\.venv\Scripts\python.exe -m ruff check .` → `All checks passed!`.
- `.\.venv\Scripts\python.exe -m shop_assistant doctor` → exit 1,
  `Missing private configuration; run python -m shop_assistant configure locally`.
  No se creó ni solicitó el token del usuario en este entorno.

Los tests usan Telegram Update reales deserializados pero Bot y tienda en memoria;
ejercitan intérprete, SQLite, runtime, checkout y recovery reales. La tienda falsa
simula un ledger externo y permite el modo live **solo en tests**: confirma tras
respuesta perdida o devuelve unknown sin repetir submit. La compra seca deja la
lista intacta y envía aviso simulado después del reinicio, no recibo real.

## Revisión final y bloqueos

- Comprobado: un submit máximo ante respuesta perdida, `unknown` conserva líneas e
  intento incierto; resultado `simulado` no elimina la lista; los avisos no implican
  pago. La entrega de notificaciones Telegram es at-least-once y puede duplicar
  avisos si falla su confirmación, **no** acciones de compra.
- Las cuatro tiendas reales deshabilitan `prepare`, `submit`, `reconcile`,
  `live_verified`. Ofertas públicas parciales sin GTIN independiente/cotización
  completa/destino; no se ha validado el precio mínimo global ni un pago real.
- Fórmula sin cotejo de etiqueta física y referencia independiente: permanece
  deshabilitada; solo bloquea fórmula. Se requiere colaboración local del usuario.
- Faltan configuración privada y prueba desde Telegram propio del usuario; faltan
  inicio de sesión de Windows, consentimiento/instalación de tarea y verificación
  de disponibilidad 24/7. El modo actual no autoriza compra live. Nunca introducir
  contraseña ni código bancario en chat o logs; si se habilitan futuras conexiones,
  resolver el paso bancario manualmente en navegador visible y reconciliar.

Archivos: `tests/test_end_to_end.py`, `tests/fakes.py`, `README.md`,
`docs/setup.md`, `docs/store-capabilities.md`, `docs/superpowers/progress.md`,
`docs/superpowers/task-8-report.md`. Sin cambios en módulos de producción.

## Revisión round 1 — límite exacto de caída

- El RED inicial anterior (`IndexError`) era exclusivamente de preparación del test,
  **no** era un test conductual que fallase por un defecto de producto. La prueba
  original de respuesta perdida recorría el `except Exception` normal de checkout,
  que registraba `uncertain`: no cubría la caída tras el commit externo y antes de
  registrar la respuesta en SQLite.
- RED conductual nuevo: `python -m pytest
  tests/test_end_to_end.py::test_confirmed_order_is_not_repeated_after_crash -q`
  → `1 failed`: `assert len(interrupted) == 1`, observado `0`. El fake aún no llamaba
  al hook tras escribir su ledger. La prueba prepara la orden con inbox durable,
  cancela el worker **después** del commit externo mediante `CancelledError` (no
  capturado por `except Exception`), verifica que SQLite conserve intento incierto
  sin confirmación ni eliminación de línea y reabre componentes con la misma BD.
- GREEN focal: `.\.venv\Scripts\python.exe -m pytest tests/test_end_to_end.py -q`
  → `3 passed in 0.95s`. Se añadió al fake solo el hook después del ledger;
  recovery confirma un pedido externo tras reinicio y deja `submit_calls == 1`.
- Documentación local corregida: los adaptadores reales pueden quedar
  `requiere_intervencion` por cotizaciones incompletas; el aviso `simulado` del test
  no es promesa de recibo real ni de simulación completada para tiendas reales.
- Verificación final tras documentación: `.\.venv\Scripts\python.exe -m pytest
  tests/test_end_to_end.py -q` → `3 passed in 1.22s`;
  `.\.venv\Scripts\python.exe -m pytest -q` → `251 passed in 62.09s`;
  `.\.venv\Scripts\python.exe -m ruff check .` → `All checks passed!`.
