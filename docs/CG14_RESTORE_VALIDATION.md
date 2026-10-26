# CG14 — runbook de restauración aislada de NiFi 2.12.0

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

Estado actual: **PARTIAL — importación real confirmada (HTTP 201); pruebas
funcionales pendientes**. Resultado del 2026-10-21 al final de este documento.
La copia segura
[`cg14_validation_flow_nifi_2.12.0_restore_safe_20261020.json`](../nifi-flows/cg14_validation_flow_nifi_2.12.0_restore_safe_20261020.json)
deriva del snapshot capturado de NiFi y conserva los 23 processors, 27
conexiones y el Controller Service. En esta copia todos los processors y
Controller Services tienen `scheduledState: DISABLED`; el grupo original y el
snapshot de origen no se alteraron.

## Hallazgo de GOAL 30

En `nifi-flows/cg14_validation_flow_nifi_2.12.0_live_20261020.json`,
`flowContents.controllerServices[0]` es `CG14 lab Kafka3 connection`, tipo
`org.apache.nifi.kafka.service.Kafka3ConnectionService`, bundle
`nifi-kafka-3-service-nar:2.12.0`; allí aparece `scheduledState: DISABLED`.
También hay un processor diferente deshabilitado: `Unused Groovy API probe — no
input` (`flowContents.processors[]`). No se debe confundir ese campo con la
lectura operativa del API.

