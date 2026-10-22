# Procedimiento de importación canónica

Alcance autorizado de esta entrega: implementar y probar sólo sobre fixtures
sintéticos/copias propias; no migrar históricos reales ni tocar servicios.

1. Verificar el head remoto de PR42 con `git ls-remote` y conservar SHA/tree de la
   base y candidato. Leer PR61/65, contratos y estado de rúbrica.
2. Revisar los requisitos de [entrada y rollback](../../SCORING_RESPONSE_IMPORT.md).
   No rellenar datos ausentes, no reasignar IDs y no interpretar referencias del
   operador como procedencia autenticada.
3. Preparar worktree aislado y directorios temporales/cachés propios. Conservar
   snapshots originales y comandos/códigos de salida; excluir rutas locales de
   los artefactos publicados. No cargar modelos de entrega ni train/test final.
4. Ejecutar `test_scoring_import.py`, `test_scoring_replay.py` y regresiones API,
   contratos y pipeline pertinentes. Los tests usan `unittest discover -s tests`,
   que incluye los helpers de tests en el path. Verificar crash/rollback, backup,
   conflictos, bytes/scored_at, 409/503, recibos y ACK; no deducir E2E externo.
5. Ejecutar Ruff 0.17.1 E/F/I/PLW1510 y formato, CG02, CG25, layout, lock frozen y
   auditoría de dependencias. Actualizar sólo hashes actuales de fuentes editadas
   en la memoria CG25; conservar íntegra su instantánea histórica.
6. Publicar draft contra PR42 mediante push normal; enlazar inmediatamente la PR.
   Capturar CI una sola vez, con el SHA devuelto. No lanzar CI manual, watcher,
   Copilot ni merge. Entregar SHA/tree, evidencia propia, límites y revisión padre
   pendiente.

Una ejecución futura sobre datos reales necesita su autorización, evidencia de
entrada íntegra y revisión de dry-run/restauración. Este procedimiento no la concede.
