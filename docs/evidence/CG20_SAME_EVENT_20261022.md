# CG20: mismo evento API → Elasticsearch → Kibana

Ensayo nuevo del 22/10/2026 sobre main
`3b79c927c909bb0c87fe3f344c2b4bd152f31c61`, árbol
`2e7f81c7a09839378e44cccca215b84d516ded8d`, contrastado con la referencia
remota antes de empezar. Proyecto educativo, no MKDL.

**Resultado técnico acreditado para este laboratorio:** el evento
`279947a017e5d70adba2a83e5eb319c0c7495260ebac7259de1954bb834c6b8b`
recorre Filebeat → Kafka → worker programado por NiFi → API HTTP canónica →
CG15/Elasticsearch → Kibana. La respuesta HTTP, ledger SQLite, respuesta retenida
por el worker y `_source` ES son iguales. Discover devuelve un documento y el
panel representa los mismos valores consultando ese índice. Los filtros de un
ID inexistente vacían ambas vistas y restaurar el ID recupera un documento.

Issue #20 permanece abierto hasta la revisión del padre. Esta evidencia no
constituye por sí sola aceptación PM final, merge ni aceptación académica.

## Criterio, artefacto, comando y resultado

| Criterio | Evidencia nueva | Verificación | Resultado y límite |
| --- | --- | --- | --- |
| Mismo original e identidad | [raw](CG20_SAME_EVENT_20261022/raw.csv), [lote](CG20_SAME_EVENT_20261022/lab-01/input/normal.csv), [conciliación](CG20_SAME_EVENT_20261022/same-event.json) | `collect.py cg20-collect` lee journals y ledgers propios | Original conservado; topic/partition/offset `cnc-sensors-automatic-v1/0/0`; cuatro ocurrencias válidas distintas aunque sus líneas sean iguales. |
| API, ES y Kibana coinciden | [HTTP](CG20_SAME_EVENT_20261022/api-response.json), [ES](CG20_SAME_EVENT_20261022/es-query.json), [valores renderizados](CG20_SAME_EVENT_20261022/dashboard-verified-values.json), [fila Discover](CG20_SAME_EVENT_20261022/discover-visible-row.json) | `python -B -m scripts.check_cg20_same_event` | Igualdad completa HTTP/ledger/worker/ES; igualdad de identidad, origen, modelo, scores, alertas, timestamps y destino en el panel. |
| Vista real y filtro | [panel](CG20_SAME_EVENT_20261022/dashboard-verified.png), [Discover](CG20_SAME_EVENT_20261022/discover-same-event.png), [Discover negativo](CG20_SAME_EVENT_20261022/discover-negative.png), [restauración](CG20_SAME_EVENT_20261022/discover-restored.png) | Chrome mediante Computer Use, tras dos timeouts de T3 preview | Capturas reales del mismo laboratorio y mismo ID; no renders ni suma de laboratorios distintos. |
| Configuración reproducible | [export Kibana](CG20_SAME_EVENT_20261022/kibana-final-runtime-export.ndjson), [export NiFi](CG20_SAME_EVENT_20261022/lab-01/runtime-export.json), [config worker](CG20_SAME_EVENT_20261022/lab-01/graph.json), [comandos](CG20_SAME_EVENT_20261022/commands.jsonl) | Imports/exports HTTP reales, `lab.py finish` | Cuatro objetos Kibana exportados con referencias; flow NiFi exportado detenido; rutas y puertos de este ensayo explícitos. |
| Versiones y preservación | [versiones/tiempos](CG20_SAME_EVENT_20261022/versions-and-timing.json), [recursos](CG20_SAME_EVENT_20261022/resources.json), [preservación](CG20_SAME_EVENT_20261022/preservation-reconciled.json) | Inventario Docker previo/posterior y comparación | Recursos ajenos conservados; cinco contenedores y una red propios retenidos, sin volúmenes nuevos. |

Revisor de esta ejecución: agente de pruebas, 22/10/2026. Revisión del padre:
pendiente. La aceptación PM parcial anterior se conserva en el comentario
`6342104563` de issue #20. El cierre sigue reservado al padre.

## Valores del evento seguido

