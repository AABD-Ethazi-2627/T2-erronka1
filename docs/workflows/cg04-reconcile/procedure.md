# Reconciliar CG04 sin evaluar el test excluido

1. Verificar las cabezas de PR42/43, el remoto y la base elegida; trabajar en
   clon y rama propios. No modificar las ramas existentes ni los bundles.
2. Leer carga, preparación, notebook, locks, API y empaquetado. Comparar índices
   del split activo con el ejercicio 80/20, sin fit ni predicciones sobre AI4I.
3. Reutilizar `scoring.scope.load_training_source`, `split_development` y el
   pipeline activo. Mantener ejercicio, métricas y artefactos separados del v4.
4. En FedoraLinux-43, sincronizar el lock activo con Python 3.11 y uv 0.13.1.
   Ejecutar `python -m scripts.cg04_preparation` y los tests de reconciliación,
   preparación, alcance, contratos y rechazos API. Las fixtures de entrenamiento
   deben ser sintéticas; no lanzar los experimentos ni el empaquetado real.
5. Ejecutar el notebook de índices, el audit CG02, el layout y `git diff --check`.
   Guardar versiones, comandos, códigos, skips y límites. Revisar el diff.
6. Publicar solo draft contra la base deliberada; vincular la URL completa.
   Registrar SHA y checks observados sin CI manual ni watcher hijo. Entregar al
   padre para revisión independiente; no merge, cierre ni despliegue.

La suite completa de la base incluye fits sobre filas reales sin aplicar la
exclusión y la CI genera modelos. No ejecutarlos como sustituto de estos checks
en una tarea que prohíbe reentrenar/evaluar el test. Distinguir los checks locales
ejecutados de los que la plataforma pueda lanzar automáticamente al abrir PR.
