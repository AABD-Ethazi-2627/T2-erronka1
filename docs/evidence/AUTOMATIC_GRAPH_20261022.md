# CG13/14/15: implementación automática revisable — 22/10/2026

El [export y protocolo nuevos](../CG14_AUTOMATIC_GRAPH.md) hacen que NiFi
programe el consumidor Kafka del producto y recupere sus ciclos. No hay driver
externo que confirme offsets ni ConsumeKafka nativo en este export. La elección
requiere revisión del padre y aceptación del alcance de issue14. No se declara
terminado ni aceptado el grafo de la rúbrica.

Base inicial cc36beb; PR74 incorporada en ac4cf855. Tras integrarse PR75 y cerrarse
PR42, se incorporó main `1e161dd1588e34402066e4090f628681f1393860`, tree
`035f8a82e81f0ec88a2312f02fc450a0c5e647cb`, mediante merge normal local
`7a85b00913d0110b57c480a9cc73da240b1d2ac1`, sin conflictos. La nueva PR apunta
a main. No hay delta funcional en API/ledger/importador ni guard/template ES.
CG25 solo actualiza el hash del launcher Kafka modificado; conserva otros sellos.

## Fuente, export y runtime

Se reutilizan Pipeline, contratos, IDs de ocurrencia, respuesta canónica,
archivo/recibos y adaptador de commit explícito. Se añaden configuración
automática inmutable, exclusión antes de construir el consumidor, preflight del
guard final ES instalado y mapping estricto, y contabilidad por jobs únicos.
El preflight admite solo las dos fechas lifecycle enteras añadidas por ES9.5;
el resto del guard debe coincidir con el export. No instala ni modifica ES.

El export de producto está DISABLED. Sus cinco processors y ocho conexiones
se importaron y validaron realmente en NiFi2.12. El catálogo observado fija
tipos/NAR/relaciones en la fixture de regresión. GenerateFlowFile crea triggers;
ExecuteStreamCommand ejecuta el launcher; los restantes retienen salida y
diagnóstico, incluidos fallos. El [export de runtime](AUTOMATIC_GRAPH_20261022/runtime-export.json)
se conserva separado de la fuente y de las importaciones fallidas.

Filebeat9.5.4 leyó archivos sintéticos locales propios; Kafka3.7.2, NiFi2.12,
HTTP canónico con SQLite y modelos dobles en memoria, CG15/Parquet y ES9.5.4
fueron reales. La configuración Filebeat se copió del producto cambiando solo
paths/hosts/topic. Cada archivo tuvo huella distinta y las filas iguales dentro
del mismo archivo conservaron ocurrencias distintas. No SMB/OT compartido,
modelos de entrega, entrenamiento ni testfinal en este laboratorio.

## Ensayos ejecutados

- Normal: cinco mensajes, cuatro guardados y un CSV rechazado durable; offset5,
  ocho recibos CG15 y cuatro documentos ES. Ningún commit del harness.
- HTTP409/413 inyectados: offsets5/9 retenidos y recuperación automática a9/13
  al corregir el endpoint, sin descarte terminal. HTTP422: cuatro rechazos con
  raw/cuarentena antes de offset17, sin Prediction ficticia. HTTP503: offset17
  retenido y recuperación a21. Los códigos inyectados prueban transporte/ruteo;
  los tests focales HTTP verifican además la validación real del API.
- Respuesta perdida después del commit API: offset21 retenido, una inferencia
  para el evento incierto y respuesta canónica reutilizada al recuperar hasta25.
- Guard final ausente: bloqueo antes de consumir; restaurarlo permitió avanzar
  a29. No se desactivó el guard para fabricar un resultado positivo.
- ES403 real: respuesta y archivo ya guardados, offset29 retenido. Reinicio de
  NiFi propio con ese job pendiente y restauración ES; avance a33 y hashes de
  Parquet anteriores idénticos.
- Reinicio propio de Filebeat/NiFi/ES/Kafka: offset33, metadata KRaft data/metadata,
  registry y journals conservados; nueva entrada automática hasta37. Paradas y
  reinicios controlados del mismo contenedor, no pérdida de host/alimentación.
- Después del merge de main: reinicio API sobre su ledger y replay con los mismos
  bytes y `scored_at`, cero inferencias en el proceso nuevo. Cuatro entregas nuevas
  avanzaron37→41, cuatro inferencias nuevas y Parquet anteriores conservados.

**Cierre verificado:** 41 enviados/observados únicos equivalen a 36 guardados,
5 rechazados y 0 pendientes. Offset confirmado 41; 36 respuestas canónicas,
36 documentos ES, 72 recibos CG15 aceptados y 72 objetos Parquet. Los bytes del worker y `_source`
ES coinciden con el ledger canónico. No se suman replays como mensajes nuevos.
El harness utilizó administración Kafka de lectura; nunca consumió ni confirmó
el grupo del producto.

[Escenarios, recursos y preservación](AUTOMATIC_GRAPH_20261022/summary.json).
[Hashes de fuente y artefactos locales](AUTOMATIC_GRAPH_20261022/artifacts.json).

## Comprobaciones y preservación

