# CG14 — restore E2E aislado, iteración 14

## Corte vigente — 22 de octubre de 2026

[Auditoría de ramas y host](evidence/CG14_BRANCH_AUDIT_20261022.md): login HTTPS
confirmado, original intacto, RESTORE 23/27/1 DISABLED con colas vacías.
El runner integrado bloquea por Script Body antiguo y persistencia Kafka legacy.
**No hay RESTORE_FUNCTIONAL_VERIFIED.** Alinear esos dos componentes conservando
los datos antes de ejecutar; no usar el runner histórico para omitir los gates.
La copia segura versionada actual tiene SHA256
`60048fc426b25d57dd4bb6f9c8c5c99a48a80e906865d3d49a210e7659f43f52`.
Los hashes `98bc…`, mounts `/tmp/kraft-combined-logs` y resultados de iteraciones
anteriores que aparecen abajo son históricos; no describen el Compose actual.
El nuevo layout exige `/var/lib/kafka` y `/var/lib/kafka/data` con entrypoint
explícito `/lab/start.sh`. No hacer otro upload ni recrear el broker existente.

## Procedimiento e historial anterior

Estado del gate (2026-10-21): **HOST_RUNNER_PREPARED / FUNCTIONAL_NOT_TESTED**.
La estructura previamente verificada continúa siendo 23 processors, 27 conexiones,
un Controller Service. Esta iteración prepara una operación; no acredita un E2E
real ni recuperación completa de servidor. No se contactó Docker/NiFi desde el
shell del agente y no se repitió ningún upload.

## Inventario inspeccionado

Fuentes: `deploy/cg14/compose.yaml`, todos los scripts de `deploy/cg14/scripts/`,
las definiciones de `nifi-flows/`, `cg14_restore_upload.py` y la definición viva
restaurada conservada en la evidencia local de iteración 12.
`deploy/cg14/restore-inventory.json` fija los 51 IDs runtime de esa copia:
23 processors, 27 conexiones y servicio
`ce5c27e6-986a-3047-bead-420bdcc8ef65`. Se comprueban contra la API antes de
operar. El inventario no es otro import ni una nueva definición ejecutable.

| Dependencia | Configuración real inspeccionada |
|---|---|
| Destino único | `CNC-GUARD-CG14-RESTORE-TEST`, `5d4f0539-01a1-1000-4a08-0a3f4c8946d8` |
| Original protegido | `583bcfb5-01a1-1000-de1a-41cdf8ea78fe`; sólo lecturas para comparación |
| API host | `https://localhost:18443/nifi-api`; CA existente `deploy/cg14/secrets/nifi-local.crt` |
| NiFi | `apache/nifi:2.12.0` por defecto en Compose; cada bundle del flujo debe ser 2.12.0 |
| Kafka | `cnc-cg14-kafka-test`, imagen 4.3.1 fijada por digest; DNS `cg14-kafka-test:9092`, PLAINTEXT en red `cg14-nifi` |
| Persistencia Kafka | Bind `deploy/cg14/data/kafka-test` → `/tmp/kraft-combined-logs`; sin puertos host |
| Mock | Imagen Python 3.13 Alpine fijada por digest; `python -u /app/mock_predict.py`, script RO, UID/GID 65534, rootfs RO, sin puertos host |
| HTTP interno mock | `0.0.0.0:8080`; GET `/healthz` → 200; otros GET → 404 |
| POST mock | `/predict/2xx` → 200; `/predict/422` → 422; `/predict/5xx` → 503; `/predict/timeout` duerme 10 s por defecto y devuelve 200 si el cliente sigue conectado |
| Otros estados mock | JSON ilegible → 400, cuerpo >1 MiB → 413, escenario desconocido → 404 |
| Estado mock | Sin contador ni almacenamiento de negocio; threads y peticiones timeout sí comparten proceso. Se crea otro contenedor exclusivo |
| DLQ | Bind existente `deploy/cg14/data/dlq` → `/opt/nifi/cg14-dlq` |
| Dependencias runner | Python estándar (Linux `fcntl`), Docker CLI, API REST del host, imagen mock ya local; no instala paquetes ni hace pull |

El runner original `run-kafka-lab-e2e.py` fija el ID del grupo original, lee `.env`
y escribe en la DLQ compartida. El runner de outage además detiene/arranca Kafka.
**Ninguno se ejecuta ni se modifica para este ensayo.** El nuevo runner sólo
reutiliza las utilidades de autenticación/lectura de `cg14_restore_upload.py`;
no llama a su `main`, multipart ni upload.

