# Revisión acotada de hashes y fixture — 23/10/2026

**F5 resuelto localmente, con confianza alta. Sin nuevos defectos reproducibles
en las dos correcciones examinadas.** CG25 pasa con 40 criterios, 90 enlaces y
anchors locales, 191 hashes actuales y 18 históricos. La corrección de la
fixture conserva el control exacto de bytes. Este dictamen no acredita CI del
candidato, GitHub `APPROVED`, merge ni aceptación humana o docente.

## Versión y alcance

- Checkout: `D:/github/AABD-Ethazi-2627/B-taldea`; proyecto educativo canónico
  `AABD-Ethazi-2627/T2-erronka1`; rama `review/pending-20261023`.
- Base contrastada: `5005ccde81f16cd2deac6ee3b30085d773e0fc88`, árbol
  `bc532b8a0f76a4ec15bfed278b0217eac84663f6`.
- HEAD revisado: `55cfd63d71c848acbd7647eab7b69bec768b646d`, árbol
  `4e9829c0af5603a9cee1f06d53b42bc7262d7867`, **más los cambios locales
  identificados por SHA-256 en `LOG/snapshot-before.json`**. El SHA de HEAD por
  sí solo no identifica el manifiesto reconciliado ni el README revisados.
- Fuente PR92: `67ee0345aa6bddc4a4c22f8789f4ae9bb0098f35`.
- Corrección del fixture: `0ab771d7867315d2aa85776cb16b1bf7bfdbb048`.
  La pertenencia de la base, PR92 y esta corrección a HEAD se verificó mediante
  `git merge-base --is-ancestor`.

`LOG` significa `D:/github/_local/t2-review-20261023/hash-review/`.
Se aplicaron `unslop`, `review-quality`, `quality-core` y `workflow-records`,
reutilizando `docs/workflows/pending-review/procedure.md` y el informe anterior
`docs/evidence/PENDING_CLOSEOUT_REVIEW_20261023.md`. No se delegó trabajo. No se
reabrieron F1–F4 ni se reauditaron PR91, PR92 o el estudio ML completos.

## F5 — Reconciliación verificada

**Severidad técnica original: IMPORTANT. Disposición: RESUELTO en el estado
local identificado. Confianza: alta.** El bloqueo de F5 para declarar superado
CG25 queda levantado exclusivamente para este contenido comprobado.

La comprobación independiente no ejecutó `reconcile-cg25.py`, que escribe el
manifiesto. Se leyó su implementación y se contrastó el resultado con los blobs
Git y los archivos actuales, sin confiar en los booleanos del recibo.

Evidencia reproducible: `LOG/reconciliation.json`, `LOG/reconciliation.log`,
`LOG/manifest-base-to-current.diff` y `LOG/README-base-to-current.diff`.

1. El manifiesto previo del recibo corresponde exactamente al blob de la base
   y al de HEAD: SHA-256
   `1375b800f44373c4f8db8ef29e82ea9d481f527a543a71c0431e0af9dd130fa2`.
   El manifiesto local reconciliado tiene SHA-256
   `80e1dc0ad02995f82d2f94ae0ab9d6c4ff74c8bb5ccc9a3a71a3cdabe21e7830`.
   El recibo tiene SHA-256
   `deda0c4b008451784bdf68ec6eb0cb4827c8202009ecaf54b321f5066d725c85`.
2. Permanecen exactamente las mismas **191 rutas, en el mismo orden**. No hay
   claves JSON duplicadas. Cambian exactamente ocho valores de `files`:
   `README.md`, `pyproject.toml`, `uv.lock`, `scoring/requirements.txt`,
   `scripts/check_repository_layout.py`, `tests/verify_durable_pipeline.py`,
   `tests/verify_es_ingest_pipeline.py` y
   `tests/verify_elasticsearch_contract.py`. Las otras 183 entradas y sus bytes
   actuales conservan sus hashes anteriores.
