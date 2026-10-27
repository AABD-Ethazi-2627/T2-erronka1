# Revisión de pendientes

1. Verificar remoto canónico, revisión, cambios locales y worktrees antes de actuar.
2. Capturar PR e incidencias abiertas y relacionarlas con criterios y evidencias.
3. Separar código vigente, cambios de PR y registros históricos. Revisar por SHA.
4. Repartir código/pruebas, requisitos e integración sin solapar archivos editables.
5. Ejecutar los checks del proyecto y corregir defectos reproducibles dentro del
   alcance autorizado. Conservar los resultados completos fuera de los informes.
6. Registrar bloqueos materiales, acción siguiente y responsable de la decisión.
   Una prueba local no sustituye CI, integración, revisión humana o aceptación.
7. Revisar el diff final y dejar el estado recuperable. Publicar, fusionar, cerrar
   incidencias o intervenir en infraestructura compartida requiere la autoridad
   correspondiente; el procedimiento no la concede.

Los modelos se identifican por hashes del manifiesto y de los archivos. Un
reentreno con el mismo `model_version` no sustituye un bundle histórico sellado.