Propiedades exactas relevantes de la definición existente:

- ConsumeKafka: `Topics=cg14-outage-20261020102945z35bf08e`,
  `Group ID=cg14-outage-group-20261020102945z35bf08e`, `Topic Format=names`,
  `Processing Strategy=FLOW_FILE`, `Output Strategy=USE_VALUE`,
  `Commit Offsets=true`, `auto.offset.reset=earliest`,
  `Key Format=byte-array`, `Key Attribute Encoding=utf-8`,
  `Message Demarcator=""`, `Kafka Connection Service` referencia al CS interno.
- Kafka3ConnectionService: `bootstrap.servers=cg14-kafka-test:9092`,
  `security.protocol=PLAINTEXT`, `isolation.level=read_committed`.
- InvokeHTTP: `HTTP URL=http://mock-predict:8080/predict/${cg14.mock.scenario}`,
  `HTTP Method=POST`, `Request Content-Type=application/json`,
  `Connection Timeout=2 sec`, `Socket Read Timeout=3 sec`,
  `Socket Write Timeout=15 secs`, `Response Redirects Enabled=True` originalmente.
- DLQ PutFile: `Directory=/opt/nifi/cg14-dlq`,
  `Conflict Resolution Strategy=fail`, `Permissions=rw-------`,
  `Create Missing Directories=true`. UpdateAttribute produce
  `${uuid}-${cg14.code}-${invokehttp.status.code}-${cg14.http.attempt}.json`.
- Retry: contador `${cg14.http.attempt:replaceNull('0'):toNumber():plus(1)}`;
  rutas `retry <= 2` y `exhausted > 2`: petición inicial más dos reintentos.
  No se aceptan relaciones adicionales con retry automático.

La configuración completa de cada processor y servicio debe coincidir con la
copia segura fijada por SHA256, salvo los cambios explícitos de aislamiento.
Se comprueban tipos, bundles, auto-terminaciones, referencias y las 27 relaciones.
Scripts externos, classpaths, proxies, servicios externos, destinos nuevos,
Parameter Contexts, puertos y grupos anidados hacen abortar. Los generadores y
el probe inerte nunca se habilitan.

## Recursos exclusivos

Para el ejemplo estable `--run-id cg14it14a001` (8–32 caracteres a-z/0-9):

| Recurso | Valor exclusivo |
|---|---|
| Topic | `cg14-restore-cg14it14a001`, 1 partición, RF 1, retención 86400000 ms |
| Consumer group | `cg14-restore-group-cg14it14a001`; nunca se crea/reset con CLI, lo registra únicamente el consumidor al arrancar |
| Mock | `cg14-restore-mock-cg14it14a001`, etiqueta `cg14.restore.run=cg14it14a001`, red existente, sin publicaciones |
| HTTP URL | `http://cg14-restore-mock-cg14it14a001:8080/predict/${cg14.mock.scenario}`; redirects desactivados |
| DLQ contenedor | `/opt/nifi/cg14-dlq/restore-cg14it14a001` |
| DLQ host | `deploy/cg14/data/dlq/restore-cg14it14a001` |
| Manifiesto/evidencia | `deploy/cg14/data/evidence/restore-e2e/cg14it14a001.json`, modo 0600 |
| Correlación | `cg14.source.kind=restore-cg14it14a001`, URI con topic exclusivo, offsets propios |

Antes de crear recursos se exige ausencia del topic, group, contenedor y DLQ,
o intención propia ya registrada para reconciliar una operación interrumpida.
No se utiliza `--if-not-exists` para adoptar recursos desconocidos. Se conserva
un lock de destino común a todos los run IDs, además de revisiones optimistas NiFi.
No operar manualmente el grupo ni ejecutar otros clientes durante el ensayo.

El directorio se crea con el UID del proceso NiFi mediante `docker exec`,
`umask 077`, sin sudo. El runner verifica el bind real, escritura y ausencia de
symlinks. No cambia permisos de la DLQ original. Una discrepancia de montaje,
permisos, propiedades o IDs hace abortar; no se corrige automáticamente ampliando
permisos, cambiando red o reiniciando servicios.

## Operación desde la terminal real de Omarchy

