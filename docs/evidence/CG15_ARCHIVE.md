# CG15 — sink archive local, 21/10/2026

Issue [#15](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/15),
criterios Zereginak!G77 y G96. Implementación parcial verificada localmente;
revisor humano y fecha de aceptación: **pendientes**.

## Base y alcance

Comparados origin/main, PR38 y PR39–42. CG06 (`scripts/build_history.py`)
conserva CSV completos y Gold; no se duplica ni se cambia esa API.
Base elegida PR42 `feat/17-maintenance-planner`, SHA
`28a77543bfd67a36b96ddc2f4acc103b13f62c2e`: incorpora los campos obligatorios
`prediction_scope`, `temporal_prediction_enabled`, `score_semantics` que PR38
no exigía. El commit ajeno inicial `448bc45` queda en la referencia local
`preserve/cg15-parent-448bc45`, fuera de los commits publicados por este cambio.

## Contrato de consumo

Desde la raíz del repositorio, `uv sync --locked`; no hay dependencias nuevas.
`scripts.archive_consumer.consume(root, messages, ack)` recibe una secuencia
finita de `(delivery_id, kind, bytes)` y un callback. `kind` es telemetry o
prediction; los bytes son un objeto JSON conforme a los contratos existentes.
Bronze guarda exactamente los bytes recibidos, incluso JSON inválido. Rechazos
conservan referencia a Bronze, hash y motivo. Es un sink de mensajes normalizados;
no sustituye la captura Bronze de CSV crudos de CG05/06 ni normaliza CSV.

El adaptador Kafka futuro debe desactivar auto-commit, usar identidad global
`cluster/topic/partition/offset`, entregar offsets contiguos por partición y
hacer commit del siguiente offset únicamente en `ack`. NiFi debe usar una
identidad persistente y transferir a success solamente tras retorno correcto.
No se ha instalado ese adaptador, cambiado el flow ni contactado brokers.
Un error de ack requiere replay; no deshacer archivos ya comprometidos.

Identidad de telemetría: `(kind,event_id)`. Predicción:
`(kind,event_id,model_artifact_sha256,policy)`. El event_id recibido se valida,
no se recalcula: NiFi vigente lo deriva del hash de kafka.key. Un payload distinto
para la misma identidad se rechaza; incluso cambiar scored_at requiere revisión
de esa política de identidad, no sobrescritura silenciosa.

Parquet separado en `telemetry/date=YYYY-MM-DD/<identity-hash>.parquet` y
`prediction/date=YYYY-MM-DD/<identity-hash>.parquet`, usando fecha UTC del evento.
Columnas event_id/machine_id/timestamp y payload_json canónico íntegro: el JSON
mantiene tipos y campos del contrato sin mezclar esquemas entre modelos.
Un archivo por identidad es deliberadamente simple, no optimizado para volumen.
No usar machine_id como ruta ni como predictor temporal.

Un SQLite local con synchronous=FULL y BEGIN IMMEDIATE serializa escritores.
Se escribe en temporal, fsync, rename y fsync de directorios antes del commit;
solo después se llama ack. En crash previo al commit, replay concilia archivos
huérfanos comparando bytes. Los hashes de objetos comprometidos se verifican
antes de aceptar otro batch: corrupción bloquea sin ack ni rebaseline automático.
Temporales `.pending-*` de procesos muertos no se leen como datos; su limpieza
requiere procedimiento separado. Lectores deben consultar el ledger comprometido:
un glob directo puede ver archivos anteriores al commit.

## Criterio → artefacto → comando → resultado → límite

Comandos desde la raíz, ejecutados con Python 3.12.14 y lock existente:

| Criterio | Artefacto | Comando | Resultado observado | Límite/revisión |
|---|---|---|---|---|
| G77 Bronze, separación, particiones, replay | scripts/archive_consumer.py; tests/test_archive_consumer.py | `uv run --locked python -m unittest discover -s tests -p test_archive_consumer.py -v` | 5 tests OK; batch 3 = 2 guardados + 1 rechazado; replay 3; nueva entrega del mismo evento = 1 duplicado | Fixtures; revisión humana pendiente |
| G96 recuperación y ack | mismo test, subprocesos os._exit(73) después de escritura, antes/después de commit | mismo comando | Sin ACK antes del crash; reinicio deja 3 entregas, 2 eventos y 2 Parquet; disco/ack fallidos recuperables | Terminación de proceso, no corte eléctrico ni broker real; revisión pendiente |
| Compatibilidad CG06 | tests/test_history.py | `uv run --locked python -m unittest discover -s tests -p test_history.py -v` | 2 OK | CSV congelados |
| Contratos vigentes | tests/test_contract_validation.py | `uv run --locked python -m unittest discover -s tests -p test_contract_validation.py -v` | 1 OK | No prueba semántica física |
| Retención sin rebaseline | tests/test_retention_recovery.py | `uv run --locked python -m unittest discover -s tests -p test_retention_recovery.py -v` | 2 OK | Sin SMB/servicio compartido |

Contabilidad por llamada: sent = stored + rejected + duplicate + replay.
Ledger deliveries guarda los resultados nuevos; events cuenta identidades únicas.
No se promete exactly-once. Es procesamiento con replay y sink local idempotente,
sujeto a filesystem POSIX local, fsync fiable, SQLite intacto y IDs estables.
No se ha probado SMB/NFS, pérdida de disco, clúster, carga sostenida ni integración
NiFi/Kafka real. No hay despliegue, merge, cierre de issue ni aprobación humana.
CG21 puede reutilizar este contrato/resultados; sus módulos de pruebas no cambian.

## PR46: recuperación de enlaces de directorio (21/10/2026)

Hallazgo P1 verificado sobre `179436348e96a35dfe9b5fe08376dd8f4fb84d19`:
la existencia de un directorio tras interrupción no prueba que su entrada en
el padre se sincronizara. La regresión inyecta una excepción inmediatamente
después de mkdir, antes de fsync del padre, en ancestro, raíz y Bronze. Antes
del arreglo: 7 tests ejecutados, 4 fallos (tres subcasos y fallo de fsync sin
bloqueo de ACK). Después: 8 tests de archivo OK, incluyendo límites de ruta.

`mkdir` recorre también directorios existentes y sincroniza cada padre antes
del ACK. No se detiene en el primer ancestro existente: ese ancestro también
puede proceder de una ejecución interrumpida. Resuelve rutas relativas,
componentes `..` y symlinks, y termina en la raíz del filesystem. Esto añade
fsync por profundidad en cada escritura; errores de permisos/fsync de cualquier
ancestro abortan sin ACK. Se presupone jerarquía de rutas estable, sin cambios
concurrentes de symlinks/montajes; no es una frontera de seguridad de rutas.

Validación local final, Python 3.12.14, lock sin cambios:

- `uv run --locked python -m unittest discover -s tests -p test_archive_consumer.py -v`: 8 OK.
- Mismo comando con `test_history.py`: 2 OK; `test_contract_validation.py`: 1 OK;
  `test_retention_recovery.py`: 2 OK. Total pertinente: 13 tests OK.
- `ruff check scripts/archive_consumer.py tests/test_archive_consumer.py`: OK.
- `ruff format --check scripts/archive_consumer.py tests/test_archive_consumer.py`: OK.

Pruebas deterministas de orden/fsync y terminación de proceso, no evidencia de
corte eléctrico real, garantías del hardware ni filesystem remoto. Adaptadores
NiFi/Kafka, CI remoto y nueva revisión siguen pendientes. Sin merge ni cierre.

## PR46: integración con la base actual y compatibilidad Parquet (21/10/2026)

Integración normal de `feat/17-maintenance-planner`, base verificada por
`git ls-remote`: `5c14df391f0e93ad27092bc83070d145e4fb8f41`, árbol
`e3bc75475954f766243290e751fd498b18dfb634`, sobre el head anterior de PR46
`343d7f0e3d75c2df12c6f319f9f0c9cadcdd65fa`. El merge local reproduce un único
conflicto en `docs/rubrica/SEGUIMIENTO.md`: se conservan las actualizaciones
de CG19 y las referencias de CG15 en G77/G96. Las correcciones de Gold,
sus pruebas, dependencias y workflows se conservan idénticos a la base.

La conciliación del archive comparaba una nueva codificación Parquet con los
bytes existentes. Dos regresiones nuevas fallaron antes del arreglo: duplicado
con otra codificación válida y recuperación de un huérfano previo al commit.
Ahora se compara esquema y valores, conservando los bytes existentes si son
equivalentes. La comprobación inicial de hashes comprometidos sigue intacta:
no se rebaselinea corrupción ni se emite ACK ante diferencias de esquema o datos.
Se mantiene el orden fsync → commit → ACK y la API pública del consumidor.

Validación ejecutada en **FedoraLinux-43 explícito**, sin servicios compartidos,
modelos de entrega, conjunto final ni descargas de dependencias:

- Python 3.11, `tests/run_strict_resources.py`: 184 pruebas por pasada, dos
  pasadas; 0 fallos/errores/avisos/unraisables. Seis omisiones por prerrequisitos:
  tres sin bundle API local y tres sin Elasticsearch de integración configurado.
- Python 3.11 y 3.12, runner estricto sobre copias idénticas de los cinco módulos
  archive/history/retention/contracts/columnar: 18 pruebas por pasada y versión,
  dos pasadas, 0 omisiones/fallos/errores/avisos/unraisables. Incluye 11 pruebas
  archive, conservación Gold, corrupción, crash y fallos de disco/ACK.
- Fixtures sintéticas escritas con PyArrow 18.1.0 y leídas con 23.0.1, y sentido
  inverso: replay comprometido, duplicado y recuperación previa al commit OK;
  cuatro Parquet por sentido conservan exactamente sus bytes y hashes.
- Ruff 0.17.1 global y selección `E,F,I,PLW1510`, formato global (195 archivos),
  `git diff --check` desde ambos padres completos, validadores de contratos,
  `audit_cg02 --check`, layout y `uv lock --offline --check`: OK.
  Se corrigieron B023 en el test nuevo y E501 heredado del SQL, sin supresiones.
- `uv audit --locked --python-version 3.11 --output-format json` con uv 0.13.1:
  exit 0, 51 paquetes auditados, sin vulnerabilidades conocidas según esa consulta.
  Conserva dos avisos de uv sobre comando/formato JSON experimentales; no son
  avisos de las pruebas ni vulnerabilidades. El lock no cambia.

Evidencia de ejecución, salidas completas, intento interrumpido por timeout,
regresiones negativas y fixture hashes: `.git/pr46-evidence/` del clon aislado
`D:/github/_local/t2-babysit-20261021/pr46-conflict`. La documentación de esta
sección y la partición del literal SQL no cambian comportamiento tras las pruebas.
Los límites Windows previamente reportados (12 errores POSIX y aviso loky WMIC)
no se han revalidado ni resuelto aquí. Revisión independiente, CI del nuevo head,
aceptación humana y transporte real siguen pendientes. Sin merge de PR46 ni
cierre de issues; la integración de base en su rama no equivale a aceptación.
