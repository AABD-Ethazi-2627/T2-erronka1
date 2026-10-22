# PR74 — reparación de revisión R2

Proyecto educativo T2-erronka1, no MKDL. Worktree autorizado existente:
`D:/github/_worktrees/t2-es-ingest-20261022`, rama `feat/g68-es-ingest-20261022`.
Inicio limpio head `0a0bc55b94a7deaf39ddf923d9508ac89b4985b6`, árbol
`4c6800c440123b4067778d6526e3248f88adc7aa`; base viva PR42
`cc36beb49a17949c805f789b5aa3b4b568f5d4c6` comprobada por gh.

1. Revalidar worktree/PR/base, leer revisión e informe del autor y enlazar PR74.
2. `bootstrap.py` construye `red_probes.py` a partir del arnés de revisión,
   limitado a un ES propio con etiqueta `t2.review=g68-pr74-fix-r2-20261022`,
   imagen local ES9.5.4 sin pull, loopback aleatorio y binds D:. Guarda F1 HTTP400
   y las dos aserciones F2 falsas en `red-result.json`; elimina su ID exacto.
3. Ejecutar `red_assertions.py` sobre las respuestas HTTP previas: debe terminar
   con exit1, tres fallos esperados. No confundir ese resultado con un gate verde.
4. Corregir README principal y enlazar procedimiento de pipeline GET/PUT antes
   de template. Buscar todas las rutas con `rg index-template|_index_template`:
   README principal era la única instalación activa incompleta; README ES,
   verify_es_ingest_pipeline y verify_durable_pipeline ya instalan pipeline primero.
   Evidencia fechada e históricos no son instrucciones de instalación activas.
5. Corregir verify_elasticsearch_contract: fixture construida de contrato en vez
   de entrenamiento/API; guard exige script_exception, causa y motivo exactos;
   mapping exige strict_dynamic_mapping_exception en índice sin pipeline, scope
   raíz/source específico, ausencia de rechazados y conservación del documento.
6. `run_checks.py live1`: ambos verificadores completos; `setup-and-contract-final`:
   instalación documentada desde ES limpio y repetición del verificador cambiado
   tras reforzar aserciones. `run_checks.py gates-final`: Ruff0.17.1/format,
   seis tests sin ML, export, CG02, CG25, layout, lock offline y auditoría.
7. Publicar un informe R2 y registros NUEVOS, conservar todos los archivos de
   G68_ES_INGEST_20261022 sin modificación. Actualizar solo hashes actuales CG25,
   con hashes y snapshot históricos intactos; añadir hashes de evidencia nueva.
8. Inspeccionar diff, fuentes protegidas e inventario Docker completo. Commit y
   push normal a PR74, sin merge ni comentarios. Una captura de CI del SHA final,
   sin polling/watch/manual CI/Copilot. Entregar SHA/tree y revisión padre pendiente.

Todo temporal, caché nueva y evidencia propia está aquí en D:. Se reutiliza el
intérprete frozen existente del autor, sin escribir en su entorno. No SMB/OT,
Kafka viejo, migración canónica, bundle ML ni test final.