Estar en la raíz del checkout y en `feat/14-nifi-validation`. Mantener el mismo
run ID en todos los pasos. Las credenciales `SINGLE_USER_CREDENTIALS_USERNAME` y
`SINGLE_USER_CREDENTIALS_PASSWORD` se leen primero del entorno y después de
`deploy/cg14/.env`, relativo al checkout; sólo se preguntan los valores ausentes
o vacíos. El token permanece sólo en memoria. El transporte usa
CA local, hostname verificado, sin proxy heredado ni redirects de autenticación.

```bash
cd /home/admin/Projects/B-taldea
python3 deploy/cg14/scripts/run-restore-e2e.py --plan --run-id cg14it14a001
python3 deploy/cg14/scripts/run-restore-e2e.py --apply --run-id cg14it14a001
python3 deploy/cg14/scripts/run-restore-e2e.py --verify --run-id cg14it14a001
python3 deploy/cg14/scripts/run-restore-e2e.py --test --run-id cg14it14a001
python3 deploy/cg14/scripts/run-restore-e2e.py --verify --run-id cg14it14a001
python3 deploy/cg14/scripts/run-restore-e2e.py --stop --run-id cg14it14a001
```

Ejecutar **uno por uno**, revisando código de salida y manifiesto. Un fallo
detiene el procedimiento; no continuar a `--test` si `--apply` no ha terminado.

- `--plan`: sólo lectura de archivos locales. No autentica, no abre conexiones,
  no crea directorios, locks ni manifiesto. Resultado local observado:
  `STATIC_PLAN_ONLY`, `network_used=false`, `mutations=false`, conteos 23/27/1,
  hash seguro `98bcdaa8e64d197644b2e7a1c409394f50b4c8df2946780d442c109d2658839b`;
  barreras host `NOT_TESTED`, funcionalidad `NOT_TESTED`.
- `--apply`: exige processors detenidos/deshabilitados, CS DISABLED y colas 0;
  verifica grupo, inventario, configuración, original, broker, red, montajes,
  puertos y recursos exclusivos. Guarda propiedades previas no sensibles,
  estados y hash del original **antes** de crear recursos. Crea topic/mock/DLQ
  propios, aplica sólo cuatro patches y vuelve a verificar aislamiento. No
  habilita processors ni CS. Se puede repetir antes de `--test` mientras el mock
  siga running. **No usar apply para recuperar un mock detenido: usar resume.**
- `--verify`: exige manifiesto existente; consultas GET y Docker de lectura,
  recopila estados, colas, offsets, hashes/metadatos de DLQ y consulta provenance
  ya existente. Si el mock está running, comprueba además `/healthz` (HTTP 200 y
  JSON `{"mock":true,"status":"ready"}`); registra `evidence.mock`. Si está
  detenido, registra `NOT_CHECKED_STOPPED`, que no autoriza test.
  No crea topic, group, mock ni consulta provenance nueva. Actualiza
  el manifiesto propio. Antes de `--test`, no habrá evidencia funcional.
- `--test`: exige `pending=null`, run preparado, sin intención funcional ni
  producer/activaciones/servicio previos, barreras completas de nuevo y topic
  verificado. Rechaza un consumer group ya utilizado o DLQ ausente/no vacía y
  comprueba con el UID NiFi que su directorio exclusivo permite escribir.
  Habilita CS y
  espera ENABLED/VALID. Habilita sólo la cadena conectada, consumidor al final;
  comprueba VALID antes de RUNNING. Envía una sola tanda de cinco CSV mediante
  `docker exec -i cnc-cg14-kafka-test /opt/kafka/bin/kafka-console-producer.sh`
  con `--bootstrap-server cg14-kafka-test:9092`, topic propio, `acks=all`,
  `enable.idempotence=true`, `parse.key=true`, `key.separator=|`.
  Las keys `2xx/422/5xx/timeout` se convierten en `cg14.mock.scenario` en el
  UpdateAttribute de metadatos. No hay un flujo infinito de GenerateFlowFile.
- Los cuatro CSV válidos tienen timestamps distintos y `source.kind` por run;
  sus cuatro event IDs SHA256 se calculan antes del envío, se guardan en el
  manifiesto y deben coincidir con los observados en provenance. El quinto CSV pierde una
  columna y debe rechazarse; el contrato de rechazo lleva `event_id=null`.
  Todos tienen identidad de transporte propia topic/partition/offset.
- Se espera hasta 120 s para offsets `(5,5,0)`, colas vacías, downstream sin
  threads activos y cuatro archivos DLQ. `finally` detiene y deshabilita los
  processors propios, CS propio y mock propio; SIGINT/SIGTERM entran en esta
  limpieza. No se detiene Kafka ni NiFi. Se conservan contenedores y datos.
