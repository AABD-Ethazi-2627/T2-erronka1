# CG15: adaptador Kafka para el archivo durable

Este consumidor archiva **valores JSON normalizados** de telemetría y predicción.
No interpreta CSV de `cnc-sensors-smb-v1` ni de `cnc-sensors-lab-v2`: esos topics
de entrada requieren primero la normalización de NiFi. No cambia los flows,
Gold, los modelos, el scoring ni servicios compartidos.

## Instalación y ejecución

Desde la raíz del repositorio, en Fedora/Linux con Python 3.11 o 3.12:

```bash
uv sync --locked --extra kafka
uv run --locked --extra kafka python -m scripts.archive_consumer --help
```

El extra incorpora solamente `kafka-python==3.0.11`, cliente Python sin
dependencias transitivas obligatorias. El entorno offline sin `--extra kafka`
conserva sus dependencias. Se eligió frente a añadir un servicio o una biblioteca
C al consumidor. Lock y pruebas fijan la versión; no usar el paquete `kafka`.
[Paquete](https://pypi.org/project/kafka-python/3.0.11/) y
[API del cliente](https://kafka-python.readthedocs.io/en/3.0.11/apidoc/KafkaConsumer.html).

`--api-version 3.7` es el valor por defecto, correspondiente a
`apache/kafka:3.7.0` en `docker-compose.yml`. La selección explícita evita
depender de la negociación inicial v4 del cliente con brokers anteriores.
Para otro laboratorio, indicar el protocolo compatible con ese broker; el lab
de librdkafka usa `--api-version 2.0`. No anunciar una versión superior a la
soportada. La conexión sigue consultando las capacidades del broker.

Ejemplo para un **laboratorio propio**, con topics normalizados ya existentes,
endpoints propios y filesystem POSIX local con fsync fiable:

```bash
uv run --locked --extra kafka python -m scripts.archive_consumer \
  --bootstrap-servers 127.0.0.1:19092 \
  --group-id cg15-archive-lab \
  --source-namespace 'cluster-lab-UUID/topics-generation-1' \
  --topic normalized-telemetry=telemetry \
  --topic normalized-prediction=prediction \
  --root /var/tmp/cg15-lab-archive \
  --offset-reset earliest --max-records 100 --max-batches 1
```

El ejemplo no crea topics ni los publica. El operador debe autorizar los
endpoints antes de ejecutarlo. CLI v1 usa PLAINTEXT; se limita a red privada de
laboratorio. No es una configuración para brokers remotos con TLS/SASL.
No guardar el archivo en SMB/NFS. Windows nativo se rechaza antes de conectar.

`--offset-reset none` es el valor por defecto: offsets inexistentes o caducados
producen error. Para un grupo nuevo, `earliest` debe elegirse explícitamente;
solo lee lo retenido, no recupera registros eliminados por retención. No existe
opción `latest`. `--max-batches` cuenta únicamente lotes no vacíos; sin mensajes
puede esperar hasta recibir SIGINT/SIGTERM. Cada lote confirmado imprime JSON
con `sent`, `stored`, `rejected`, `duplicate`, `replay`. Los fallos dan salida
distinta de cero. Las excepciones pueden incluir datos operativos: guardar los
logs con el mismo control de acceso que el archivo.

## Identidad y offsets

La ID de entrega es JSON canónico de:

```text
["kafka", source_namespace, topic, partition, offset]
```

Es inequívoca incluso si nombres o namespaces contienen `/`, comillas o Unicode.
El namespace es un **contrato del operador**, no una identidad descubierta ni
verificada por el cliente: debe identificar el clúster de origen y la generación
de todos los topics mapeados. Mantenerlo estable entre reinicios, grupos,
consumidores y cambios de hostname del mismo origen. Si se recrea/restaura un
topic reutilizando offsets, usar una nueva generación; con generación común,
cambiarla para todo el mapeo. No reutilizar namespaces entre clústeres. La
integridad global depende de este contrato. No se deriva del bootstrap hostname,
del consumer group ni de `event_id`.

Cada proceso tiene un cliente usado por un solo hilo de aplicación, sin `seek`
ni procesamiento paralelo de sus polls. `poll` entrega un prefijo ordenado de
cada partición. Puede contener huecos numéricos por compactación o transacciones;
no se exige `offset[n+1] == offset[n]+1`. Sí se exige orden estrictamente creciente
dentro del poll, topic/partición coherentes, asignación vigente y bytes sin
deserializar. Se persiste todo ese prefijo antes de confirmar `último offset + 1`
de cada partición incluida. No se usa `commit()` sin offsets: la posición interna
podría incluir lecturas adelantadas. Particiones sin registros no se confirman.
La [API oficial de Kafka 3.7](https://kafka.apache.org/37/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html)
documenta los huecos por marcadores y transacciones abortadas.

`enable_auto_commit=False`, `allow_auto_create_topics=False` y
`isolation_level=read_committed` son fijos. La confirmación es síncrona y tiene
timeout. No hay confirmación implícita al cerrar. Bytes JSON inválidos o conflictos
de evento quedan en Bronze/rechazos durables y permiten avanzar; **tombstones
Kafka (`value=None`) bloquean el lote** sin commit, porque no son bytes JSON ni
se pueden representar fielmente como un valor vacío. Requieren intervención
en el origen o un contrato de tombstones nuevo; no se omiten automáticamente.

El sink guarda los bytes del **valor**. Claves y headers de Kafka no forman
parte del contrato de archivo. El `event_id` del payload se valida, no se
recalcula a partir de la clave. La identidad de evento y las particiones Parquet
siguen [CG15_ARCHIVE](evidence/CG15_ARCHIVE.md).

## Recuperación, rebalance y paradas

- Fallo de escritura, fsync o ledger: abortar, cerrar sin commit y reiniciar con
  el mismo namespace/raíz/grupo. El sink reconcilia huérfanos y verifica hashes.
- Commit fallido o timeout ambiguo: los datos locales permanecen; no se hace
  rollback ni se continúa al siguiente poll. Al reiniciar, el broker puede
  repetir el lote o haber aceptado el commit. Ambos casos conservan el archivo.
  Un commit multipartición parcialmente aceptado también permite replay seguro.
- Un rebalance después de la primera asignación deja al proceso en fallo y
  exige reinicio. Los callbacks solo marcan eventos y nunca escriben ni
  confirman desde el hilo IO. La pérdida detectada antes del ack impide ese
  commit; una carrera con un commit ya en vuelo puede dejarlo aceptado o
  rechazado por el broker. En cualquier caso solo contiene entregas durables.
  No se promete una transacción atómica entre SQLite y el consumer group.
- SIGINT/SIGTERM solo solicita parada: si llega durante poll, no se procesa ese
  lote; si llega durante la persistencia, se termina y confirma el lote actual,
  sin leer otro. SIGKILL/crash deja los offsets para replay. El cierre no
  confirma la posición interna. Los handlers previos se restauran al salir.
- `--max-poll-interval-ms` limita el tiempo sin poll. Reducir `--max-records`
  o ampliar ese intervalo si el disco es lento; superar el intervalo puede
  causar rebalance y replay. No se mantiene un hilo consumidor paralelo al sink.
- Procesos con raíces distintas deben usar grupos distintos: compartir grupo
  reparte las particiones, no replica el archivo. Procesos con la misma raíz
  local usan el bloqueo SQLite ya existente; cualquier timeout de bloqueo aborta
  sin confirmar. No compartir esa raíz por SMB ni entre hosts.

No es exactly-once. Es consumo con replay y persistencia local idempotente,
dependiente de retención suficiente, namespace correcto, integridad del disco,
fsync fiable y ausencia de manipulación externa del directorio de archivo.

## Pruebas

```bash
uv run --locked --extra kafka python -m unittest discover -s tests -p 'test_kafka_archive.py' -v
uv run --locked --extra kafka python -m unittest discover -s tests -p 'test_archive_consumer.py' -v
uvx --from ruff==0.17.1 ruff check .
```

Las pruebas unitarias usan el sink real con filesystem/SQLite y un transporte
controlado: no prueban un broker Apache Kafka desplegado. Sin el extra Kafka,
la suite omite explícitamente el módulo opcional. El workflow automático
`validate.yml` instala ese extra para ejecutar las regresiones; conserva sus
triggers y no ejecuta el lab de sockets. Evidencia ejecutada, versiones,
límites y revisión pendiente: [CG15_KAFKA](evidence/CG15_KAFKA_20261021.md).

Laboratorio de protocolo opcional, solo loopback, sin Docker ni descarga del
broker Java. Añade temporalmente un wheel de unos 5 MB a un entorno de `uv`,
sin modificar el lock ni el extra de producción:

```bash
uv run --locked --extra kafka --with confluent-kafka==2.16.0 python tests/kafka_wire_lab.py
```

Ese script crea y destruye su propio mock librdkafka, publica tres fixtures y
ejecuta la CLI en subprocesos. Comprueba offsets del grupo, replay, hashes
Parquet y SIGTERM. Sigue siendo un **mock del protocolo Kafka**, no demuestra
aceptación con Apache Kafka 3.7 ni tolerancia a fallos de un clúster real.
