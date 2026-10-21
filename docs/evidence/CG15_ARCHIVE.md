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