- Registra las transiciones de estado y validación por ID en el manifiesto.
- Tras parar, crea una consulta de provenance reciente (hasta 1000 eventos),
  espera hasta 45 s y filtra en memoria por IDs restaurados y topic exclusivo.
  Sólo persiste atributos permitidos. Exige HTTP 200/422/503, timeout, contador
  final 3 para 503 y timeout, ningún intento >3, rechazo CSV, DLQ=4, cuatro
  event IDs válidos distintos, offsets 5/5/0, colas 0, componentes DISABLED y
  hash original sin cambios para declarar `VERIFIED`. Evidencia insuficiente
  produce salida 2; no se interpreta como éxito.
- `--stop`: reconciliación idempotente de los IDs con intención de habilitación
  registrada, incluso si cambió la configuración; mantiene comprobación de
  identidad. Detiene sólo el mock con etiqueta y configuración propias. No
  depende de la validez funcional para parar. Errores de stop no se ocultan.

## Recuperar el mismo run después de stop — hotfix safe mock resume

Causa confirmada: apply sólo crea el mock si su nombre no existe; después exige
que esté running. Stop conserva el contenedor, pero lo detiene. Test tampoco lo
arranca. `prepared=true` conserva los patches y no acredita disponibilidad HTTP.

El manifiesto inspeccionado para `cg14it14a001` registra `prepared=true`,
`resources_intent=true`, `stopped=true`, `functional=NOT_TESTED`, `pending=null`,
sin test_intent, producer, activated ni service_intent. El inspect suministrado
por el operador confirma el mock propio `exited`, con label del run, imagen
fijada, red `cg14-nifi`, sin puertos y bind del script RO. No se ejecutó Docker
ni NiFi desde el agente para este hotfix; el manifiesto real no se modificó.

Se añade **`--resume` explícito**: no repite apply, no crea contenedores/topics,
no cambia configuración o estados NiFi, no produce mensajes. Usa el manifiesto
existente, su lock y su mismo run ID. Antes de arrancar exige:

- Run preparado, recursos coincidentes, sin ejecución funcional previa ni otra
  operación pendiente; sólo admite reconciliar su propio arranque pendiente.
- Identidad y configuración aislada completas del RESTORE, CS propio DISABLED,
  processors detenidos/deshabilitados, colas vacías y hash del original intacto.
- Broker/montajes/red/puertos correctos, topic configurado, group aún no utilizado,
  DLQ exclusiva vacía y escribible por NiFi.
- Mock existente con nombre **y** label del run, imagen por digest, comando,
  usuario, entrypoint, rootfs RO, cap-drop ALL, no-new-privileges, sin privilegios,
  restart policy `no`, red exclusiva prevista, ningún port binding ni publicación,
  y único bind RO del script. El inventario JSON fija los componentes NiFi;
  la imagen Docker esperada está fijada por `MOCK_IMAGE` en el runner, no por
  un campo inventado en ese inventario.
- Estado `running`, `exited` o `created`, coherente con Running y sin pausa ni
  restarting; ID Docker completo, igual al registrado si ya hubo reanudación.

Si está detenido, registra/fsync la intención **antes** de un único
`docker start <ID existente>`. Si ya está running, no hace start ni restart.
Vuelve a inspeccionar el mismo ID y valida `/healthz`. El resultado queda en
`mock_resume.status` y se muestra al terminar:

- `STARTED`: arranque propio confirmado y healthy, o reconciliado después de una
  respuesta perdida observando ese mismo contenedor running y healthy.
- `ALREADY_RUNNING`: ya estaba running y healthy; ninguna orden de arranque.
- `FAILED`: fallo/interrupción de arranque o de healthz; no se autoriza test.
- `BLOCKED`: una precondición, propiedad, identidad o estado impide continuar;
  no se inicia ningún contenedor.

El registro incluye container_id, fase, intentos de arranque y fecha de éxito;
los errores guardan sólo su tipo. Mientras el arranque sea incierto conserva
`pending=resume-owned-mock` y `stopped=false` conservador. Si un segundo resume
observa el contenedor todavía detenido tras un intento incierto, **no repite
start**. Si lo observa running, sólo realiza lecturas/healthz para reconciliarlo.
Una parada explícita propia confirmada permite un nuevo ciclo stop/resume del
mismo contenedor, sin borrar el contador ni repetir fixtures. Stop confirma el
estado detenido mediante inspección; puede resolver así la incertidumbre del
arranque propio. No resuelve ni autoriza repetir una producción Kafka incierta.

