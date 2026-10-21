# CG14: worker durable opt-in

`scripts.run_durable_pipeline` conecta CSV raw, proyección de ocurrencia,
`/predict` canónico, salidas JSON inmutables y archivo CG15. ES es un destino
adicional obligatorio cuando se configura. No cambia el grafo NiFi del host.
Los mocks y LogAttribute siguen siendo auxiliares de diagnóstico.
El worker implementa el cableado P57-INTEGRATION-1; su aceptación en el
laboratorio Apache Kafka/NiFi y la revisión del padre siguen pendientes.

## Prerrequisitos y ejecución

Linux/POSIX con `fcntl`, disco local durable con fsync fiable, Python 3.11/3.12,
entorno del lock con extra `kafka`, API de esta revisión y manifiesto exacto del
bundle aprobado ya disponible. El worker lee el manifiesto; no carga modelos,
no entrena y no consulta datasets. No usar el journal/archivo en SMB/NFS.
La distro validada se llama `FedoraLinux-43` pero declara Fedora Linux 44 WSL.
Dependencias de la base integrada: kafka-python `3.0.11+cncguard.1`, HTTPX
0.27.0, FastAPI 0.133.0, Starlette 1.7.0 y PyArrow 23.0.1. El wheel local
de PR64 corrige los avisos de resources; no se cambia su pin ni su contenido.

En un laboratorio propio autorizado, con broker y topic ya creados:

```bash
uv sync --locked --extra kafka
uv run --locked --extra kafka python -m scripts.run_durable_pipeline \
  --root /var/tmp/cg14-own-lab \
  --manifest /path/to/approved/manifest.json \
  --source-namespace 'cluster-UUID/topics-generation-1' \
  --source-kind lab_fixture --scoring-url http://127.0.0.1:18000/predict \
  kafka --bootstrap-servers 127.0.0.1:19092 \
  --group-id cg14-durable-own-lab --topic raw-own-lab \
  --offset-reset earliest --max-records 1 --max-polls 10
```

Son endpoints de ejemplo, no servicios descubiertos ni autorizaciones para
infraestructura compartida. No hay endpoints por defecto. La CLI no crea
topics, servicios, bundles o índices. `none` es el reset por defecto;
`earliest` requiere elección explícita y sólo recupera lo retenido por Kafka.
Kafka v3.7 es el protocolo predeterminado de PR58; elegir otro con
`--api-version` sólo si el broker lo soporta. PLAINTEXT se limita a laboratorio.
HTTPX conserva verificación TLS, desactiva proxies del entorno y no sigue
redirects. No hay flags para desactivar TLS. No pasar secretos en argumentos.

Cada ejecución consume como máximo diez polls por defecto, incluidos vacíos.
`--attempts 3 --timeout 10` limita HTTP por petición. Los fallos terminan el
proceso y dejan offsets sin confirmar. El presupuesto del poll debe superar
el máximo HTTP calculado más 60 segundos para disco; un disco más lento aún
puede causar revocación, que impide el commit. SIGINT/SIGTERM dejan terminar
el lote actual o lo dejan para replay; no confirman un poll sin procesar.

Para ES añadir antes de `kafka`:

```text
--es-url http://127.0.0.1:19200 --es-index cnc-telemetry-own-lab
```

Preparar previamente un índice concreto con el mapping del repositorio y
`index.translog.durability=request`; configurar las réplicas activas apropiadas.
El worker guarda predicciones completas, no un subconjunto de campos. No
gestiona plantillas, aliases, retención ni infraestructuras. Si ES no se
configura, los destinos requeridos son outbox local y archivo CG15.

## Identidad y orden de commits

La entrada es un CSV por valor Kafka, con timestamp UTC y los trece campos
históricos. Se reutiliza `parse_csv_event` en modo inference: valida y retira
etiquetas, sin convertirlas en features. Se conserva cada byte original,
incluidos saltos de línea, antes de validar, proyectar o llamar a HTTP.

PR58 conserva la entrega `["kafka", namespace, topic, partition, offset]`.
El parser conserva su kind legacy exacto (`--legacy-source-kind`, por defecto
`cg14-lab-kafka`) y el binding lo mapea al `--source-kind` canónico configurado.
Para otro alias CG14 indicar su valor exacto; no inferir ni sustituir IDs de
la ruta PR42 basada en Kafka key. Esta CLI migra CSV mediante el parser CG14.
`bind_occurrence` conserva el ID legacy y raw en el sidecar y deriva la
ocurrencia de las coordenadas originales mediante `cnc.occurrence.v1`.
No se deduplica por contenido: dos CSV iguales en offsets distintos generan
ocurrencias distintas. El namespace identifica cluster y generación de log,
no consumer group, hostname o run. Una recreación de topic exige generación
nueva. La CLI Kafka trata sus coordenadas consumidas como origen; no es una
ruta de republicación con origen implícito.