| Campo | Valor igual entre API/ES/panel |
| --- | --- |
| `event_id` | `279947a017e5d70adba2a83e5eb319c0c7495260ebac7259de1954bb834c6b8b` |
| `source.kind` | `lab_fixture` |
| `source.uri` | `kafka://t2-cg20-b74cb05b34/generation-1/cnc-sensors-automatic-v1` |
| `source.record_ref` | `cnc-sensors-automatic-v1/0/0` |
| `model_version` | `synthetic-replay-only` |
| `failure_score`, `anomaly_score` | `0.8`, `0.5` |
| `alert_level`, `risk_alert`, `anomaly_alert` | `CRITICA`, `true`, `true` |
| `timestamp` | `2026-10-21T08:00:00Z` |
| `scored_at` | `2026-10-22T13:47:41.231811Z` |
| Destino ES | `cnc-alerts-automatic-v4` |
| `_id` ES | `a7f78d005fefd2883d6f762aa3befb9c9962083000c333a5d6740c9ee86e1a1c` |

El destino y `_id` se cotejan con el hit ES y aparecen en el panel; no son campos
añadidos a la respuesta API. Discover muestra fechas con zona del navegador
Europe/Madrid y milisegundos: `08:00Z` aparece como `10:00`, y `scored_at` como
`15:47:41.231`. El panel conserva el texto UTC completo, incluidos los microsegundos.
La copia desde el botón del editor JSON de Discover devolvió un portapapeles vacío;
no se presenta como una exportación íntegra de Discover. Se conservan la lectura
visible, el detalle capturado y la consulta ES íntegra por identidad.

## Alcance del ensayo y fallos conservados

Se evaluaron primero RUN-FINAL PM y las evidencias PR76/PR69. No satisfacían el
criterio pendiente: PR76 terminaba en ES y PR69 mostraba otros cien documentos
sin scoring. Este ensayo utiliza datos nuevos y un conjunto propio de servicios.

Entrada: cuatro filas válidas iguales y una inválida, para superar la ventana
de fingerprint de 228 bytes de Filebeat sin cambiar la configuración del producto.
Resultado: **5 observados = 4 guardados + 1 rechazado + 0 pendientes**, offset 5,
cuatro documentos ES y ocho archivos/recibos CG15. Se sigue una ocurrencia única
por sus coordenadas Kafka; el hash del contenido por sí solo no identifica una
ocurrencia. El driver del lab no consume ni confirma registros; NiFi programa el
worker de producto mediante ExecuteStreamCommand.

La instrumentación inicial de captura del stub intentaba serializar cabeceras
binarias y devolvía 500 después de escribir la respuesta canónica en SQLite.
El worker retuvo el registro, sin ACK. Se corrigió solo el registro del stub y se
reinició su proceso propio verificando su PID/cmdline. La respuesta del evento
seguido se recuperó del ledger (`risk_calls=0` en su primer HTTP 200 tras reinicio).
Se conservan intentos fallidos, respuesta, `scored_at` y journals; no se reenvió ni
recreó el lote para ocultar el fallo. La cadena se completó automáticamente después.

El runner PowerShell inicial agotó su timeout de 60 s; los contenedores remotos
siguieron vivos. Se inspeccionó estado y procesos antes de continuar solo la
configuración NiFi. Otros lanzamientos WSL devolvieron `WSAETIMEDOUT` antes de
ejecutar Python; fijar `--cd` explícitamente permitió continuar. Los logs fallidos
se conservan. La fuente de producto no cambió. La primera configuración del panel
usaba nombres de origen no presentes y tenía contraste insuficiente en modo
oscuro; el export final consulta `source.kind/uri/record_ref`, con fondo explícito.

La comprobación inicial de preservación comparaba el texto sin ordenar de
`docker diff`; falló por el orden de sus entradas. Se conservaron ambas capturas y
se verificó igualdad de las entradas ordenadas. Esto comprueba metadatos y rutas
de la capa, no constituye una nueva lectura/hash de los contenidos ajenos.

## Repetición y límites

El verificador offline no arranca servicios ni modelos:

```powershell
py -3 -B -m scripts.check_cg20_same_event
```

Los [helpers](CG20_SAME_EVENT_20261022/reproduce/lab.py) publicados son copias de
los ejecutados, formateadas y con imports sin uso retirados, `check=False`
explícito seguido de verificación de retorno y comparación de `docker diff`
ordenada. No se afirma una segunda ejecución del lab con estas copias editadas.
Sus fuentes ejecutadas originales y hashes están retenidos en el taskroot local.