Desde la terminal real de Omarchy, **uno por uno**, sin ejecutar apply:

```bash
cd /home/admin/Projects/B-taldea
python3 deploy/cg14/scripts/run-restore-e2e.py --resume --run-id cg14it14a001
python3 deploy/cg14/scripts/run-restore-e2e.py --verify --run-id cg14it14a001
```

Exigir salida 0 en ambos; resume STARTED/ALREADY_RUNNING, pending null, mock
running y `evidence.mock.healthz=READY`, configuración aislada intacta, colas 0,
sin ejecución funcional anterior ni nueva incertidumbre. Verify no inicia el
mock: si vuelve a aparecer detenido, investigar antes de test.

Sólo después de superar estas condiciones, la operación funcional prevista es:

```bash
python3 deploy/cg14/scripts/run-restore-e2e.py --test --run-id cg14it14a001
```

El test vuelve a comprobar todas las barreras; la habilitación de CS y processors
debe confirmar VALID antes de llegar al producer. Este hotfix **no ha ejecutado
fixtures reales**, y no acredita todavía la funcionalidad del host.

Ante cualquier fallo, detener únicamente los recursos habilitados del run:

```bash
python3 deploy/cg14/scripts/run-restore-e2e.py --stop --run-id cg14it14a001
```

No editar el manifiesto a mano, borrar el mock, repetir apply, cambiar run ID
ni enviar de nuevo una tanda con resultado incierto.

## Interrupciones y rollback

El manifiesto se escribe con rename atómico y fsync antes de cada mutación.
`pending` describe una respuesta pendiente/incierta. No hay reintentos de red
para escrituras. Topic/mock/configuración se reconcilian mediante lecturas en
un nuevo `--apply`, antes de que haya intención de test. Repetir `--apply` no
crea otro grupo ni vuelve a configurar propiedades ya correctas.

En cuanto existe `test_intent`, incluso si el envío no llegó a iniciarse,
**no se permite repetir `--test` ni `--apply` para ese run**. `producer=
OUTCOME_UNCERTAIN` no es confirmación de cero mensajes ni de cinco mensajes.
Conservar topic y offsets, usar `--verify` y `--stop`; nunca volver a enviar a
ciegas. Si se pierde el ID de una consulta provenance, no se recrea
silenciosamente: esa prueba puede quedar sin evidencia suficiente.

Rollback explícito opcional, con el manifiesto existente:

```bash
python3 deploy/cg14/scripts/run-restore-e2e.py --rollback --run-id cg14it14a001
```

Primero hace stop propio, exige colas vacías y configuración reconocida; restaura
sólo las propiedades cambiadas de los cuatro processors desde su snapshot.
Deja los componentes tocados DISABLED, aunque antes estuvieran STOPPED.
Esto devuelve referencias compartidas a una copia **inactiva**: nunca arrancarla
manualmente. Conserva topic, consumer group, DLQ, mock detenido y evidencias;
no elimina contenedores, mensajes, volúmenes ni directorios. Un nuevo ensayo,
tras rollback seguro, requiere otro run ID y otro `--apply`. Si hay colas
residuales, rollback aborta: inspeccionarlas, no vaciarlas automáticamente.

## Efectos y riesgos pendientes

Decisión D14: reutilizar sólo broker/red/instancia NiFi de laboratorio; aislar
los destinos de datos por run. Motivo: preservar import y flujo original sin
reinicios. Impacto: siguen compartidos CPU/RAM/disco, logs, índices de provenance
y repositorios NiFi/Kafka. Rollback: operación anterior, limitada al destino.

| Riesgo | Trigger y mitigación | Contingencia / responsable / revisión |
|---|---|---|
| HIGH: recursos compartidos del servidor | Disco/CPU/threads agotados; sólo 5 registros, mock con límites, retención topic 24 h; no repetir tandas | Stop propio y conservar datos; operador del host; revisar antes de apply/test |
| HIGH: envío incierto o muerte abrupta | SIGKILL, fallo CLI/API o pérdida de respuesta; intent durable, lock y prohibición de replay | Verify/stop, inspección de offsets y manifiesto; operador; tras interrupción |
| HIGH: drift entre operaciones | Cambios manuales o por otro cliente; IDs fijados, propiedades completas, hash del original y revisión API | Abortar, stop de IDs propios; operador; antes de cada activación |
| Evidencia provenance incompleta | Índice tarda, consulta expira o >1000 eventos recientes | No declarar VERIFIED; conservar manifiesto/offsets/DLQ; operador, tras test |
| Diferencia export/API | Valores por defecto, estados o DTO distintos | Abortar sin activar; inspeccionar diferencia y ajustar con evidencia; mantenedor, primer apply |
| Permisos bind/imagen no local | UID host no puede leer DLQ o imagen fijada no está en cache | Abortar, sin chmod global ni pull automático; operador, primer apply |