3. Los siete archivos distintos del README coinciden **byte a byte**, mediante
   `git show`, con PR92 en el SHA indicado. Las ocho entradas del recibo
   contienen exactamente el hash anterior de la base y el hash actual observado;
   no hay rutas omitidas, adicionales ni repetidas.
4. `docs/memoria/manifest.json:57` registra ahora para README
   `a0a963692a18269ad73f89abb997ca4e8456a11322193981e7680925b7d17807`.
   Su delta respecto de la base recoge las dependencias del laboratorio, enlaces
   al estado/revisión del 23/10 y la distinción entre aceptación PM de CG14 y
   tareas pendientes. No se exige que README sea idéntico al de PR92: incorpora
   también la reconciliación documental local, cuyo diff se conserva.
5. Se comparó el objeto completo del manifiesto: además de esos ocho hashes,
   solo cambia `evidence_status` y se añade `current_reconciliation`
   (`docs/memoria/manifest.json:236` y `:246`). El primero declara reconciliación
   local y aceptación humana pendiente; el segundo vincula base, HEAD y recibo.
   `historical_snapshot`, `active_scope`, `source_template`, `human_review`,
   `base_commit` y el resto de metadatos conservan exactamente sus valores.
6. Se verificaron de nuevo los **191 hashes actuales y los 18 históricos**. Los
   históricos se calcularon sobre los blobs de su propio `base_commit`, sin
   presentarlos como ejecución vigente. `human_review` sigue en `pending` y las
   40 filas de la memoria siguen en `Pendiente`.
7. `scripts/check_cg25_memory.py` es idéntico en bytes al de `5005cc`; SHA-256
   `8b6a7d2d627502be154c0303f316e945eb6842c3ca545eb42532f0eb30aa02e7`.
   Se conservan la comparación SHA-256 de bytes, el recorrido histórico, la
   cobertura de criterios, los enlaces, la comprobación de ancestro, el alcance
   ML y el estado humano. `docs/memoria/README.md` también es idéntico a la base.

No se observó relajación del verificador ni conversión de una evidencia
histórica o una aceptación pendiente en PASS. El recibo conserva
`gate_result=pending_execution_after_reconciliation`: documenta su momento de
creación. El PASS de esta revisión procede de la ejecución posterior guardada
en `LOG/cg25.log`, no de una modificación de ese campo.

Los cuatro documentos sellados de rúbrica son idénticos en bytes a `5005cc`:

- `docs/rubrica/SEGUIMIENTO.md`:
  `32a6a76a3793568f8e7dd4cd5c8a5bad658267bab17a4603718ab46424d7a330`.
- `docs/rubrica/ESTADO_20261022.md`:
  `a9914fd57a1ac2e0ec2ff758e849c22f1556b64b22cccc8072879d8e1820ea60`.
- `docs/rubrica/OBJETIVOS_Y_ETAPAS.md`:
  `9328ed0be2628ea7cc2bdd66b9aa59002c1002b1982b77a1e0a02cb4e8ccf9dc`.
- `docs/rubrica/fuente.json`:
  `d84d493e34479cfdbaac54d2fb53e7024fcad7b6c772bf04b0fa26572f0de2e2`.

## Fixture de exportación — comparación exacta preservada

`tests/test_dependency_runtime.py:39` coincide con el blob de `0ab771d`.
El delta completo de ese commit sobre este archivo cambia únicamente
`path.write_text(render(ROOT))` por
`path.write_bytes(render(ROOT).encode("utf-8"))`.

La comparación de producto sigue en `scripts/export_runtime.py:38`–`:40`:
codifica la exportación en UTF-8 y compara `target.read_bytes() == expected`.
El exportador es idéntico en bytes al de PR92. La corrección de la fixture
escribe los bytes que el contrato exige; no introduce normalización de saltos
de línea, lectura de texto ni tolerancias en el verificador. La escritura usada
por el propio exportador en `:55` emplea igualmente `write_bytes`.

Se ejecutó solo el método
`test_drift_and_missing_file_fail_without_rewriting_the_file`, con la salida de
`uv export` sustituida por un `CompletedProcess` determinista formado a partir
del archivo local de requisitos. Se ejercitaron las funciones reales `render`
y `check`, sin lanzar `uv`:

