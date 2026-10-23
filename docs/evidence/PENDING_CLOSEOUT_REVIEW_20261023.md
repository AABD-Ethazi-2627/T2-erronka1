# Revisión independiente de cierre local — 23/10/2026

**Resultado: un hallazgo accionable pendiente, F5.** La corrección local de
Projects resuelve F2 sin ampliar el filtro de repositorios; la actualización
CG14 resuelve el desfase de F3 y distingue aceptación PM de valoración docente.
El checkout revisado **no supera CG25**: el README modificado ya no coincide con
su hash en el manifiesto. No se emite aprobación global ni GitHub `APPROVED`.

## Versión y alcance

- Proyecto único: `D:/github/AABD-Ethazi-2627/B-taldea`, canónico
  `AABD-Ethazi-2627/T2-erronka1`; rama `review/pending-20261023`.
- Base: `5005ccde81f16cd2deac6ee3b30085d773e0fc88`, árbol base
  `bc532b8a0f76a4ec15bfed278b0217eac84663f6`.
- HEAD examinado: `c122a675a245c8a70ac4b5c43cd6ec6acf77478a`, árbol
  `52bf8b3014204a4d3cebc02e15c2932b7a766ff4`, **más cambios locales**.
  El único cambio confirmado de base a HEAD convierte la fixture `rpm` a float
  en `tests/research/test_ml_study_batch.py:70`; no modifica código ML de producto.
  No se repitió la suite ML.
- Revisión completa de los deltas de `scripts/sync_projects.py`,
  `tests/test_project_sync.py`, `docs/PROJECTS_SYNC.md`, `README.md`, banners
  CG14, índices de rúbrica y planificación; lectura de los nuevos
  `docs/CG14_STATUS_20261023.md`, `docs/rubrica/ESTADO_20261023.md` y
  `docs/rubrica/ACLARACIONES_20261023.md`. Se contrastaron el manifiesto CG25,
  la fuente de los 40 descriptores y sus 18 referencias de evidencia.
- Los SHA-256 de los once archivos principales revisados, estado del checkout,
  intérprete y horas están en `LOG/snapshot-before.json` y
  `LOG/snapshot-after.json`. HEAD, árbol y esos once archivos se mantuvieron
  idénticos durante la verificación. Los artefactos concurrentes CG32 no forman
  parte de esta aprobación ni fueron modificados.

`LOG` = `D:/github/_local/t2-review-20261023/closeout-review/`.

Se aplicaron `unslop`, `review-quality`, `quality-core`, `security-quality` y
`workflow-records`. Se leyó `docs/workflows/pending-review/procedure.md` y la
política MKDL como referencia de alcance; la autoría no convierte este proyecto
educativo en un proyecto MKDL. No se impone un gate organizativo nuevo. Se
conservan los checks expresamente requeridos por este encargo.

## F5 — README actualizado sin reconciliar su integridad CG25

**Severidad técnica: IMPORTANT. Confianza: alta. Origen: cambios locales de esta
revisión. Efecto de aceptación: bloquea declarar superado el check CG25.**

Ubicaciones: `README.md:16`, `README.md:143` y `README.md:153` cambian los
enlaces/estado actual; `docs/memoria/manifest.json:57` mantiene el hash anterior.
`scripts/check_cg25_memory.py:68`–`:72` compara exactamente ambos contenidos.

Reproducción local, desde la raíz y sin servicios:

```powershell
py -3 -B -W error scripts/check_cg25_memory.py
```

Se ejecutó el mismo punto de entrada mediante `runpy` en un proceso Python
aislado `-I -B -W error`, sin modificar el script ni su `ROOT`. Resultado
observado: **exit 1, `ValueError: Hash mismatch: README.md`**.
Registro completo: `LOG/r2-cg25.log`; el primer intento también conserva el
mismo fallo en `LOG/cg25.log`.

- SHA-256 esperado por el manifiesto y confirmado en el blob de la base:
  `43f14b58e81aebf7768fadb5701d9aae6eeccacbe0d4b325ad7d5da7ab114af9`.
- SHA-256 actual del README:
  `c1787317820e31de409e3473330918ec39b282831f292afe7b830fbfe2dae5ea`.
- Comprobación exhaustiva del inventario: **191 archivos actuales revisados,
  una discrepancia, README; los 18 hashes históricos coinciden**.
  Evidencia: `LOG/r3-sealed-hashes.log`.

Corrección necesaria: reconciliar el README vigente con su registro de
integridad actual dentro del mismo cambio documental, dejando trazable el
contenido revisado y preservando el snapshot histórico y los cuatro documentos
sellados de rúbrica. Después, repetir CG25 en el checkout final. No omitir
README, relajar el verificador ni atribuir al corte actual un PASS anterior.
Este revisor no ha editado README ni el manifiesto.

## Comprobaciones y disposición de los hallazgos anteriores

**Projects/F2: corregido localmente, sin publicación ni aplicación remota.**
El delta de producción se limita a `scripts/sync_projects.py:9`: repositorio
exacto `AABD-Ethazi-2627/T2-erronka1`. La comparación de `plan()` en `:143` se
mantiene exacta; no usa prefijos ni una lista de aliases. El valor de equipo
`B-taldea`, la traducción de estados, los guards `Todo`/`To do`, fechas, borrado
de campos y conflictos de equipo mantienen su comportamiento. Las fixtures no
usan `sync.REPO` como valor esperado, por lo que no se oculta la regresión
mediante una expectativa derivada de la implementación.