1. `raw/*.bin`, `origin/*.json` y job SQLite FULL se confirman antes del API.
2. `identity/*.json` conserva proyección y sidecar; los contratos estrictos
   nunca reciben `raw_record` ni el sidecar.
3. Cada intento HTTP se registra antes de I/O. El API compara las cabeceras
   `X-CNC-Manifest-SHA256` y `X-CNC-Contracts-SHA256` antes de inferir y las
   devuelve en éxito. El worker exige ambas: un API antiguo que las ignore
   falla cerrado. Sin cabeceras, los clientes existentes conservan su contrato.
4. El API PR61 persiste/reutiliza la respuesta canónica antes de 2xx. El worker
   comprueba Prediction, telemetría y manifiesto y guarda esa respuesta en su
   journal antes de escribir destinos.
5. `outbox/telemetry` y `outbox/prediction` son JSON inmutables. CG15 persiste
   Bronze, Parquet y ledger; un rechazo CG15 bloquea el origen. Se reutiliza
   su misma clave de evento, sin inventar una segunda semántica de IDs.
   Cada stream exige un recibo durable `stored` o `duplicate` y la huella de
   sus bytes. Se consulta también después del archivo de jobs pendientes:
   `replay=1, rejected=0` no acredita aceptación del recibo original. Un
   recibo `rejected` sigue bloqueando en todos los reintentos, sin editarlo.
6. ES opt-in usa `_create` con esa misma clave Prediction. Un 409 sólo se
   acepta tras GET y comparación exacta del `_source`; nunca sobrescribe.
7. El job pasa a completado sólo después de todos los destinos requeridos.
   PR58 confirma offsets explícitos `último entregado + 1` del poll completo
   tras comprobar asignación; no usa posición prefetched ni auto-commit.

El journal fija versión de worker, manifiesto completo, bytes de schemas,
namespace, source kind y destinos. Cambiar cualquiera exige reconciliación;
reiniciar con configuración nueva no reinterpreta jobs antiguos. La API
también rechaza un manifiesto o contrato distinto durante un HTTP incierto.
Esto evita inferir silenciosamente con otro modelo. Cambios de umbrales,
anomaly model o metadatos bajo una misma identidad siguen sujetos al 409 de
PR61. Un modelo nuevo deliberado requiere una migración revisada, no borrar
ledgers, generar IDs nuevos arbitrarios o editar estados para saltar el bloqueo.

## Fallos y recuperación

CSV/UTF-8 inválidos y HTTP 422 son rechazos terminales: raw más cuarentena
durable antes del ack, sin predicción ficticia. La cuarentena referencia el
delivery mediante nombre/hash, motivo y hashes del cuerpo cuando corresponde.
HTTP 409 y otros 4xx/3xx bloquean, conservan evidencia y no confirman offsets.
La API admite como máximo 32.768 bytes, incluidos cuerpos fragmentados; un
cuerpo mayor conserva 413. JSON con más de 64 contenedores anidados devuelve
422 antes del parsing. Errores de sintaxis/validación también devuelven 422
acotado, sin serializar `input` ni contexto recursivo. Los errores internos no
se reclasifican como errores de validación.
2xx requiere cuerpo Prediction válido y las dos precondiciones reconocidas;
un 204 o JSON inválido no es éxito. Los 5xx y errores de transporte, incluidos
timeouts, tienen intentos finitos y, al agotarse, dejan cuarentena de bloqueo
y ningún ack. No se convierten en descartes terminales porque el servidor
puede haber confirmado la respuesta antes de perderse el transporte.

Reiniciar con la misma raíz, configuración, grupo, namespace y coordenadas.
Si el worker perdió un 2xx, el API devuelve la misma respuesta de su ledger;
si ya la guardó localmente, el worker publica sus mismos bytes sin HTTP nuevo.
Un fallo tras archivo o ES y antes de done/ack vuelve a comparar los destinos.
Incluso un job completado revalida archivo y ES al reentregarse; la pérdida
del ledger o de un recibo comprometido bloquea antes de recrear el archivo.
Un commit Kafka incierto causa replay del prefijo; no repetir un productor.
PR58 cierra el consumidor sin auto-commit tras error o revocación.