- Versión corregida: **1 test, OK**.
- Versión anterior al commit, compilada en memoria: **1 test, un fallo esperado**
  en `assertTrue(check(ROOT, path))`, sin errores del auditor. En Windows,
  `write_text` traduce LF a CRLF; el control de bytes rechaza esa fixture.
- Sondas sobre `check`: acepta UTF-8 exacto; rechaza traducción CRLF, BOM UTF-8,
  un byte eliminado, uno añadido y uno alterado. En los cinco rechazos deja
  intactos los bytes escritos. También se comprobaron archivo ausente sin
  creación y UTF-8 con caracteres no ASCII frente a UTF-16.

Evidencia: `LOG/byte-control.json`, `LOG/bytes.log`, `LOG/fixture-fixed.log` y
`LOG/fixture-previous.log`. El fallo de la versión anterior es una reproducción
controlada de la regresión corregida; no es un fallo del candidato vigente.

## Ejecución, estabilidad y límites

Python **3.12.10**, dentro del rango `>=3.11,<3.13` del proyecto; solo biblioteca
estándar, procesos aislados `-I -B -W error`. Todas las llamadas shell usaron
`exec_command login=false`, sin `pwsh-warm`. El runner PowerShell se ejecutó
mediante `agent-ps`, sin perfiles. El auditor rechaza sockets y subprocesos
distintos de las lecturas Git permitidas. Los temporales de las sondas se crean
y retiran exclusivamente dentro de `LOG`.

Comandos reproducibles desde la raíz; `LOG/results.json` conserva argumentos,
horas y códigos de salida reales:

```powershell
agent-ps D:/github/_local/t2-review-20261023/hash-review/run_checks.ps1
py -3 -I -B -W error D:/github/_local/t2-review-20261023/hash-review/audit_hash_review.py final
```

El runner ejecutó `snapshot`, `reconciliation`, `cg25` y `bytes`: **exit 0 en
los cuatro modos**. `cg25` ejecutó mediante `runpy` el punto de entrada original
de `scripts/check_cg25_memory.py`, sin sustituir `ROOT` ni sus comprobaciones:

```text
PASS: 40 criteria, 90 local links/anchors, 191 current and 18 historical hashes
Documentation only; no technical reruns, CI result or human acceptance asserted.
```

`LOG/snapshot-before.json`, `LOG/snapshot-after.json` y `LOG/stability.json`
registran HEAD, árbol, rama y los 18 archivos del alcance por hash. Los ocho
archivos reconciliados, manifiesto, recibo, fixture, exportador, verificador y
documentos sellados permanecieron iguales durante los checks.
`git diff --check 5005ccde81f16cd2deac6ee3b30085d773e0fc88` pasó, **exit 0**.

Durante la revisión se observaron únicamente estos cambios concurrentes de
resultados/documentación fuera de las dos correcciones:

- `docs/evidence/FINAL_VALIDATION_20261023.json`.
- `docs/workflows/pending-review/runs/20261023.md`.
- `docs/workflows/pending-review/state.md`.
- `docs/workflows/pending-review/tasks.json`.

Sus hashes observados y transiciones de estado están registrados en los
snapshots y `stability.json`; no se revisa ni se certifica aquí su contenido.
Los cambios locales CG32 y `PENDING_BUNDLE_20261023.json` ya presentes tampoco
forman parte del dictamen. La única escritura propia en el checkout es este
informe; los scripts, logs y temporales están en `LOG`.

No se usó red ni se contactaron servicios. No se ejecutó exportación real con
`uv`, entrenamiento, inferencia, carga ni suites principales; estas últimas
corresponden al padre sobre su candidato final. No se modificaron fuentes,
manifiesto, recibo, ramas o evidencias de otros agentes, ni se hizo commit,
push, PR, comentario o merge. Las comprobaciones solo acreditan la integridad
documental y el comportamiento de bytes descritos; no cierran otros hallazgos,
validación de infraestructura, CI, entrega ni aprobación humana.