Antes de main: 46 tests y 108 subtests por combinación Windows/Fedora 3.11/3.12,
con `-W error`. Tras el merge: 71 tests y 130 subtests tanto en Fedora 3.12 como
Windows 3.12, incluyendo importador/replay de PR75, worker, HTTP y offsets.
Las regresiones incluyen recibo CG15 rechazado persistido, replay sin ACK,
límites HTTP y fallos en fronteras antes/después de done/ACK. Los dobles de
transporte se distinguen del recorrido real anterior. Sin migraciones reales.

Gates finales registrados con argv/exits: Ruff0.17.1 en todos los Python
rastreados, default y E/F/I/PLW1510, ambos `--ignore-noqa`; formato del diff,
CG02, CG25, layout, lock offline, auditoría y actionlint. Los avisos Ruff iniciales
de evidencia PR74 quedaron resueltos por la base integrada; no se editaron ni
suprimieron desde esta rama.
Los once gates finales tienen exit 0. Auditoría: 57 paquetes, 0 vulnerabilidades
y 0 estados adversos; los avisos experimentales de uv se conservan en el log.
[Logs de gates](AUTOMATIC_GRAPH_20261022/gates/results.json),
[Fedora tras main](AUTOMATIC_GRAPH_20261022/post-main-tests.log) y
[Windows tras main](AUTOMATIC_GRAPH_20261022/post-main-windows312.log).
La copia Windows versionada normaliza CRLF a LF; el log original y su hash
se conservan en el taskroot.

Inventarios completos antes/después. El Kafka histórico
`28d70b96fca30458914c3f8cb26fe7bcc388778bcb78f7b5cb35d38a5463b464` permaneció
detenido, inspect idéntico y mismas entradas de capa con tipo/ruta/multiplicidad.
No se arrancó, removió ni recreó. No se eliminaron contenedores, imágenes,
volúmenes, redes, ramas o worktrees. Los recursos propios quedan detenidos,
con ID/label verificados y datos retenidos.
Se conservan 102/102 contenedores, 60/60 imágenes, 78/78 volúmenes y 9/9 redes
previos. Quedan nueve contenedores propios detenidos y dos redes propias,
incluidos los intentos fallidos. [Invariantes de fuentes protegidas](AUTOMATIC_GRAPH_20261022/invariants.json)
verifica API/ledger/importador/ES/export staged y estado de rúbrica contra main.

Todo nuevo writable/temp/cache quedó bajo
`D:/github/_local/t2-babysit-20261021/automatic-graph-20261022`.
Imágenes locales `--pull=never`, rootfs read-only y puertos loopback aleatorios.
API solo en loopback y gateway de la red propia. Python existente reutilizado
read-only, sin clon ni instalación nueva.

Excepción /tmp autorizada expresamente: ES falló con `/tmp/final-flags*` y,
aun con ES_TMPDIR/CLI_JAVA_OPTS en D:, requirió `/tmp/.java_pid*` para su attach.
Se mantuvo su seguridad. `es-posix-runtime.ext4` de D: respalda el filesystem
POSIX montado en `lab-01/es-posix`, enlazado solo a `/tmp` y `/lab/runtime` del
ES propio `6812fc9cd213adca5e45fc20c0b428c54ace7003f7059833c715d1e5a1c51ae4`,
label `t2.automatic.run=t2-auto-0a3ce18890`. Datos/metadata ES usan otros binds D:.
No `/tmp` del host ni recursos ajenos. El loop mount queda retenido para revisar
el contenedor detenido; mounts y archivos propios están inventariados.

Se conservan fallos de instrumentación: red internal sin publicación efectiva,
helpers/attach ES, assets NiFi, CRLF del boot, tipo/NAR y relación failure de
AttributesToJSON, fechas GET de ES, flags/UID de Filebeat y nombre antiguo de
API de offsets. El primer colector rechazaba un bind exactamente igual a su
raíz autorizada; se corrigió la contención sin ampliar esa raíz. Ninguno de
estos intentos se cuenta como PASS ni reemplaza sus salidas originales.

## Repetición y requisitos pendientes

Taskroot local con `launch.ps1`, `run.py`, `lab.py`, `fixture_api.py`,
`api_restart.py`, `post_merge.py`, `collect.py`, logs y estados sellados. Para
regresiones: `agent-ps <taskroot>/launch.ps1 tests <nombre-nuevo>`; rechaza
sobrescribir logs. Otro lab necesita taskroot nuevo, sus binds POSIX/boot/config,
inventario e IDs nuevos. No repetir start, productor o fases sobre estos datos.
Para revisar, leer checkpoint/state y verificar ID/label antes de cualquier acción.

Pendientes: revisión del padre, CI de la nueva PR, aceptación del conector NiFi
programado como alternativa a ConsumeKafka de issue14 y configuración del
entorno objetivo. Otros orígenes requieren reconciliar identidades; aquí no se
aplica el importador a datos reales. No se ejecutaron carga sostenida, rebalance
durante escritura, HA/multinodo, retención prolongada ni pérdida de disco/host o
alimentación. No se acredita exactly-once distribuido, SLA ni aceptación de rúbrica.
