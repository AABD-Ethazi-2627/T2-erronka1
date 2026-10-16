# Verificación de la actualización de issues

Comprobación del 16/10/2026. Esta revisión comprueba la definición del trabajo y la coherencia del tablero; no ejecuta los modelos, servicios, pruebas de integración ni acredita criterios docentes.

- 30 guías publicadas: las 27 issues existentes y CG28/#35, CG29/#36, CG30/#37.
- 40/40 celdas de descriptores avanzados de `docs/rubrica/fuente.json` asociadas a guías en `manifest.json`.
- Los 30 cuerpos de GitHub coinciden con las guías locales, transformando enlaces relativos en enlaces a la rama documental.
- Todas las issues tienen responsables y están en Project #2 y en el central #1.
- Dependencias nativas de GitHub presentes; grafo del manifiesto sin ciclos.
- Fechas de las 30 issues: 120 valores de Hasiera-data, Amaiera-data, Start date y Target date coinciden con el plan versionado; las dependencias terminan antes o el mismo día que sus sucesoras.
- La validación de fechas por API no acredita que la vista Gantt tenga seleccionados sus campos visuales. Configurar Date fields en la interfaz sigue siendo una comprobación distinta.
- Quitada la prohibición de FastAPI de CG16. Corregidos títulos de CG16/CG18/CG25 para reflejar el alcance actual.
- Enlaces locales y `git diff --check` correctos. No se ejecuta CI remota.

## Cómo repetir la comprobación

Leer las issues y sus `blockedBy`/`projectItems` mediante GitHub GraphQL o `gh`, comparar el cuerpo con cada guía de `manifest.json`, resolver los enlaces de `docs/` y contrastar las fechas con `docs/planificacion/PLAN_2026-11-06.json`. Para cobertura, unir los números de `criteria` del manifiesto y compararlos con los `row` de `fuente.json`; deben coincidir los 40, sin números ajenos.

Las tareas nuevas tienen estimaciones brutas y fechas objetivo, no capacidad validada. La revisión del esfuerzo restante y las dudas de la rúbrica con el tutor siguen pendientes. Abrir una issue no equivale a cumplir su criterio.
