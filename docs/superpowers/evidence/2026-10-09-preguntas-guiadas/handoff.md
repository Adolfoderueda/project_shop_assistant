# Handoff — preguntas guiadas, aceptación bloqueada

Rama local `feat/guided-questions`; worktree `.worktrees/guided-questions`.
Código candidato: `b1a7601` (no merge/push/activación). Spec y plan aprobados;
ocho tareas ejecutadas con revisiones independientes. Revisión final: **NOT READY**.

## Verificación final del controlador

- Suite completa: **1.641 tests pasan en 518,81 s**; Ruff y diff sin errores.
- Verificador independiente v5: **rechaza aceptación**, exit1; source/probe hashes
  actuales coinciden. Conversaciones reales: acotadas **42/102**, seguridad **6/39**,
  libre general **0/24**; 351 pasos ejecutados, **381 no ejecutados**.
- 228 turnos modelo, 96 aclaraciones, 6 salidas inválidas; 45 selecciones de botones
  simuladas. Fallback/botones/candidato validado no cuentan como comprensión.
- Evidencia completa: [final-fixes-v5.md](final-fixes-v5.md). V4 fue inválida por
  decodificación UTF-8 incorrecta en generación de matriz, conserva datos y no se
  cuenta como aceptación. V5 preserva las expectativas originales.

## Bloqueos para continuar

1. **HIGH, seguridad:** Cancelar por callback autenticado no establece frontera del
   historial. Replays de selecciones anteriores pueden devolver destinatarios
   cancelados a la inferencia y crear una propuesta nueva desde una respuesta suelta.
   No se afirma escritura de líneas guardadas en esa reproducción. Falta regresión
   específica y reparación de procedencia/frontera para callback Cancelar.
2. **Calidad E4B:** todavía hay prosa en lugar de llamadas nativas, operaciones/foco
   incorrectos y conversaciones posteriores no ejecutadas. No relajar el decodificador.
3. **Cambio UX decidido por controlador:** después de caducidad hace falta Cancelar
   explícito antes de otra petición natural; nueve expectativas anteriores de reinicio
   en un solo turno siguen fallando. No es aprobación humana de ese cambio UX.
4. **Wheel:** recursos SQL ahora declarados y probados en fuente; falta verificar
   distribución instalada porque build/wheel/setuptools no están disponibles y no
   hay autorización para instalar dependencias.

Rama, worktree y ledger conservados por revisión no limpia. No se tocó la lista
habitual, configuración privada ni el worker Telegram experimental. No se comprobó
su estado actual. Un nuevo lanzamiento o migración privada necesita autorización
separada; `dry_run` no sustituye bloqueo de compras.

## Decisiones del controlador y coste si fueran incorrectas

En orden del ledger; no son solicitudes/aprobaciones humanas nuevas.

| Decisión | Motivo | Coste si incorrecta |
|---|---|---|
| Worktree hijo pese a aislamiento previo | No editar código del worker activo | Worktree local adicional |
| Generar briefs con PowerShell | Extractor solo reconoce Task, plan usa Tarea | Brief mal extraído |
| No elegir modelo explícito de subagentes | Restricción del harness, usuario no eligió modelo | Mayor coste heredado |
| Vincular reofertas a entrega real, consultas sin renovación | Preservar preguntas/TTL y autoridad | Regresión de botones/testigos |
| Hacer inerte fallback en controlador | Fallo del modelo no es selección | Regresión de controles textuales |
| Extender tarea7 al borde de escritura | Repositorio también promovía fallback | Regresión de compatibilidad/controles |
| Excluir solo rechazos validados del historial | No bloquear conversación ni fabricar selección | Contexto inseguro o denegación |
| No reutilizar destinatarios caducados | Caducidad es permiso de aplicación | Usabilidad o resurrección de alcance |
| Diagnóstico nativo local versionado, límites iguales | Aceptación real insuficiente | Tiempo extra de inferencia sin mejora |
| Recursos de migración distribuibles sin instalar | Manifest anterior no incluía SQL | Regresión de lookup de recursos |
| Reset explícito Cancelar/comando tras caducidad | No existe prueba independiente de petición nueva | Turno adicional y expectativas antiguas fallidas |
| Aparcar residual callback Cancelar, flag off y sin merge | Límite de única corrección/revisión final | Candidato inseguro si se activase |
| Aparcar calidad nativa sin más prompts especulativos | Preservar pruebas y decodificación estricta | Trabajo pendiente antes de bot usable |
| Aparcar verificación wheel sin instalar | No existe permiso para dependencias | Defecto de instalación aún no detectado |