Los commits Kafka acreditan consumo, no entrega exactamente una vez ni ausencia
de duplicados semánticos. Los logs/provenance siguen siendo de la misma instancia;
los filtros aíslan la evidencia, no los repositorios. Se crea una consulta de
provenance global de lectura durante `--test`; sólo se guardan eventos propios.
Autenticación y comandos Docker/API pueden dejar sus metadatos normales de auditoría.
No hay acceso a predictor de producción, CNC, alertas, CG13 ni destinos de negocio.

## Registro de evidencia y validación local

- Runner nuevo: `deploy/cg14/scripts/run-restore-e2e.py`.
- Inventario fijado: `deploy/cg14/restore-inventory.json`; hash
  `2231b311018f7dc50a9a130dc556a895f20b9959c9ebbf3e213280ca45de32da`.
- Mock existente sin cambios, hash verificado por runner:
  `5d3a55f96177a5639b71ff64b4828abf6890f56e581f6c564a1f166f3241c2bc`.
- Tests nuevos: `tests/test_cg14_restore_e2e.py`, dobles locales sin daemon/API.
  Cobertura de selección/IDs, aislamiento, recursos compartidos, abortos,
  idempotencia de apply/configuración, reconciliación tras interrupción, no replay,
  stop, rollback, secretos y criterios funcionales positivos/negativos.
- Hotfix safe mock resume: `PYTHONPATH=. ./.venv/bin/pytest -q`: **209 passed**,
  conservando los 167 tests previos. Pruebas sin Docker/NiFi: detenido/running,
  propiedad, imagen, red, puertos, mounts, ejecución, healthz, interrupción,
  manifiesto durable, prohibición de duplicación/restart, mock original y barreras
  previas al test; ciclo stop/resume confirmado sin replay funcional.
- `git diff --check`: exit 0. `--plan`: exit 0, sin red ni mutaciones del runner.
- Siguiente gate del run existente: ejecutar resume/verify y, sólo tras superar
  las barreras, test/verify/stop en la terminal autorizada del host
  y revisar su manifiesto. ENABLED/VALID, HTTP, timeout, DLQ, provenance y offsets
  del RESTORE real continúan **NOT_TESTED** en esta iteración.

Contrato de estados REST contrastado con la
[API oficial NiFi](https://nifi.apache.org/nifi-docs/rest-api.html).
La aceptación definitiva de la configuración y sus estados corresponde a la
instancia host 2.12.0; las pruebas locales no sustituyen esa comprobación.

## Presentación del canvas conservada — petición del propietario, 2026-10-21

Se ordenó visualmente RESTORE-TEST desde la UI autenticada de Chrome del host:
fixtures en la columna izquierda; Kafka, metadatos y validador en la siguiente;
rutas, HTTP y salidas alineados; reintentos y DLQ en las filas inferiores.
Colores por función: gris azulado para CSV/probe, azul para Kafka, verde azulado
para validación, ámbar para rutas/reintentos, violeta para HTTP, verde para
aceptados y rojo para DLQ/errores. Comprobación DOM final: 23 processors,
27 conexiones y cero superposiciones entre processors.

**Preferencia permanente: conservar esta distribución.** Los cambios funcionales,
pruebas E2E, resume/stop y mantenimiento posterior no deben aplicar auto-layout,
mover bloques ni sustituir estilos. Cambiar la presentación sólo por petición
expresa del propietario. La referencia de posiciones y colores observados está
en `deploy/cg14/restore-layout.json`; es documentación visual, no una definición
para importar ni una operación automática de restauración.

Se cambiaron posiciones y colores, sin activar componentes, ejecutar fixtures,
reimportar ni editar propiedades funcionales, endpoints o relaciones. El grupo
original no se abrió ni modificó. Las definiciones JSON fijadas por hash, el
inventario y el manifiesto E2E existente se conservaron.
