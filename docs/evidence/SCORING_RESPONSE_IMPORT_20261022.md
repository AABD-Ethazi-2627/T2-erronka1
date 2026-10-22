# Importación de respuestas canónicas — evidencia propia

Base PR42 verificada en remoto antes de trabajar y antes de publicar:
`cc36beb49a17949c805f789b5aa3b4b568f5d4c6`. Implementación educativa no MKDL,
relacionada con PR61/65/72 e issues12/14/15/21. Revisión del padre pendiente.

La [CLI y su contrato](../SCORING_RESPONSE_IMPORT.md) exigen snapshots originales,
hashes, configuración completa compatible y evidencia explícita de identidad.
Validate es el modo predeterminado. Import usa backup nuevo para ledger existente,
SQLite FULL/BEGIN IMMEDIATE y una única transacción para el lote completo. El API
reproduce el BLOB original sin recalcular `scored_at`, manteniendo 409/503 y los
recibos antes de ACK del pipeline. No se reasignan IDs distintos entre orígenes.

## Pruebas y controles

Se ejecutaron 77 tests por entorno, incluidos 14 nuevos de importación, en Windows
CPython 3.11.9 y FedoraLinux-43/WSL CPython 3.12.15. Cada ejecución declara dos skips
de `test_api` por ausencia de bundle de modelo; no son passes. El resto usa dobles
deterministas, SQLite/archivo reales y HTTP local donde lo requiere la regresión.
No se entrena ni se carga el modelo de entrega. Las suites seleccionadas incluyen:

- Bytes originales con orden/espacios/UTF-8 y LF, `scored_at` anterior, restart API,
  cero llamadas a inferencia, 409 por payload/configuración y 503 no preparado.
- CLI en proceso separado, validate sin crear target/backup, reejecución sin
  escrituras, duplicados de lote, compatibilidad con ledger previo sin tabla auxiliar.
- Hash/configuración incompatibles, etiquetas prohibidas, retargeting, campos
  ausentes/desconocidos, JSON duplicado/no finito/profundo/oversized y UTF-8 inválido.
- Conflictos internos/contra ledger, backup existente que no se sobrescribe,
  restauración a otra copia, fallo tras inserción y fallo de commit con rollback.
- Proceso terminado con exit73 después de insertar y antes de commit; validate
  rechaza journal pendiente, import recupera con SQLite y el backup coincide con
  el estado original; retry final es duplicate.
- Corrupción de bytes importados/orfandad bloquea sin rescoring; corrupción de
  SQLite/esquema, WAL/SHM/journal en validate y WAL sin sidecars se rechazan.
- Regresiones de API/contratos, profundidad JSON, puente CG14, pipeline durable,
  recibos HTTP y archivo/ACK. No se modifica el consumidor de archivo.

Ruff **0.17.1**, reglas predeterminadas y selección E/F/I/PLW1510, formato completo,
CG02, CG25, layout y diff pasan. `uv==0.13.1 lock --check` pasa sin cambiar lock;
`uv audit --locked` informa 57 paquetes sin vulnerabilidades conocidas ni estados
adversos. Se conserva su aviso de comando experimental, sin ocultarlo.
La memoria CG25 conserva sus 18 hashes históricos y revisión humana pendiente.

Comandos reproducibles, con intérpretes frozen existentes y temporales/cachés propios:

```text
python -B -m unittest discover -s tests -p test_scoring_import.py -v
python -B -m unittest discover -s tests -p test_scoring_replay.py -v
python -B -m unittest discover -s tests -p test_api.py -v
python -B -m unittest discover -s tests -p test_archive_json_depth.py -v
python -B -m unittest discover -s tests -p test_cg14_scoring_bridge.py -v
python -B -m unittest discover -s tests -p test_cg14_durable_pipeline.py -v
python -B -m unittest discover -s tests -p test_durable_receipts_http.py -v
python -B -m unittest discover -s tests -p test_archive_consumer.py -v
python -B -m unittest discover -s tests -p test_contract_validation.py -v
ruff --version
ruff check .
ruff check --select E,F,I,PLW1510 .
ruff format --check .
python -B -m scripts.audit_cg02 --check
python -B -m scripts.check_cg25_memory
python -B scripts/check_repository_layout.py
uv tool run --from uv==0.13.1 uv lock --check
uv tool run --from uv==0.13.1 uv audit --locked
git diff --check cc36beb49a17949c805f789b5aa3b4b568f5d4c6
```

Los logs de las suites combinadas capturan warnings y unraisables durante discovery,
ejecución y `gc.collect(2)`. Los [logs y hashes](SCORING_RESPONSE_IMPORT_20261022/index.json)
registran ejecución propia; se sustituyen rutas absolutas locales y se normalizan
saltos de línea al publicar. Se
conservan hashes de originales y versiones portables. No son logs de CI.

## Incidencias corregidas y límites

El ejecutor inicial cortó a 60 s: se repitió con timeout acotado adecuado y logs
progresivos. Las primeras pruebas detectaron `fsync` sobre descriptor read-only en
Windows; se abrió el backup en `r+b`. El ensayo crash exigió permitir recuperación
nativa del journal sólo en import explícito. Ruff detectó líneas largas y SIM102;
se corrigieron sin relajar reglas. Fedora no interpretaba el gitfile Windows del
worktree manual: se fijaron `GIT_DIR`/`GIT_WORK_TREE` sólo en ese proceso, sin editar
metadatos compartidos. Las comprobaciones finales sustituyen esos intentos fallidos.

No se aplica ninguna migración histórica real, no se modifica modelo/datos de
entrega, train/test final, ML, lock, ES ingest PR74 ni grafo NiFi. No se operan
servicios compartidos, SMB/OT ni volúmenes Docker. No acredita carga, pérdida de
host/alimentación, HA, migración coordinada de archivo/worker/ES, E2E externo ni
aceptación humana. Los históricos incompletos o con IDs distintos siguen bloqueados
según el contrato; las referencias de procedencia las aporta el operador y no se
autentican automáticamente. Un API anterior no conserva los BLOB de replay.

Publicación: draft contra PR42, push normal, sin merge ni comentarios a terceros.
La captura única de CI del SHA publicado y la revisión del padre son fases
posteriores y se entregan separadas de esta evidencia local.