No borrar archivos, responses.sqlite3 del API, pipeline.sqlite3 o ledger de
CG15 para desbloquear. Conservar el árbol completo, proteger sus permisos y
respaldarlo de forma consistente con el API y retención Kafka. Los hashes de
objetos comprometidos se comprueban antes de reutilizarlos. Corrupción o
contenido distinto bajo una identidad bloquean; recuperar desde copia
verificada y reconciliar entregas/offsets antes de reanudar. Los temporales
huérfanos no son éxito. No hay comando automático de purga o reset.

Hay transacciones independientes en API, worker, CG15, ES y Kafka: **no hay
exactly-once entre servicios**. Hay persistencia local previa al ack y replay
idempotente condicionado a conservar ledgers/configuración y a la durabilidad
de los servicios. Una pérdida de disco/retención o borrado externo requiere
recuperación operativa. El outbox no publica automáticamente topics nuevos;
sus JSON y Parquet son destinos durables operables de esta versión.

## Export NiFi auxiliar

`nifi-flows/cg14_durable_staged_nifi_2.12.0.json` es un export separado, con
procesadores DISABLED, stdin de CSV y coordenadas originales en atributos
`kafka.topic`, `kafka.partition`, `kafka.offset`. No contiene ConsumeKafka ni
modifica exports revisados. Ejecuta el mismo CLI en modo `stdin`; requiere
Python/checkout/entorno con extra kafka y disco accesibles dentro de NiFi.
Configurar los parámetros `WORKER_CHECKOUT`, `WORKER_PYTHON`, `DURABLE_ROOT`,
`PINNED_MANIFEST`, `SOURCE_NAMESPACE`, `SOURCE_KIND` y `SCORING_URL`. Los valores
de argumento no pueden contener el delimitador `;`. Este export no habilita ES.
El export usa el kind legacy predeterminado `cg14-lab-kafka`; para otro alias,
generar/revisar una definición específica antes de habilitarla.

ExecuteStreamCommand conserva el original con `execution.status`; sólo status
0 llega a completed-original. Los receipts y originales fallidos tienen
puertos separados sin auto-terminaciones ni LogAttribute como sink final.
Un receipt 0 expresa commit del worker o rechazo durable, **no ack Kafka**.
Se debe conservar la entrada staged y conectar explícitamente los puertos
en un laboratorio revisado. No conectar un ConsumeKafka que ya confirme su
origen y atribuirle las garantías del worker Kafka.
Las propiedades y relaciones siguen la documentación de
[ExecuteStreamCommand 2.12.0](https://nifi.apache.org/components/org.apache.nifi.processors.standard.ExecuteStreamCommand/).
El export está inspeccionado offline; no se acredita import/ejecución NiFi.

Regenerar siempre a una ruta nueva; el comando rechaza sobrescritura:

```bash
python -m scripts.build_durable_pipeline_flow --output /new/path/flow.json
```

## Validación y límites

La suite `test_cg14_durable_pipeline.py` usa disco/SQLite/CG15 reales y API
ASGI real con modelos sintéticos en memoria. Los errores HTTP y callbacks
Kafka son transportes dobles declarados. `verify_durable_pipeline.py` añade
HTTP real por loopback y ES 9.5.4 real en contenedor propio `--network=none`,
sin puertos ni volúmenes, con datos tmpfs y `--pull=never`. Usa curl por
docker exec exclusivamente contra 127.0.0.1 dentro de ese contenedor.
No prueba Apache Kafka, NiFi, Filebeat, SMB/OT ni un modelo de entrega.
`test_durable_receipts_http.py` añade Uvicorn/HTTP real, conflictos CG15 en
ambos streams, cuatro intentos con conexiones reabiertas, commit de origen
incierto y validación JSON profunda/fragmentada en Python 3.11 y 3.12.

```bash
PYTHONPATH=.:tests python tests/verify_durable_pipeline.py --output /new/path/result.json
```

Ese verificador reserva un fichero nuevo antes de crear recursos y registra
fallos y limpieza; no reemplaza evidencia previa. Las pruebas de cortes por
excepción verifican replay y commits visibles, no un ensayo de pérdida de
alimentación del disco. Antes de aceptación faltan ensayo Kafka/NiFi real,
import del export, caída/rebalance real, persistencia tras reinicio del host
y revisión independiente sobre el SHA final. Los 218 avisos Kafka heredados
se corrigieron en PR64, incorporada en esta base; véase su
[evidencia](evidence/KAFKA311_WARNING_FIX_20261021.md). La validación del delta
y sus límites se registran en [la ronda 2](evidence/DURABLE_PIPELINE_FIX_R2_20261021.md).
