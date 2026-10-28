# CG32 — carga breve del grafo integrado con el bundle propio

Issue #81. Amplía la evidencia de #23 (microbenchmark cola/JSONL) y #20 (mismo
evento con RiskDouble/AnomalyDouble) sin reabrirlas. No es HA, SLA ni capacidad
sostenida; el rendimiento ML sigue siendo desarrollo sintético.

## Grafo medido

`CSV append → Filebeat → Kafka (KRaft, 1 partición) → NiFi 2.12
(GenerateFlowFile + ExecuteStreamCommand) → scripts.run_automatic_graph →
API real (scoring/score_api.py + bundle) → ledger/CG15 → ES (_create, guard
cnc-prediction-v1) → Kibana Discover`.

Las versiones e identidades actuales se fijan en `deploy/images.json` y en los
Dockerfiles de `deploy/cg32/compose.yaml`; cada campaña registra sus imágenes
efectivas. Las medidas históricas conservan su runtime original y no se
atribuyen a imágenes posteriores.

Producto sin cambios: worker, API, export NiFi (`build_automatic_graph_flow`),
Filebeat (`filebeat/filebeat.yml`, solo rutas/host/topic), pipeline y template ES.
Herramientas nuevas del ensayo:

| Archivo | Papel |
| --- | --- |
| [deploy/cg32/compose.yaml](../deploy/cg32/compose.yaml) | Proyecto Compose propio, puertos aleatorios en loopback, `cap_drop: ALL`, sin restart |
| [deploy/cg32/api_server.py](../deploy/cg32/api_server.py) | `create_app(manifest)` intacto + envoltorio ASGI que registra el tiempo servidor por petición (sin cuerpos ni cabeceras) |
| [scripts/cg32_lab.py](../scripts/cg32_lab.py) | init/up/run/model/discover/stop del laboratorio |
| [scripts/cg32_load.py](../scripts/cg32_load.py) | Fixture, oferta temporizada, reconciliación y estadísticas (sin servicios) |
| [tests/test_cg32_load.py](../tests/test_cg32_load.py) | Regresiones de fixture, oferta, reconciliación y percentiles |

## Aislamiento y presupuesto (paso 1 y 6)

- Proyecto `cg32-<uuid>`; contenedores, red y volúmenes NiFi propios; Kafka/ES en
  binds del directorio del lab. No usa SMB, el broker histórico, servicios
  compartidos ni los contenedores `iabd-*`/`cnc-cg14-*` existentes.
- Secretos NiFi generados en `<lab>/.env` (0600), nunca impresos ni versionados.
- El bundle se monta **solo lectura** en la API; NiFi recibe una copia byte a byte
  del `manifest.json` (el worker no carga pickles). `verify_bundle` exige que los
  hashes de `rf.pkl`/`if.pkl` y del manifiesto coincidan con el recibo sellado
  `CG26_REHEARSAL_2026-10-21.json` antes de cada run. Un bundle internamente
  coherente con el mismo `model_version` no sustituye esa identidad.
- Presupuesto acordado antes de arrancar (`BUDGET` en `cg32_lab.py`): RAM libre
  ≥6 GiB y disco libre ≥20 GiB al iniciar; lab ≤4 GiB; drenaje ≤900 s; lag ≤20.000.
  Límites de contenedor: Kafka 768 MiB, ES 1,2 GiB, NiFi 2 GiB, API 768 MiB,
  Filebeat 256 MiB, Kibana 1,6 GiB (solo para Discover). El primer límite superado
  detiene la oferta/drenaje y queda en `stopped_by_budget`; el informe se produce igual.
  Antes de la primera fila se comprueban disco y lag. Durante la oferta se consulta
  el presupuesto antes de escribir cada fila y después de esperar el turno.
  Las consultas de disco se separan al menos 0,5 s para limitar el coste del
  recorrido; el intervalo efectivo depende de la tasa y de la E/S. Lag usa la
  última muestra de 2 s. Es una parada cooperativa, no un límite instantáneo.
  `expected` conserva el plan y `offered`/la reconciliación cuentan solo filas
  escritas. Con cero filas, los tiempos/rates sin observaciones quedan en `null`.
- Sin retención automática, sin borrar datos, sin `down -v`, sin cambios de firewall.
  El firewall del host bloquea contenedor→host: por eso la API corre como servicio
  del proyecto (debian-slim + intérprete/venv del checkout montados solo lectura).

## Cada run

Topic, grupo, raíz del worker, ledger API, índice ES y grupo NiFi **nuevos**;
`offset_reset=earliest` explícito en el primer arranque del grupo. Solo un grafo
NiFi activo (los grupos anteriores se detienen antes de subir el nuevo).
`run.json` se reserva con estado `preparing` y las identidades planeadas antes
de preparar archivos o recursos externos. El estado del lab registra el intento;
las identidades NiFi se añaden al obtenerlas. Un error de preparación o de control
de pausa/SIGKILL deja `status=failed` y ejecuta el cleanup de los recursos
intentados. STOPPED/RUNNING y SIGKILL deben confirmarse: una excepción del hilo
de control o agotar sus 30 s de intentos no constituye una inyección realizada.

Fixture: primeras N filas nominales (todas las etiquetas 0) de
`data/ai4i2020_train.csv`, cinco sensores + `machine_type`, timestamp
`2026-10-23T00:00:00Z + i s`. Mismo hash entre repeticiones de una tasa; IDs nuevos
por ocurrencia porque el `event_id` deriva de topic/partition/offset. No usa el test.