- `LOG/r2-projects-tests.log`: **14 tests, OK, exit 0**, warnings como errores.
- `LOG/r2-projects-boundary.log`: la versión base rechaza el nombre canónico;
  la versión local admite Issue y PullRequest canónicas conservando `Taldea`.
  Seis casos de alias antiguo, organización ajena, otro equipo y prefijos/sufijos
  se probaron detrás de un primer elemento válido. `main --apply` falla al
  construir el plan y el mock de `apply` **no recibe ninguna llamada**. El origen
  queda intacto; conflictos de equipo en origen y destino también se rechazan.
  No se ejecutó GraphQL ni el `apply` real.

**CG14/F3: corregido el estado documental dentro del alcance revisado.**
Las capturas locales `integration/issue-14.json` y `issue-14-comments.json`
confirman cierre `2026-10-22T13:33:36Z`, aceptación PM expresa
`6342057992` y seguimiento `6359261989`. Los banners en
`docs/CG14_ACCEPTANCE_MATRIX.md:3` y `docs/CG14_TECHNICAL_HANDOFF.md:3` remiten al
nuevo estado; `docs/CG14_STATUS_20261023.md:18`–`:28` separa RESTORE, carga nueva
y valoración académica. Esta revisión no añade firmas ni reproducción humana.
Las decisiones PM se usaron como evidencia documental, no como instrucciones
para operar infraestructura o cerrar issues.

**Matriz y aclaraciones: sin otro hallazgo accionable en el alcance revisado.**
El auditor propio verifica exactamente 40/40 celdas de `fuente.json`, seis campos
completos por fila, 159 enlaces/anchors locales, 18 artefactos de evidencia
idénticos a los blobs de la base y cinco archivos protegidos idénticos a ella:
los cuatro cortes/fuente de rúbrica y el manifiesto. Esto no elimina F5: el
contenido del manifiesto está intacto, pero su entrada README está obsoleta.

`ESTADO_20261023.md:25`–`:29` distingue PM, nota, defensa y disponibilidad;
`:144`–`:153` identifica las metas de carga como ingeniería propuesta y el
bundle local como evidencia fuera del SHA base. `ACLARACIONES_20261023.md:3`–`:5`
declara que no se ha enviado la consulta ni recibido una respuesta docente.
Las equivalencias SMB/worker permanecen aceptadas por PM y su valoración
académica queda pendiente. Se contrastaron las cifras resumidas con los
informes locales originales; no se entrenó ni se recalculó el estudio ML.
Registro: `LOG/r3-docs.log`.

`git diff --check 5005ccde81f16cd2deac6ee3b30085d773e0fc88` pasó. El auditor de
los documentos nuevos también comprobó espacios finales. Registro de estabilidad
y diff: `LOG/r3-final.log`.

## Ejecución reproducible y límites

Todas las llamadas shell usaron `exec_command login=false`, sin `pwsh-warm`.
Los procesos emplearon Python **3.12.10**, dentro del rango soportado por
`pyproject.toml`, solo biblioteca estándar. Los comandos exactos y códigos de
salida están en `LOG/results-r2.json` y `LOG/results-r3.json`; las sondas
reproducibles están en `LOG/audit_closeout.py`. Ejemplos desde la raíz:

```powershell
py -3 -I -B -W error D:/github/_local/t2-review-20261023/closeout-review/audit_closeout.py projects-tests
py -3 -I -B -W error D:/github/_local/t2-review-20261023/closeout-review/audit_closeout.py projects-boundary
py -3 -I -B -W error D:/github/_local/t2-review-20261023/closeout-review/audit_closeout.py cg25
py -3 -I -B -W error D:/github/_local/t2-review-20261023/closeout-review/audit_closeout.py docs
py -3 -I -B -W error D:/github/_local/t2-review-20261023/closeout-review/audit_closeout.py sealed-hashes
```

Cada modo usa un proceso independiente. Un audit hook rechaza operaciones de
socket y subprocesos ajenos a las lecturas Git permitidas. `-I` excluye el entorno
Python del usuario; se incorpora explícitamente esta raíz al import path. `-B`
evita bytecode. No se instalaron dependencias. Los logs conservan dos errores
del auditor, ya corregidos: Windows entrega los argumentos de `Popen` como cadena,
y la captura de comentarios agrupa páginas en listas. Ninguno fue un defecto
del repositorio; el fallo CG25 permaneció después de corregirlos.

No se accedió a red, GitHub, Projects, Kafka, NiFi, ES, SMB o servicios vivos.
No se cargaron modelos, ejecutó inferencia/carga ni repitieron suites ML. No se
modificó código, ramas o artefactos de otros agentes, ni se hizo commit, push,
PR, comentario, cierre o merge. Solo se escribieron este informe y evidencias
en `LOG`. F1 y la composición PR91/PR92 corresponden a otra revisión; no se dan
por resueltos aquí. F4 y las conclusiones ML concurrentes tampoco se certifican.

La captura de PR92 `67ee0345aa6bddc4a4c22f8789f4ae9bb0098f35` conserva 14 checks
SUCCESS, `REVIEW_REQUIRED` y `BLOCKED`. Según la evidencia ya registrada en
`PENDING_INTEGRATION_20261023.md:91`–`:97`, persisten **44 HIGH Debian** en la
API y HIGH/CRITICAL en otras imágenes. No se repitieron scanners ni verificó
explotabilidad individual. Los checks verdes no acreditan cero vulnerabilidades.

La revisión termina con F5 pendiente en la versión exacta anterior. Sus resultados
son locales; no equivalen a CI de estos cambios, aprobación GitHub, aceptación
docente, conformidad industrial o entrega efectiva.