La REST API oficial marcada **Version 2.12.0** muestra `scheduledState` como
parte de la definición de flujo versionada; el API de Controller Services, por
separado, expone `component.state` como estado operativo. Que ambos campos
usen valores ENABLED/DISABLED no los hace equivalentes: describen objetos y
contextos diferentes. Interpretar `scheduledState` como el estado solicitado
por la definición al importar es una inferencia basada en el modelo y en el
endpoint de upload, no un resultado demostrado aquí. La copia preparada deja
ese campo en DISABLED; la única comprobación concluyente para esta instancia es
consultar el componente tras importar la copia. [REST API NiFi 2.12.0](https://nifi.apache.org/nifi-docs/rest-api.html)

La API viva consultada al comenzar esta auditoría informó para el grupo original:
`ENABLED`, cero errores de validación; el export indicó `DISABLED`. El tipo,
bundle y propiedades inspeccionadas no sensibles coincidían. GOAL 31 no puede
confirmar el estado post-import hasta ejecutar una importación aislada.

## Preflight

1. Verificar el estado Git y conservar el hash del export de origen.
2. Usar una instancia NiFi 2.12.0 de laboratorio con volúmenes exclusivos
   `cg14-restore-*`. La alternativa es un Process Group hermano en
   `cnc-cg14-nifi` únicamente si el propietario confirma que esa instancia y sus
   repositorios son de laboratorio (no producción).
3. No ejecutar `init-secrets.sh` contra un `.env` existente. Confirmar que el
   archivo de acceso tiene las variables esperadas y modo `0600`, sin mostrar
   valores. No reiniciar el NiFi original para arreglar credenciales.
4. Confirmar que el snapshot no contiene `ConsumeKafka` dirigido a ningún broker
   real. En el artefacto preparado el processor, todos los demás processors y el
   Controller Service están `DISABLED`.
5. Confirmar que el Process Group original conserva su ID y conteos. No usar el
   endpoint de reemplazo `PUT /process-groups/{id}`; la prueba debe crear un
   grupo nuevo mediante `POST /process-groups/{rootId}/process-groups/upload`.

El endpoint oficial de NiFi 2.12.0 acepta multipart con `groupName`, posición,
`clientId`, `disconnectedNodeAcknowledged` y archivo de definición. El ejemplo
de integración debe usar una sesión autenticada ya autorizada y leer el token
en memoria; no poner tokens en la línea de comandos, archivos versionados o
salida. Nombre recomendado único:
`CG14-RESTORE-TEST-20261020-<run-id>`.

## Validación post-importación

Sin iniciar processors todavía:

1. Consultar el nuevo Process Group y comprobar 23 processors, 27 conexiones,
   un Controller Service y cero referencias externas.
2. Comprobar que los endpoints de las 27 conexiones, sus relaciones seleccionadas
   y las referencias de Controller Service resuelven dentro del grupo.
3. Comprobar que todos los bundles requeridos son `2.12.0` y están disponibles;
   registrar `validationErrors` por nombre, sin exportar propiedades sensibles.
4. Confirmar que `ConsumeKafka — CG14 synthetic E2E` está detenido o deshabilitado.
   Debe permanecer así durante toda la prueba de fixture. Confirmar que ningún
   processor está `RUNNING` antes de continuar.
5. Leer el Controller Service importado por API: registrar `state`, número de
   errores y propiedades no sensibles filtradas. El resultado esperado de esta
   copia segura es `DISABLED`; no se considera superado hasta observarlo.
6. Para probar que el servicio se puede habilitar, confirmar en API que el
   bootstrap resuelve exclusivamente al broker de laboratorio aislado
   `cg14-kafka-test:9092`, no a una dirección/alias real. Habilitar sólo el
   Controller Service de la copia, manteniendo ConsumeKafka deshabilitado;
   registrar transición/validación y volver a deshabilitarlo. Si el broker no se
   puede verificar como laboratorio, omitir esta acción y marcarla BLOCKED.
7. Para procesamiento sintético, arrancar explícitamente el mock local y sólo
   la cadena necesaria desde un generador `Fixture — valid_event` en la copia.
   Primero validar el destino `mock-predict` y que no hay salida a servicios
   externos. Verificar ruta accepted, provenance y cola vacía. No activar las
   fixtures de timeout/5xx salvo que se ejecuten como caso separado acotado.
8. Dejar todos los componentes de la copia detenidos/deshabilitados al terminar.
   No tocar estados del Process Group original.

## Resultado de la iteración 7 (histórico; actualizado abajo)

La restauración se **bloqueó antes de enviar el upload**. El sandbox denegó
acceso a `docker.sock`. Más tarde falló la autenticación REST local: el archivo
ignorado `deploy/cg14/.env` ya no presenta el nombre esperado para el usuario y
la clave del password aparece con nombre malformado. No se imprimieron valores,
no se editó el archivo y no se reinició NiFi. Sin Docker ni credenciales válidas
no es posible crear con seguridad el grupo aislado ni ejecutar fixtures. No se
recibió respuesta de importación, por lo que no hay error de importación que
atribuir a NiFi.

Antes de reintentar, el propietario debe restaurar el `.env` válido desde su
fuente local segura o autorizar al administrador del host. No regenerar la clave
`NIFI_SENSITIVE_PROPS_KEY` contra los volúmenes existentes. Luego reanudar el
preflight anterior y guardar el resultado de importación bajo un nombre de
evidencia nuevo.

## Actualización — iteración 8 (2026-10-20)

La comprobación de GOAL 35 corrigió el diagnóstico operativo: las claves que
actualmente aparecen en `deploy/cg14/.env` coinciden exactamente con las que
`init-secrets.sh`, Compose y `run-kafka-lab-e2e.py` esperan. El modo observado
del archivo es `0600`. Se inspeccionaron sólo nombres de claves y metadatos; no
se leyeron ni imprimieron valores, y no se modificó ni regeneró ningún secreto.
Por ello no había discrepancia de nombres que corregir en el cliente.

Se intentó una consulta autenticada mediante el helper existente, que valida
TLS con `deploy/cg14/secrets/nifi-local.crt`; el resultado fue `URLError` antes
de obtener token, porque no hay servicio escuchando en `localhost:18443`.
`curl` con el certificado local validado también devolvió HTTP `000` por
conexión rechazada. No es evidencia de credenciales inválidas. Docker usa el
contexto `default`, pero la API en `/var/run/docker.sock` devolvió
`permission denied`; no se usó sudo ni se cambió el socket o sus grupos. No hay acceso
alternativo a NiFi para crear un Process Group aislado.

Estado actual de GOAL 35–38: NiFi **VERIFIED activo desde el Chrome del host**;
acceso del shell del agente a loopback y Docker **BLOCKED por aislamiento de la
sesión**; importación **no intentada**. La pestaña autenticada mostraba el grupo
original con 0 componentes ejecutándose, 22 detenidos, 1 deshabilitado y 0
inválidos. No se reinició el contenedor ni se cambió el grupo.

El proceso del agente pertenece al cgroup `app-t3code-agents`; `docker context`
es `default`, pero Docker CLI devuelve `permission denied` para
`/var/run/docker.sock`. `ss` no puede abrir netlink y las conexiones desde el
shell a `127.0.0.1:18443` y `localhost:18443` fallan. El namespace de red del
agente coincide con su PID 1, pero no se obtuvo el inode del namespace del host;
por eso no se afirma una diferencia concreta de namespace frente al host. La
pestaña Chrome ya autenticada sí llega a NiFi, lo que distingue este fallo de un
NiFi caído en el host.

El shell no tiene un canal autorizado para el POST autenticado. La UI observada
no ofrece una carga directa de este archivo JSON; la carga de definición se
documenta mediante REST. Para reanudar sin eludir el sandbox, un administrador
debe ejecutar el cliente de restauración desde una terminal del host con acceso
HTTPS y credenciales ya disponibles, o entregar una instancia NiFi 2.12.0
aislada accesible por API. El destino debe ser una instancia separada o un
Process Group nuevo con todos los componentes deshabilitados; nunca el grupo
original. No hay que iniciar ni reiniciar el NiFi que ya está funcionando.

## Cliente ejecutable desde el host — 2026-10-21

La función del canvas observada requiere un Registry Client. Ese mensaje no
valida ni invalida el archivo JSON. La carga local utiliza el endpoint REST
independiente indicado arriba.

El cliente [`cg14_restore_upload.py`](../cg14_restore_upload.py) ya existe en
el checkout. Usa sólo Python estándar y valida TLS con el certificado público
existente. Lee `SINGLE_USER_CREDENTIALS_USERNAME` y
`SINGLE_USER_CREDENTIALS_PASSWORD` primero del entorno y después de
`deploy/cg14/.env` (ruta relativa al script, independiente del directorio actual).
Sólo solicita manualmente los valores ausentes o vacíos. El archivo admite
`CLAVE=valor`, comillas exteriores y prefijo `export `; los valores son literales,
sin expansión de variables ni ejecución de shell. No imprime credenciales ni las
lee durante el preflight. No usa Docker, no habilita servicios ni arranca processors. Acepta únicamente
la copia con SHA256
`98bcdaa8e64d197644b2e7a1c409394f50b4c8df2946780d442c109d2658839b`.

Desde una terminal real de Omarchy, en la raíz del repositorio:

```bash
python3 cg14_restore_upload.py \
  --flow nifi-flows/cg14_validation_flow_nifi_2.12.0_restore_safe_20261020.json \
  --cert deploy/cg14/secrets/nifi-local.crt
```

Este preflight es completamente local. Para la operación real, ejecutar el
mismo comando con `--execute`. No ejecutar varios clientes simultáneamente.
Después de autenticar, el cliente comprueba que el nombre
`CNC-GUARD-CG14-RESTORE-TEST` no existe como hijo del grupo raíz y solicita
escribir `IMPORTAR`. Envía un único upload; no reintenta el POST ni borra un
grupo parcialmente creado. Mantiene una huella de configuración y estados del
grupo original antes y después. Los hashes no acreditan el estado de todos los
repositorios o volúmenes de NiFi.

Las evidencias se guardan en un directorio nuevo e ignorado por Git:
`deploy/cg14/data/evidence/restore-upload-<UTC>-<run-id>/result.json`.
Incluyen ID, código HTTP cuando se obtiene, conteos, tipos, bundles, referencias,
relaciones, estados y número de errores de validación. No incluyen propiedades,
credenciales, tokens ni cuerpos de error del servidor. No confundir cero
errores publicados para un componente deshabilitado con su validación funcional.

Si se pierde la respuesta, el resultado puede ser incierto: inspeccionar el
destino antes de cualquier nuevo intento. Conservar el grupo creado con sus
componentes deshabilitados; no borrarlo para repetir el ensayo.

Verificación local realizada: preflight válido con el certificado existente;
99 tests Python superados (93 anteriores y 6 pruebas aisladas del cliente);
`git diff --check` sin errores. Las pruebas nuevas usan dobles de la API, sin
contactar NiFi. **Upload real NOT_TESTED**: este cliente todavía debe ejecutarse
desde el host autorizado. La habilitación del servicio, los fixtures y la
recuperación ante desastre siguen NOT_TESTED en la copia importada.

### Comprobación y corrección del cliente — 2026-10-21

El preflight volvió a pasar sin red. Una consulta HTTPS local de sólo lectura,
con el certificado existente y sin proxy, fue bloqueada por `PermissionError`
(errno 1). No hay un canal de terminal del host disponible para esta sesión;
no se ejecutó `--execute`. No se encontraron archivos `restore-upload-*/result.json`
en el directorio de evidencias. Esto no demuestra que NiFi esté detenido.

Se reprodujo un defecto en el manejo de errores del cliente: después de un
upload simulado HTTP 200, un GET post-import simulado HTTP 503 sobrescribía
`http_status` y `upload` de la operación ya respondida. La corrección conserva
HTTP 200 y el ID creado, y registra el fallo posterior en
`post_import_http_error`, sin repetir el POST. La nueva prueba falló antes de
la corrección y pasó después. La suite completa pasó con **100 tests**;
Compose `config --quiet` devolvió código 0. Estos casos simulados no son
evidencia de importación real: **RESTORE NOT_TESTED**, ejecución desde esta
sesión **BLOCKED**. El comando de ejecución manual anterior sigue vigente.

### Hotfix de negociación HTTP 406

`Api.request` enviaba `Accept: application/json` también en el login. El
contrato oficial NiFi 2.12.0 de `POST /access/token` consume formulario URL
encoded y produce `text/plain`, con respuesta 201. El cliente ahora admite
`accept` por operación: login usa `text/plain`; GET y upload conservan JSON.
No se modifica el multipart ni su boundary. [Contrato REST oficial](https://nifi.apache.org/nifi-docs/rest-api.html)

El diagnóstico HTTP permite identificar método, path, código, Accept y
Content-Type usando sólo metadatos de la petición; omite Authorization,
formularios, cookies, cuerpos y mensajes del servidor. El 406 histórico del
host no incluía el endpoint: la cabecera incorrecta está confirmada mediante
código, contrato y tests, pero su atribución al 406 real requiere la nueva
traza desde el host. No se realizó autenticación real ni upload en el hotfix.

Verificación: 107 tests superados (100 anteriores y 7 casos nuevos),
`python3 -m py_compile cg14_restore_upload.py`, `git diff --check` y preflight
local correctos. Los tests usan respuestas sintéticas, nunca el broker o NiFi.
Para comprobar sólo autenticación/GET desde el host, ejecutar el comando
`--execute` anterior y cancelar con Ctrl+C cuando solicite `IMPORTAR`, sin
introducir esa confirmación. El upload sigue NOT_TESTED hasta una operación
real autorizada posterior.

### Importación real confirmada — 2026-10-21

El responsable ejecutó el cliente desde Omarchy. Autenticación: HTTP 201;
upload: **HTTP 201 Created**, grupo `CNC-GUARD-CG14-RESTORE-TEST`, ID
`5d4f0539-01a1-1000-4a08-0a3f4c8946d8`. La evidencia original se preserva en
`deploy/cg14/data/evidence/restore-upload-20261021T071342Z-ca97a554/result.json`:
`upload=RESPONDED`, `http_status=201`, `original_unchanged=true`.

La parada posterior era un defecto del cliente: aceptaba sólo HTTP 200 para
el upload. Ahora acepta 200 o 201. Una regresión con 201 falló antes del cambio
y pasó después; suite completa: **108 passed**, compilación y diff-check correctos.
**No repetir la importación**: el grupo ya está creado.

La inspección autenticada de Chrome confirmó 23 processors deshabilitados,
27 conexiones y un `CG14 lab Kafka3 connection`, tipo Kafka3ConnectionService,
bundle `org.apache.nifi:nifi-kafka-3-service-nar:2.12.0`, con estado operativo
**Disabled** y scope del grupo restaurado. Los tipos de processors mostrados
son 2.12.0. Observación adicional guardada, sin sobrescribir `result.json`, en
`ui-validation-20261021T0715.json` dentro del mismo directorio ignorado.

La copia segura con `scheduledState: DISABLED` se ha importado y su servicio
está realmente DISABLED. Esto confirma el comportamiento de esta copia; no
demuestra que el campo serializado equivalga al estado operativo del original,
ni que un importador deba habilitar automáticamente servicios. El original
tenía ENABLED según la evidencia previa y su huella no cambió durante el upload.

No se habilitaron servicios ni processors. La validación detallada de referencias,
errores latentes de componentes deshabilitados, habilitación controlada y fixtures
de la copia siguen NOT_TESTED. Importación observada no equivale a recuperación
ante desastre o restauración funcional completa.


## Iteración 12 — validación real de la copia existente (2026-10-21)

**RESTORE_IMPORT_VERIFIED / RESTORE_STRUCTURE_VERIFIED**.
Se inspeccionó el grupo existente `5d4f0539-01a1-1000-4a08-0a3f4c8946d8`
mediante Chrome autenticado. No se repitió el upload ni se ejecutó `--execute`.
El padre es `58225f2d-01a1-1000-3ae3-f4e0bdbcef29`; hay una única copia
`CNC-GUARD-CG14-RESTORE-TEST`.

Se descargó su definición viva desde **Download Flow Definition → Without
External Services**. La comparación con la copia segura confirma 23 processors,
27 conexiones y un Controller Service, bundles 2.12.0, propiedades y relaciones
iguales. Las 54 referencias de origen/destino resuelven dentro del grupo, con
los nuevos instanceIdentifier; ConsumeKafka referencia el servicio interno.
No hay Parameter Contexts, servicios externos, grupos remotos ni puertos de
entrada/salida. Se normalizaron sólo identificadores de instancia/grupo y
geometría/estilo para comparar; no se alteraron los JSON originales.

Servicio observado en UI:

- ID runtime: `ce5c27e6-986a-3047-bead-420bdcc8ef65`.
- Tipo: `org.apache.nifi.kafka.service.Kafka3ConnectionService`.
- Bundle: `org.apache.nifi:nifi-kafka-3-service-nar:2.12.0`.
- Estado runtime: **DISABLED**, confirmado en la tabla de servicios.
- Referencia: un processor, `ConsumeKafka — CG14 synthetic E2E`.
- Bootstrap: `cg14-kafka-test:9092`; protocolo PLAINTEXT del laboratorio.
- Read Committed, Max Poll Records 10000, Client Timeout 60 sec,
  Max Metadata Wait Time 5 sec, Acknowledgment Wait Time 5 sec.
- Validación/habilitación del servicio: **NOT_TESTED**; no se pulsó Verify ni
  Enable. Disabled no demuestra VALID ni ausencia de errores latentes.

El original tenía runtime ENABLED en la evidencia previa; la definición segura
contiene scheduledState DISABLED y la copia importada está realmente DISABLED.
Esto confirma el resultado seguro de esta importación y no un fallo de bundles.
No prueba que todos los exports de NiFi preserven o cambien el runtime del mismo
modo. Estado serializado, estado operativo y validación son comprobaciones
separadas; habilitar la copia exige una acción posterior explícita.

### Aislamiento: FUNCTIONAL_RESTORE_BLOCKED

La definición viva mantiene el mismo topic
`cg14-outage-20261020102945z35bf08e`, consumer group
`cg14-outage-group-20261020102945z35bf08e`, endpoint
`http://mock-predict:8080/predict/${cg14.mock.scenario}` y directorio
`/opt/nifi/cg14-dlq` que el original. Compose monta este último desde
`deploy/cg14/data/dlq`. Es un grupo independiente en el mismo servidor, no un
entorno de efectos independiente. Ningún processor/servicio fue habilitado.

Para desbloquear: verificar administrativamente el runtime de laboratorio y
provisionar topic/group exclusivos, un mock aislado o correlación independiente
verificada, y salida/DLQ exclusivos con permisos comprobados. Aplicar esos
cambios sólo a la copia, guardar snapshot previo, ejecutar fixtures acotadas y
volver a deshabilitar. El shell actual no dispone de acceso autorizado al
runtime Docker; no se intentó eludir esta restricción. No hay fixture nueva,
commit de offsets, DLQ nueva ni provenance nuevo: CSV válido/inválido,
2xx/422/5xx/timeout/retry exhausted quedan **NOT_TESTED en la copia**.

### Evidencia y regresión

Directorio local ignorado:
`deploy/cg14/data/evidence/restore-validation-20261021-iteration12/`:
`restored-live.json`, `original-live.json`, `validation.json`.
El result.json de HTTP 201 anterior se conserva íntegro.
La comparación de las definiciones ejecutables del original y de la copia
coincide (exceptuando estados/identificadores y presentación). Todas las
acciones sobre NiFi en esta iteración fueron de lectura. En UI: original
0 running, 22 stopped, 1 disabled, 0 invalid mostrados, colas 0; restaurado
0 running, 23 disabled, 0 invalid mostrados, colas 0. El contador de inválidos
no valida componentes deshabilitados.

- `PYTHONPATH=. ./.venv/bin/pytest -q`: **113 passed in 0.14s**.
- `docker compose -f deploy/cg14/compose.yaml config --quiet`: exit 0
  (validación de configuración, no prueba del daemon).
- `git diff --check`: exit 0.
- Sin propiedades sensibles pobladas en el export restaurado; sin credenciales
  ni JWT añadidos a evidencias. Revisión limitada a artefactos de esta iteración.
- Hashes del export seguro, cliente y result.json original conservados.

La restauración funcional y recuperación ante desastre siguen pendientes.
La evidencia histórica E2E, recovery 3/3, DLQ y provenance no se degrada por no
repetirse aquí, pero tampoco prueba ejecución funcional de esta copia.


## Iteración 13 — ejecución detenida antes de mutar (2026-10-21)

**STRUCTURE_VERIFIED** conserva la evidencia de iteración 12.
**FUNCTIONAL_BLOCKED**: una consulta Docker de sólo lectura volvió a obtener
`permission denied ... unix:///var/run/docker.sock` (exit 1). Se detuvo la fase
2; no hubo acceso alternativo al host, creación de recursos ni mutaciones NiFi.
No se intentó eludir el sandbox. El estado vivo no se volvió a verificar.

Inventario basado en la definición viva descargada en iteración 12, no en una
consulta nueva. Nombres de prueba siguientes son propuestas, NO recursos creados:

| Componente | Recurso original/compartido | Recurso de prueba propuesto | Aislamiento confirmado |
|---|---|---|---|
| ConsumeKafka — CG14 synthetic E2E | Topic cg14-outage-20261020102945z35bf08e | cg14-restore-<run_id> | No |
| ConsumeKafka, Group ID | cg14-outage-group-20261020102945z35bf08e | cg14-restore-group-<run_id> | No |
| Kafka3ConnectionService | cg14-kafka-test:9092, PLAINTEXT de lab | Mismo broker lab autorizado; topic/group exclusivos | Runtime no accesible |
| InvokeHTTP | http://mock-predict:8080/predict/${cg14.mock.scenario} | Mock independiente sin puertos host | No |
| PutFile DLQ | /opt/nifi/cg14-dlq | /opt/nifi/cg14-restore-test/<run_id>/dlq | No: verificar montaje/permisos antes de usar |
| Fixtures y atributos | cg14.source.uri, record.ref, schema.version, mock.scenario | run_id y event_id sintéticos únicos | No ejecutado |
| UpdateAttribute/RouteOnAttribute | contador cg14.http.attempt; retry/exhausted; filename | Conservar semántica, correlacionar run_id | Sin cambios |
| LogAttribute y provenance | Logs/repositorios de la misma instancia | Correlación por PG/run_id; mismos repositorios | No es aislamiento de servidor |
| Contextos/referencias | Sin Parameter Contexts ni servicios externos; referencia interna al CS | Mantener referencia interna | Verificado sólo en snapshot previo |

Las propiedades de topic/group pertenecen a ConsumeKafka, no al servicio.
Bootstrap pertenece a Kafka3ConnectionService. No se editaron propiedades ni
se consultó documentación para aplicar cambios, porque la ejecución se detuvo
antes de configurar.

**No ejecutar el runner E2E actual para esta copia:**
`deploy/cg14/scripts/run-kafka-lab-e2e.py` fija GROUP_ID al grupo original
`583bcfb5-01a1-1000-de1a-41cdf8ea78fe`, no acepta un destino alternativo y usa
`data/dlq`. Aunque crea topic/group nuevos, no satisface el aislamiento pedido.
No se modificó ni ejecutó el runner.

Única operación manual de desbloqueo, desde la terminal real de Omarchy
(sólo lectura, sin secretos; no ejecutar el runner ni el upload):

```bash
docker inspect --format '{{.Name}} state={{.State.Status}} networks={{json .NetworkSettings.Networks}} mounts={{json .Mounts}} ports={{json .NetworkSettings.Ports}}' cnc-cg14-nifi cnc-cg14-kafka-test cnc-cg14-mock-predict
```

Conservar esa salida localmente. Permite comprobar redes, montajes y destinos
antes de preparar un mock/DLQ exclusivos; NO ejecuta fixtures ni resuelve por
sí sola la restauración funcional.

Regresión nueva: 113 passed in 0.14s; py_compile del cliente y git diff --check
exit 0. Evidencia ignorada: `restore-validation-20261021-iteration13/validation.json`.
Tests A/B/C/D/E NOT_TESTED en la copia; offsets, intentos HTTP, provenance,
DLQ y colas finales no medidos en esta iteración. No hubo activación que
requiriese limpieza. No se afirma ausencia medida de commits/escrituras del
original: no hay acceso al runtime. Estado seguro último observado: copia
DISABLED; original 0 running. Recuperación completa de servidor no demostrada.

## Iteración 14 — runner host preparado (2026-10-21)

Estado actualizado: **HOST_RUNNER_PREPARED / FUNCTIONAL_NOT_TESTED**.
La evidencia Docker suministrada por el propietario confirma los tres contenedores
running, red `cg14-nifi`, HTTPS sólo en `127.0.0.1:18443` y binds de DLQ/Kafka.
No se volvió a consultar Docker/NiFi desde el shell del agente. No hubo upload,
activación, modificación del original, reinicio, eliminación, commit, push ni PR.

Se preparó un runner separado, `deploy/cg14/scripts/run-restore-e2e.py`, y un
inventario fijado de los 51 IDs runtime restaurados. Incluye plan offline,
preparación exclusiva, verificación, test acotado, parada y rollback limitado al
destino, manifiesto durable sin secretos, autenticación interactiva en memoria,
CA local, lock por destino y protección contra repetición de envíos inciertos.

El procedimiento vigente para esta iteración está en
[CG14_RESTORE_E2E.md](CG14_RESTORE_E2E.md), con inventario real, patches exactos,
comandos host, recuperación y riesgos. Sustituye las propuestas de ejecución de
las iteraciones anteriores; **no ejecutar de nuevo el cliente de upload ni los
runners E2E/outage que fijan el grupo original**.

Validación local: `--plan --run-id cg14it14a001` exit 0, sin conexiones ni
mutaciones; `PYTHONPATH=. ./.venv/bin/pytest -q`: **164 passed** (113 anteriores
conservados); `git diff --check`: exit 0. El éxito funcional sólo puede declararse
tras revisar el manifiesto generado por la ejecución real en el host.

### Hotfix de autenticación del runner — 2026-10-21

Inspección local: `run-restore-e2e.Api` hereda `login`, `request` y el cliente
TLS de `cg14_restore_upload.Api`. La lectura de username **ya aplicaba
`strip()`**; la contraseña de `getpass` no se normaliza. Tanto apply como verify
usan el mismo POST `/access/token`, `Accept: text/plain`, formulario producido
por `urllib.parse.urlencode(...).encode()` y
`Content-Type: application/x-www-form-urlencoded`. El método JSON `call` del
runner no interviene en la autenticación.

Por ello no se ha demostrado que espacios periféricos en username expliquen
el HTTP 400 reportado: el código existente ya los eliminaba. Un 201 previo y
un 400 posterior no permiten determinar la causa concreta del rechazo del
servidor. No se reprodujo contra NiFi ni se inspeccionaron credenciales o cuerpos.

Corrección mínima: rechazar localmente username vacío después de `strip()`,
antes de pedir contraseña o enviar el POST. Se conserva la implementación
compartida para evitar divergencias. Tests sobre la clase real del runner
comprueban username con espacios/tabulaciones, contraseña con espacios,
Unicode y caracteres reservados intactos, contrato de formulario, respuesta
201 y HTTP 400 sin token ni reintento ni exposición de secretos/cuerpos.

`PYTHONPATH=. ./.venv/bin/pytest -q`: **167 passed**.
`git diff --check`: exit 0. Sin acceso al runtime, apply, test, import,
reinicios ni cambios al grupo original. Funcionalidad restaurada sigue pendiente
de evidencia host; se puede reintentar sólo verify con el mismo run ID aplicado.
