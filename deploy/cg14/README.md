# Despliegue local de NiFi para CG14

> Estado vigente para publicar: ver [handoff CG14](../../docs/CG14_TECHNICAL_HANDOFF.md).
> Las secciones de evidencia siguientes son históricas; sus JSON de runtime
> permanecen locales e ignorados. Para RESTORE-TEST usar el
> [runbook específico](../../docs/CG14_RESTORE_E2E.md), sin repetir importación
> ni utilizar los runners del grupo original.

Despliegue aislado: no reutiliza ni modifica los Compose de la raíz, no inicia Kafka de forma predeterminada y no publica Kafka, Elasticsearch ni APIs. El broker `kafka-test` requiere el perfil explícito `kafka-test` y no publica puertos de host. NiFi escucha únicamente en `127.0.0.1:18443`; para compañeros se recomienda un túnel SSH.

## Estado y versión

Se fija Apache NiFi `2.12.0`, versión explícita disponible a fecha de esta preparación. NiFi 1 dejó de recibir soporte en diciembre de 2024 y NiFi 1.25.0 está afectado por advisories posteriores; 2.12.0 incluye correcciones de seguridad más recientes. Referencias: [descargas/ciclo de soporte](https://nifi.apache.org/download/) y [advisories de Apache](https://nifi.apache.org/documentation/security/). CG14 mantiene un flow exportado para NiFi 1.25.0; NiFi 2 no garantiza compatibilidad automática de NAR/flows NiFi 1. Por eso este Compose no importa ni ejecuta ese JSON. Valida el flow/script y sus processors contra 2.12.0 en una instancia limpia antes de adaptarlo conscientemente.

La imagen oficial configura autenticación de usuario único. **No crea identidades NiFi independientes para compañeros**; para roles distintos se necesita OIDC/LDAP y políticas de autorización.

## Requisitos y arranque

Docker Engine y Compose plugin; Engine 28+ recomendado para aislamiento de puertos localhost. El límite predeterminado del contenedor es 5 GiB y heap máximo 2 GiB. Ajusta `.env` según el host.

```bash
cd deploy/cg14
./scripts/init-secrets.sh
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f compose.yaml up -d
docker compose --env-file .env -f compose.yaml ps
```

El inicializador genera credenciales aleatorias y `NIFI_SENSITIVE_PROPS_KEY` en `.env`, con permisos `0600`, sin imprimir valores y sin reemplazar un archivo existente. `.env` está excluido de Git. Restringe el acceso al Docker daemon: el administrador del host puede leer variables del contenedor mediante la API de Docker/`inspect`.

URL local: <https://localhost:18443/nifi>. Se usa el puerto 18443 porque otro proyecto Docker ya publica 8443 en todas las interfaces; no se detuvo ni alteró ese servicio. HTTPS está activo; la imagen genera certificado local autofirmado, que el navegador no confiará inicialmente. Exporta el certificado público y revisa la huella por un canal confiable:

```bash
mkdir -p secrets && chmod 700 secrets
docker exec cnc-cg14-nifi openssl s_client -connect localhost:8443 -servername localhost -showcerts </dev/null 2>/dev/null | openssl x509 -out secrets/nifi-local.crt
openssl x509 -in secrets/nifi-local.crt -noout -fingerprint -sha256
curl --cacert secrets/nifi-local.crt https://localhost:18443/nifi/
```

Distribuye ese certificado público a los equipos autorizados e instálalo en su almacén de confianza según las políticas del sistema. No aceptes una huella no verificada ni desactives validación TLS permanentemente.

Parada sin borrar datos: `docker compose --env-file .env -f compose.yaml stop`. Reanudar: sustituye `stop` por `start`. `down` elimina contenedor y red, pero conserva volúmenes nombrados. Nunca uses `down -v`.

## Acceso por túnel SSH

La plantilla de configuración restringida, comandos para Windows/Linux y pasos administrativos están en [`ssh/README.md`](ssh/README.md). El servicio está `inactive`/`disabled`, no escucha en 22 y no hay host keys visibles. La sintaxis de un candidato temporal pasó `sshd -t`/`sshd -T -C`; la configuración efectiva instalada falla por falta de host keys. No se habilitó SSH ni se modificaron usuarios o firewall. Acceso desde un segundo equipo: `NOT_TESTED`.

## Kafka y pipeline CG14

El Compose raíz activa solo `scoring-api`; Kafka, Filebeat, NiFi, Elasticsearch y Kibana aparecen comentados. `filebeat/filebeat.yml` no configura output. No hay contrato CG13 aprobado en este checkout ni topics confirmados. No se activa consumo productivo ni se inventan endpoints `/predict`.

Auditoría read-only de otros proyectos: los cuatro contenedores `iabd-kafka`, `iabd-kafka-1/2/3` están detenidos. Los nodos 1–3 pertenecen a `/home/admin/Big_Data/07_BD_Aplikatua/3_Apache_Kafka/2-kasua-kafka-klusterra/compose.yaml`; sus listeners configurados usan PLAINTEXT, anuncian `kafka-N:19092` dentro del clúster y `localhost:9092–9094` hacia fuera, y el Compose publica esos puertos sin limitar la interfaz. El proyecto Compose actual no tiene endpoints Kafka en su red `nifi-net`; no se confirmó alcance LAN ni TCP a un broker activo. Otro Compose fuera de este repo contiene una contraseña NiFi débil en claro; su propietario debe rotarla y retirar el secreto del historial conforme a su proceso. Ninguno de esos servicios o archivos se modificó.

Mientras CG13 siga pendiente, existe un broker local opcional. Está fijado a Apache Kafka 4.3.1 por digest, solo en el perfil `kafka-test`, sin puertos de host, con volumen propio y red CG14. Solo se usa `cg14-test-raw`, separado de cualquier topic del equipo. Apache publica 4.3.1 como versión soportada y ofrece su imagen Docker oficial ([releases](https://kafka.apache.org/community/downloads/), [Docker](https://kafka.apache.org/43/getting-started/docker/)). Arráncalo expresamente y ejecuta el smoke test sintético:

```bash
cd deploy/cg14
docker compose --env-file .env -f compose.yaml --profile kafka-test up -d kafka-test
docker compose --env-file .env -f compose.yaml --profile kafka-test ps
./scripts/kafka-test-smoke.sh
docker exec cnc-cg14-nifi getent hosts cg14-kafka-test
docker exec cnc-cg14-nifi bash -lc 'timeout 3 bash -c "</dev/tcp/cg14-kafka-test/9092"'
```

El smoke crea solo `cg14-test-raw` y publica/consume `tests/fixtures/cg14/valid_event.csv`; no consume mensajes reales ni ejercita el processor NiFi. Detén únicamente el broker opcional con `docker compose ... stop kafka-test`; conserva su volumen.

El Process Group CG14 incluye `org.apache.nifi.kafka.processors.ConsumeKafka`, bundle `org.apache.nifi:nifi-kafka-nar:2.12.0`, y `Kafka3ConnectionService`. En NiFi 2.12 `FLOW_FILE` crea un FlowFile por mensaje Kafka; se comprobó con cinco mensajes sintéticos. `DEMARCATOR` puede combinar mensajes y no se usa para esta prueba. `RECORD` requiere Record Reader/Writer y no se usa porque el framing y los bytes raw deben conservar el contrato CSV. `Commit Offsets` está habilitado en el processor de laboratorio; una caída del broker mostró que todavía no hay evidencia de reanudación/commit en esa condición. Esto no prueba exactly-once. El consumer y todos los processors quedan detenidos al finalizar los tests.

Para conservar trazabilidad por evento, la opción de ingestión a evaluar primero es `DEMARCATOR` sin combinar mensajes, de modo que cada mensaje Kafka se preserve como FlowFile; validar esa configuración frente a los mensajes CG13 antes de activar. Si se selecciona `RECORD`, dividir por registro y transferir los metadatos Kafka correspondientes antes de calcular `event_id`. Las opciones exactas dependen de si un mensaje Kafka contiene una fila CSV o un record set y de la semántica de `event_id` ratificada por CG03. El grupo actual no tiene consumidor ni publicador real y permanece detenido. El export de la instancia actual con DLQ está en [`nifi-flows/cg14_validation_flow_nifi_2.12.0_dlq.json`](../../nifi-flows/cg14_validation_flow_nifi_2.12.0_dlq.json); no se importó el JSON NiFi 1.x.

El grupo contiene generadores manuales detenidos para fixtures CSV, el validador Groovy que comparte fuente con los tests Python, rutas accepted/rejected y sinks de integración local que registran una whitelist de atributos, sin payload. Los generadores esperan un día entre ejecuciones para evitar producción accidental si alguien los inicia. `InvokeHTTP` apunta solamente al servicio Docker opcional `http://mock-predict:8080/predict/<scenario>`; no representa `/predict` real. El rechazo se audita por atributos y después se conserva como archivo JSON en `deploy/cg14/data/dlq`, con permisos `0600`, filename UUID/código/estado/contador y volumen bind persistente. Es una DLQ local de desarrollo, no un destino compartido ni una garantía de backup; los fallos de escritura se enrutan al sink local de error de motor.

`CSVReader`/`ConvertRecord`/`ValidateRecord` y `JsonRecordSetWriter` no se insertaron delante del validador: convertir y reserializar la línea CSV puede alterar los bytes que se usan para `event_id` y `raw_record`. Antes de introducirlos hace falta definir en CG03/CG13 el framing por mensaje y preservar/capturar el registro raw exacto. El Groovy existente valida estructura y contrato en el mismo paso.

El mock sólo se inicia explícitamente: `docker compose --env-file .env -f compose.yaml --profile integration-mocks up -d mock-predict`. No publica puertos host. Sus rutas `/predict/2xx`, `/predict/422`, `/predict/5xx` y `/predict/timeout` son simulaciones, no endpoints reales.

## Persistencia, backup y restauración

Se montan seis volúmenes nombrados para configuración/estado y repositorios, además del bind mount `deploy/cg14/data/dlq` para rechazos; el broker opcional usa su propio bind mount aislado. Comprueba montaje con `docker inspect cnc-cg14-nifi`; evita copiar `Config.Env` a informes. Para backup consistente: detener NiFi, archivar los volúmenes `cg14-nifi-*` y `.env` en almacenamiento cifrado, y reiniciar. Conserva `NIFI_SENSITIVE_PROPS_KEY` para leer valores sensibles cifrados. Restaurar requiere detener servicio, recuperar volúmenes con permisos/propietario correctos y `.env` modo `0600`, y arrancar. Ensaya en volúmenes separados; no sobrescribas datos existentes.

## Diagnóstico y matriz futura CG14

`./scripts/diagnose.sh` no imprime `.env`, entorno del contenedor ni logs. Antes de compartir logs, revísalos y redacta. La exposición esperada de esta instancia es `127.0.0.1:18443/tcp`. Existe otro NiFi en contenedor ajeno a este Compose que ya publica `0.0.0.0:8443` y `[::]:8443`; este despliegue no lo modificó. Por ello, el requisito global “ningún NiFi accesible directamente desde LAN” queda `BLOCKED` hasta que el responsable de ese otro proyecto restrinja su publicación. La prueba desde otro equipo autorizado aún está pendiente.

| Caso | Evidencia necesaria | Estado |
|---|---|---|
| CSV válido → HTTP 2xx | Flow NiFi → mock 200 → sink accepted; sin error Groovy | VERIFIED (mock local) |
| CSV inválido / header / campos ausentes / tipos | Rutas de rechazo y códigos `MALFORMED_CSV`, `HEADER_ROW`, `INVALID_NUMERIC` en logs whitelist | VERIFIED (fixtures sintéticos) |
| HTTP 422 | Mock devolvió 422; InvokeHTTP procesó `No Retry` hacia rechazo | VERIFIED (mock local) |
| HTTP 5xx | Mock devolvió 503 tres veces (inicial + dos reintentos); cola drenada | VERIFIED (mock local) |
| Timeout | Mock retrasó respuesta; `Socket Read Timeout=3 sec`; tres solicitudes observadas, DLQ con intento 3 y `event_id` | VERIFIED (mock local) |
| Retry limitado | Contador FlowFile y RouteOnAttribute limitan a dos retries; validado con 5xx y timeout | VERIFIED (mock local) |
| Dead-letter/rechazo durable | Fixtures inválido, HTTP 422, 503 y timeout escribieron JSON local en modo `0600`; 422/503/timeout conservaron `event_id`, 503/timeout registraron contador 3; 6 archivos sobrevivieron reinicio | VERIFIED (DLQ local, no compartida) |
| Trazabilidad `event_id` | Hash se crea en el flow y viaja como atributo; integración end-to-end con servicio real pendiente | PARTIAL |
| Provenance/histórico | Provenance real consultado para los topics sintéticos; sin histórico/retención fuera del repositorio local | VERIFIED (laboratorio CG14) |
| Kafka real RAW / Consumer Group | Los cuatro brokers ajenos están detenidos; contrato CG13/CG03 no confirmado | BLOCKED |
| Kafka local de prueba | KRaft 4.3.1 aislado; smoke fixture sintético y DNS/TCP desde NiFi | VERIFIED (no es CG13) |

## Evidencia de esta ejecución

**Estado de referencia de iteraciones anteriores; actualizado por la sección Iteración 4 al final de este archivo.**

Host observado: Omarchy/Arch, LAN `192.168.75.205/24`; Docker Engine `29.9.1` (cumple el mínimo recomendado), RAM total 31 GiB y disco libre inicial 645 GiB.

- `docker compose config --quiet`: VERIFIED.
- Apache NiFi 2.12.0: running/healthy; UI HTTPS devuelve 200 y el endpoint de acceso sin credenciales devuelve 401. El token endpoint aceptó las credenciales locales (201). HTTPS validado con el certificado exportado mediante `curl --cacert`, incluido SAN `localhost`.
- Seis volúmenes nombrados para conf, state y los cuatro repositorios: montados y escribibles. El hash de `conf/flow.json.gz` fue idéntico antes/después de `docker compose restart` y `compose stop/start`. Tras construir el grupo CG14 y añadir el sink DLQ, el Process Group `CNC-GUARD-CG14-DEV` contiene 21 processors (20 detenidos y un probe deshabilitado), 25 conexiones y 0 inválidos; persistió tras reinicios. El DLQ guardó seis archivos sintéticos con modo `0600`; el conteo se mantuvo tras un segundo reinicio de NiFi.
- `restart: unless-stopped`, límite 5 GiB/3 CPU, heap máximo 2 GiB, `privileged=false`, `cap_drop=ALL`, sin `docker.sock`. La publicación es únicamente `127.0.0.1:18443->8443`; intento contra `192.168.75.205:18443` fue rechazado. NiFi usó aproximadamente 1.05 GiB durante la medición.
- Los valores de credenciales y la clave sensible no aparecieron en las últimas 500 líneas del contenedor. `.env` es local, modo `0600` e ignorado por Git.
- Kafka real: `iabd-kafka`, `iabd-kafka-1/2/3` `exited`; sin Kafka activo del equipo. El Compose del clúster publica PLAINTEXT 9092–9094 all-interface y anuncia `localhost` en sus listeners externos; no se modificó ni se probó desde LAN. Broker local de prueba `cnc-cg14-kafka-test` healthy, topic `cg14-test-raw`, round-trip del fixture `valid_event.csv` PASS; desde NiFi DNS y TCP 9092 PASS. El test no usa NiFi ConsumeKafka ni representa CG13.
- SSH: OpenSSH 10.6p1; `systemctl is-active/is-enabled` devuelve `inactive`/`disabled`; no listener :22, NiFi solo loopback :18443. Sistema `sshd -t` falla sin host key. Candidato aislado `sshd -t`/`sshd -T -C` válido con clave temporal. No se aplicó configuración ni se tocó firewall. Prueba LAN pendiente.
- El firewall no se pudo leer (`nft`/`iptables` devolvieron `Operation not permitted`); no se modificó ninguna regla. No fue posible probar desde un segundo ordenador LAN.
- Ya había otro NiFi de un Compose distinto (`/home/admin/nifi/ariketak/06-ariketa-mariadb-mongodb`) publicando 8443 en `0.0.0.0` y `[::]`, junto con 8081, MongoDB 27017 y MySQL 3306. No se detuvo ni alteró. Su alcance LAN efectivo depende del firewall y permanece por revisar; bloquea declarar que ningún NiFi está expuesto en el host.
- El grupo CG14 tiene 23 processors y 27 conexiones en NiFi 2.12.0; 0 inválidos; ConsumeKafka y Kafka3ConnectionService presentes y detenidos al cierre. PublishKafka no forma parte del flujo actual.
- Pruebas CG14 actuales: `PYTHONPATH=. ./.venv/bin/pytest -q` -> `90 passed`; `git diff --check` sin errores.
- Pruebas NiFi ejecutadas con fixtures sintéticos: validador sin error de motor; CSV inválido/header/campos/tipos rechazados; mock 200 accepted; HTTP 422 escrito a DLQ con `event_id` y status en filename; 503 produjo tres solicitudes (inicial + dos reintentos), DLQ con contador 3 y `event_id`; timeout de lectura de 3 s produjo tres solicitudes, DLQ con contador 3 y `event_id`. Se drenaron colas de accepted que aparecieron durante la parada; al cierre el grupo quedó detenido y sin colas.
- Mock sólo dentro de `cg14-nifi`, sin puertos host. DNS se corrigió al alias Compose `mock-predict`; la prueba desde NiFi validó DNS y acceso antes de ejecutar processors.

El valor débil de acceso que aparecía en `README.md` y `ENUNTZIATUA.md` fue retirado de los archivos actuales. Sigue en el commit histórico inicial; no se reescribió historial. Rota cualquier instancia que lo haya usado y coordina cualquier limpieza del historial por separado.

## Iteración 4 — cierre de evidencia (2026-10-20)

Esta sección actualiza los estados y conteos históricos anteriores.

- E2E sintético más reciente: `data/evidence/2026-10-20/kafka-e2e-20261020-121056-b65d66/e2e-summary.json` (evidencia local no publicada). 5 mensajes → 5 FlowFiles; 2 `accepted`, 3 `rejected`, 3 escrituras DLQ modo `0600`; offset final 5/5, lag 0, queue 0. Eventos de provenance: `RECEIVE` 5, `CONTENT_MODIFIED` 5, `ROUTE` 5, `CLONE` 2, `FORK` 2, `FETCH` 2, `SEND` 5, `DROP` 3. El mock interno respondió HTTP 200 para los dos registros válidos.
- Los dos eventos idénticos de entrada produjeron el mismo `event_id`, con offsets Kafka diferentes. No hay deduplicación persistente y ambos llegaron al InvokeHTTP mock: idempotencia de efectos externos `PARTIAL`.
- Se reinició únicamente NiFi con colas vacías; el grupo (23 processors/27 conexiones), el ConsumeKafka 2.12.0 y `Kafka3ConnectionService` habilitado persistieron. NiFi volvió a `healthy`, HTTPS autenticado respondió 200 y el E2E normal posterior pasó.
- Prueba de caída del Kafka de laboratorio: evidencia `data/evidence/2026-10-20/kafka-e2e-20261020-120637-4bac4b/outage-test.json` (evidencia local no publicada). Broker restaurado a `healthy`, pero el intento expiró sin offset/group committed ni provenance para los cinco mensajes. Recuperación automática del consumer tras outage: `PARTIAL`, no superada.
- `PYTHONPATH=. ./.venv/bin/pytest -q`: 90 passed. `docker compose -f deploy/cg14/compose.yaml config --quiet` y `git diff --check`: exit 0. API HTTPS autenticada: 200; sin credenciales: 401. Puerto publicado `127.0.0.1:18443`; Kafka y mock sin publicación host.
- SSH: OpenSSH 10.6p1, servicio `inactive`/`disabled`; no se observan host keys y `sshd -t` falla por ausencia de host keys. No hubo cambios administrativos. Segundo equipo/túnel: `NOT_TESTED`.
- Servicios de otros proyectos no fueron modificados. Docker muestra `iabd-nifi` en `0.0.0.0` y `[::]` para 8081/8443, MongoDB en 27017 y MySQL en 3306. Son publicaciones potenciales verificadas, pero no se pudo leer el ruleset del host ni probar desde otro ordenador; la accesibilidad LAN efectiva queda `NOT_TESTED`.
- El broker CG13 y su contrato/topic RAW siguen sin confirmar. No hay flujo productivo ni deduplicación durable; no se consumieron mensajes reales.

## Iteración 5 — recuperación de outage Kafka (2026-10-20)

### Análisis de causa raíz

El informe anterior `data/evidence/2026-10-20/kafka-e2e-20261020-120637-4bac4b/outage-test.json` (evidencia local no publicada) mostró cinco registros en el log, sin offset del consumer group ni provenance. Al revisar el runner, el modo de outage no hacía baseline: detenía Kafka antes de arrancar ConsumeKafka, consideraba `state=RUNNING` prueba de actividad real y publicaba tras observar el healthcheck del broker. Por eso aquella evidencia no permitía separar un fallo de rejoin de una condición de carrera o una falta de observabilidad del propio ensayo; no demuestra un defecto del processor.

El ensayo controlado identificó además un falso negativo reproducible del runner: el snapshot NiFi `flowFilesOut` puede reiniciarse al volver a programar el processor. En una ejecución, Kafka había alcanzado offset 6/6, lag 0 y cola vacía, pero el delta del contador fue −15 y el runner lo rechazó. Se corrigió el gate para basarse en offsets comprometidos exactos y cola drenada; los contadores NiFi se guardan como diagnóstico, y el éxito final exige seis eventos `RECEIVE`, seis offsets distintos y seis `event_id` únicos en provenance. No se alteró `ConsumeKafka`, el Controller Service ni ningún offset.

### Resultado del ensayo

Comando reproducible: `python -u deploy/cg14/scripts/run-kafka-outage-recovery.py --runs 3 --timeout-seconds 120 --outage-seconds 12`. Cada repetición creó un topic y group aislados, envió tres registros válidos antes de la interrupción, mantuvo el mismo processor/group, detuvo y arrancó exclusivamente `cnc-cg14-kafka-test`, esperó la API del broker y DNS/TCP desde NiFi, y publicó tres eventos nuevos.

| Ejecución | Baseline | Recuperación | Provenance | DLQ nueva | Estado |
|---|---|---|---|---:|---|
| `data/evidence/2026-10-20/outage-20261020T102835Z-1-2afecb/outage-recovery.json` (evidencia local no publicada) | 3/3, offset 3, lag 0 | 6/6, offset 6, lag 0 | 6 RECEIVE, 6 offsets e IDs únicos | 0 | VERIFIED |
| `data/evidence/2026-10-20/outage-20261020T102910Z-2-68b471/outage-recovery.json` (evidencia local no publicada) | 3/3, offset 3, lag 0 | 6/6, offset 6, lag 0 | 6 RECEIVE, 6 offsets e IDs únicos | 0 | VERIFIED |
| `data/evidence/2026-10-20/outage-20261020T102945Z-3-5bf08e/outage-recovery.json` (evidencia local no publicada) | 3/3, offset 3, lag 0 | 6/6, offset 6, lag 0 | 6 RECEIVE, 6 offsets e IDs únicos | 0 | VERIFIED |

Los logs del primer ensayo incluyen desconexión del nodo, rebootstrap al listener `cg14-kafka-test:9092` y reconexión; en las tres regresiones el mismo grupo llegó a lag cero. El broker terminó `healthy`, NiFi `healthy`, 23 processors/27 conexiones, cero inválidos, cola vacía y processors de test detenidos (el probe preexistente continúa disabled). El topic retiene los seis mensajes de cada repetición; no se borraron topics, offsets, volúmenes ni DLQ. Los eventos son sintéticos válidos, por lo que el resultado esperado fue cero nuevos archivos DLQ.

### Idempotencia y límites

La prueba CG14 previa demostró que dos mensajes idénticos producen el mismo `event_id` pero ambos llegan a HTTP. El diseño persistente requerido y los casos de prueba posteriores están en [`IDEMPOTENCY.md`](IDEMPOTENCY.md); no se implementó deduplicación porque CG03 aún debe definir la identidad y no se dispone del API/destino real. Esta recuperación confirma lectura y commit de offsets en el broker de laboratorio, no exactly-once ni supresión durable de efectos externos. CG13 real, acceso remoto SSH y replay de un mismo evento a través de API/destino siguen pendientes.

### Regresión de software y seguridad local

Tras añadir tres tests del gate/parser: `PYTHONPATH=. ./.venv/bin/pytest -q` → **93 passed** (90 previos + 3 nuevos). `docker compose --env-file .env -f compose.yaml config --quiet`, `python -m py_compile` y `git diff --check` terminaron correctamente. TLS con certificado local: UI 200; API sin autenticación 401 y API autenticada accesible. La publicación de NiFi sigue solo en `127.0.0.1:18443`; Kafka y mock no publican puertos host. No se modificaron contenedores ajenos. Estado global del proyecto: `PARTIAL` hasta confirmar CG03/CG13, probar el túnel desde otro equipo y resolver el SSH administrativo pendiente.