### Puntos de medida (mismo reloj CLOCK_MONOTONIC del host)

| Medida | Inicio | Fin |
| --- | --- | --- |
| Modelo en proceso (`model`) | `predict_proba`(RF)+`score_samples`(IF), una fila, `perf_counter`; 20 de calentamiento excluidas | — |
| HTTP | servidor: entrada al ASGI | último mensaje de respuesta (`api-timing.jsonl`) |
| E2E | tras `write`+`fsync` de la línea CSV | primer `_search` ES (cada 100 ms) que devuelve el documento; incluye refresh |

Percentiles nearest-rank **por run**; entre repeticiones solo media/mediana/min/max/
desviación de los p50/p95 de cada run (`cg32_load summarize`), nunca mezclados.
Lag Kafka: `end - committed` del grupo cada 2 s mediante OffsetFetch sin unirse al
grupo. CPU: integración de `docker stats` cada 2 s (aproximación). La métrica
`container_mem_usage_max_mib` es el máximo muestreado de `MemUsage` por contenedor;
la CLI Docker en Linux resta caché al uso total. No mide RSS ni un pico continuo.
El worker corre dentro de NiFi y se contabiliza en `nifi`. Los recibos históricos
con `rss_max_mib` conservan sus bytes y valores: ese campo representaba la misma
lectura `MemUsage`, con un nombre incorrecto, y no una medición de RSS.
Referencia: [Docker stats](https://docs.docker.com/reference/cli/docker/container/stats/).

El cliente exporta el certificado público desde el contenedor NiFi perteneciente
al proyecto Compose, guarda su SHA-256 en el estado privado del laboratorio y
verifica cadena y nombre `localhost` en todas las llamadas. Un certificado
ausente, sustituido o emitido para otro nombre aborta antes de enviar credenciales.
Bytes: CSV, valores Kafka, raíz del worker (`du`) y store primario ES.

### Contabilidad e IDs

`reconcile` compara conjuntos, no solo totales: líneas ofrecidas (hash) ↔ registros
Kafka (offset+hash) ↔ jobs del worker (`record_ref`) ↔ documentos ES. Publica
`observed = saved + rejected + pending`, líneas repetidas por Filebeat,
`http_repeated_posts`, ciclos NiFi por código de salida y `valid_lost`.

## Secuencia

```bash
uv sync --frozen --python 3.12 --extra kafka
LAB=/ruta/nueva/cg32-AAAAMMDD
M=/ruta/bundle-propio/manifest.json        # manifest.json + rf.pkl + if.pkl
uv run --frozen python -m scripts.cg32_lab --lab $LAB init
uv run --frozen python -m scripts.cg32_lab --lab $LAB up
uv run --frozen python -m scripts.cg32_lab --lab $LAB model --manifest $M --output $LAB/model.json
# Piloto
uv run --frozen python -m scripts.cg32_lab --lab $LAB run --manifest $M --label pilot --rate 1 --duration 10
# Medida: tres repeticiones; 50/s solo si piloto y presupuesto lo permiten
for i in 1 2 3; do uv run --frozen python -m scripts.cg32_lab --lab $LAB run --manifest $M --label base-$i --rate 10 --duration 60; done
# Recuperación (separada de las nominales)
uv run --frozen python -m scripts.cg32_lab --lab $LAB run --manifest $M --label pause --rate 1 --duration 20 --pause-at 5 --pause-for 20
uv run --frozen python -m scripts.cg32_lab --lab $LAB run --manifest $M --label kill --rate 1 --duration 20 --kill-at 6
uv run --frozen python -m scripts.cg32_load summarize $LAB/runs/base-*/run.json --output $LAB/summary-10.json
uv run --frozen python -m scripts.cg32_lab --lab $LAB discover --index <índice> --event-id <id> --output $LAB/discover
uv run --frozen python -m scripts.cg32_lab --lab $LAB stop
```

Configuración aceptada de partida (CG20): trigger 2 s, `max_records=1`,
`max_polls=3`, `attempts=1`, `timeout=0.5`, broker con
`group.initial.rebalance.delay.ms=0` (igual que CG14). Una optimización cambia
**una sola** variable (`--max-records`) y repite misma fixture y tasas; no se
añaden hilos ni consumidores al grupo (propietario único del offset).

El worker usa el Python del checkout y la API el Python 3.11 de su imagen
(`scoring/Dockerfile`); ambos deben conservar `scikit-learn==1.5.0`. La API
rechaza un bundle de otra versión sklearn (`Model/runtime sklearn mismatch`).

## Bundle reconstruido · 28/10/2026

El propietario autorizó regenerar el bundle y continuar las issues. La identidad
reconstruida se conserva en `docs/evidence/CG32_REBUILT_IDENTITY_20261028.json`;
no reemplaza el sello histórico de CG26. Para medir este candidato, añadir a
**cada** comando `model` o `run`:

```bash
--identity-record docs/evidence/CG32_REBUILT_IDENTITY_20261028.json
```

El valor por defecto sigue exigiendo CG26. La opción explícita exige ambos
artefactos y sus hashes, y los recibos distinguen `rebuilt_candidate` y guardan
el hash del registro de identidad. No mezclar corridas de ambas identidades.
La API se comprobó con `/health` y `/predict` (HTTP 200, mismo event_id). Los
pickles y el tar del bundle permanecen fuera de Git; el registro conserva rutas,
comandos y hashes para reproducirlos.