Para repetir el lab, crear un taskroot nuevo en D:, copiar allí `reproduce/`,
preparar `process-temp`, `ruff-cache`, `uv-cache`, `lab-01` y un checkout propio de
la base indicada; ajustar las rutas explícitas de `C`, `launch.ps1` y
`root-mount.sh`. Requiere FedoraLinux-43, Docker e imágenes locales indicadas,
Python 3.12 con las dependencias del proyecto y Kafka, y `mke2fs` local. El entorno
de Python existente se monta de solo lectura. No ejecutar `start` sobre este
taskroot ni sus datos sellados. `lab.py` rechaza un `state.json` existente.

Secuencia realizada: inventario → `prepare_posix.py`/montaje → `lab.py start`
→ continuación de configuración `resume-nifi` → `lab.py normal` → reparación del
registro fixture → `collect.py cg20-collect` → `kibana_lab.py kb-start/kb-configure/kb-search`
→ consultas/capturas de navegador → `export.py cg20-export` → `lab.py finish`
→ inventario posterior/reconciliación. El orden exacto, reintentos y códigos de
salida quedan en `commands.jsonl`; los exports contienen las rutas y puertos reales.

ES9.5.4 necesita temporales JVM con semántica POSIX. Se usó una imagen ext4 nueva
de 256 MiB respaldada en D:, montada en una carpeta propia en D: y bind a
`/lab/runtime` y `/tmp` **internos** de su contenedor con rootfs de solo lectura.
La excepción está expresamente autorizada; no se usa `/tmp` del host. Se conserva
el montaje y la imagen, sin desmontar ni borrar nada. Los datos de otros servicios
tienen binds propios D:. Puertos elegidos aleatoriamente y publicados en loopback.

Son datos y modelos **sintéticos**: RiskDouble/AnomalyDouble de las pruebas
existentes, no inferencia de un modelo real. No se entrenó, cargó un bundle,
preparó entrega ni ejecutó testfinal. No hay SMB/OT compartido, migraciones reales,
SLA, HA, carga sostenida, tolerancia a pérdida de host/disco ni exactly-once global
acreditados. Las marcas de tiempo de archivo son observaciones de filesystem;
no se calculan latencias por etapa ni percentiles con una instrumentación ausente.

No se arrancaron los nueve contenedores del ensayo anterior, no se editaron
sellos o datos históricos, no se tocó el broker histórico ni los cuatro volúmenes
Kibana previos. Los inventarios íntegros quedan locales porque contienen
configuración de servicios ajenos; se publica únicamente el resumen y los recursos
propios. CI se captura una sola vez tras publicar el draft, sin activación manual
ni seguimiento. Los gates locales y sus resultados se registran por separado.

## Validación local final

[Diez gates ejecutados](CG20_SAME_EVENT_20261022/validation/gates-final-r2-summary.json),
todos exit0: Ruff0.17.1 global `--ignore-noqa`, selección E/F/I/PLW1510 también
global `--ignore-noqa`, formato de los nueve Python añadidos, verificador del
mismo evento, CG02, CG25, layout, enlaces del informe y `git diff --check`.
El [verificador también pasó en Windows](CG20_SAME_EVENT_20261022/validation/same-event-windows.log).
No se repitió la suite ML. Los intentos de gates anteriores y sus correcciones
quedan locales; no se bajaron reglas ni se añadieron supresiones.

La actualización del seguimiento exige cambiar su hash en el manifiesto CG25
vigente; se cambió únicamente esa entrada, conservando el snapshot histórico.
Los originales ejecutados permanecen locales. Las copias publicables normalizan
CRLF o espacios finales de la lectura AX, con hashes antes/después en
[normalización](CG20_SAME_EVENT_20261022/publication-normalization.json) y
[espacios AX](CG20_SAME_EVENT_20261022/publication-whitespace.json).
[checksums.json](CG20_SAME_EVENT_20261022/checksums.json) sella cada archivo de
este directorio salvo el propio manifiesto; el informe exterior se fija por Git.
Los cinco puertos del lab quedaron cerrados y los cinco contenedores detenidos.
