# CG14 — matriz de aceptación y evidencia

Fecha de corte: 2026-10-21. Issue oficial: [#14](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/14). Los seis criterios oficiales exactos fueron recibidos del responsable; la matriz siguiente los transcribe y los vincula a evidencia existente. No se volvió a consultar GitHub.

## Corte vigente de publicación — 2026-10-21

Actualización PR65 ronda 2: el [worker opt-in](CG14_DURABLE_PIPELINE.md) ya
implementa raw→API canónica→CG15→ES configurado, con recibo durable aceptado
por stream antes de completar/ACK. [La evidencia de corrección](evidence/DURABLE_PIPELINE_FIX_R2_20261021.md)
separa regresiones HTTP/disco, crashes de procesos y ES aislado de la
aceptación del grafo NiFi/Apache Kafka real. El conteo 209 y las reservas de
runtime siguientes pertenecen al corte anterior; no son el total de esta
ronda ni prueba de ausencia del worker. La revisión padre sigue pendiente.

La regresión actual es **209 tests superados**. La estructura RESTORE 23/27/1
está verificada; su servicio fue importado DISABLED. El RESTORE E2E funcional y
la habilitación del servicio restaurado siguen **NOT_TESTED**. El mock propio
no estaba disponible durante el intento comunicado; existe soporte `--resume`,
pero falta una ejecución completa acreditada. La recuperación Kafka 3/3 es
histórica y pertenece al laboratorio, no a esta copia ni a CG13 real.

La tabla inferior conserva el corte histórico y sus reservas de evidencia HTTP;
no autoriza cerrar los criterios oficiales. La revisión de otro integrante,
contratos CG03/CG13/CG28, aceptación de idempotencia en runtime y SSH remoto
siguen pendientes.
La issue #14 continúa abierta; la referencia del PR es únicamente `Refs #14`.
Evidencias de runtime ignoradas se citan como rutas locales, no como enlaces a
archivos disponibles en GitHub. Ver el estado vigente en
[CG14_TECHNICAL_HANDOFF.md](CG14_TECHNICAL_HANDOFF.md).

Estados usados:

- `VERIFIED_LAB`: evidencia ejecutada en el entorno sintético aislado.
- `VERIFIED_REAL`: evidencia ejecutada contra componentes/contratos reales aprobados del equipo.
- `PARTIAL`: parte del criterio tiene evidencia, faltan destino/contrato o límites.
- `BLOCKED`: depende de una decisión o componente externo inexistente/no aprobado.
- `NOT_TESTED`: no se ejecutó la prueba identificada.

| Criterio | Implementación | Test/evidencia | Estado | Bloqueo / siguiente paso |
|---|---|---|---|---|
| **1. Flujo JSON exportado y versiones de processors** | Export 2.12.0 del grupo vivo y copia segura de restauración | `live-flow-export-audit.json`, hash del export y validación estructural local 23/27/1; API viva comparada en `iteration6-handoff.json` | VERIFIED_LAB | Importación real confirmada el 2026-10-21; validación funcional pendiente, sin prueba de disaster recovery |
| **2. Rutas HTTP 2xx, 422, 5xx y timeout probadas** | InvokeHTTP a mock local; fixtures de respuesta 422, 5xx y timeout presentes | `kafka-e2e-20261020-121056-b65d66/e2e-summary.json` demuestra 2 HTTP 200. Evidencia previa dice que 422/503/timeout no se repitieron; las fixtures de error constan detenidas | PARTIAL | Ejecutar los tres casos de error controlados cuando el runtime esté disponible; la ruta 2xx sí está verificada |
| **3. Rechazo 422 y retry 5xx limitado** | Relaciones y contador de reintentos están en el flujo de laboratorio | El export y el E2E confirman la ruta normal y rechazo CSV, pero no prueban el comportamiento HTTP 422/5xx; fixtures manuales detenidas | PARTIAL | Ejecutar 422 y 5xx y medir el límite, exhaustion y DLQ en runtime |
| **4. Contadores y provenance sin secretos** | Conteos por registros/FlowFiles y eventos NiFi; evidencia sin contenido | E2E sintético: RECEIVE=5, CONTENT_MODIFIED=5, ROUTE=5, SEND=5, DROP=3; 5 mensajes, 5 FlowFiles, 2 aceptados, 3 rechazados. `e2e-summary.json` | VERIFIED_LAB | Evidencia limitada al broker y mock de laboratorio |
| **5. Artefactos, versiones, comandos, resultados reales y límites documentados** | Handoff, runbook, matriz y evidencias locales | `CG14_TECHNICAL_HANDOFF.md`, `CG14_RESTORE_VALIDATION.md`, esta matriz y JSON bajo `deploy/cg14/data/evidence/2026-10-20/` | PARTIAL | Importación HTTP 201 y estado DISABLED documentados en el runbook; quedan validación funcional y límites de integración |
| **6. Revisión de otro integrante con conclusión y fecha** | Revisión externa requerida por issue | No existe evidencia de revisión externa con conclusión y fecha en este checkout | NOT_TESTED | Solicitar a otro integrante revisión y registrar identidad/fecha/conclusión |
| Contrato/validador determinista y regresión | `cg14_validation`; reglas CSV/JSON y códigos de error | Suite del repo: `PYTHONPATH=. ./.venv/bin/pytest -q`: 93 passed en esta consolidación; evidencia en `deploy/cg14/data/evidence/2026-10-20/iteration6-handoff.json` | VERIFIED_LAB | Confirmar propuesta v0.1.0 con CG03 |
| Flow NiFi en versión objetivo y export revisable | Process Group `CNC-GUARD-CG14-DEV`, bundle NiFi 2.12.0 | API leída: 23 processors, 27 conexiones, 0 inválidos; nombres/tipos/bundles y cableado coinciden. El Controller Service vivo está ENABLED; el JSON solicita `scheduledState: DISABLED`; `../deploy/cg14/data/evidence/2026-10-20/live-flow-export-audit.json` (evidencia local no publicada) | PARTIAL | Estado DISABLED confirmado en la copia importada; definición y referencias verificadas en iteración 12; validación runtime de la copia pendiente |
| GOAL 30: semántica y ubicación de `scheduledState` | Está en `flowContents.controllerServices[0]` del export. El API vivo expone por separado `component.state`. Interpretar el primero como el estado solicitado al importar es una inferencia del modelo | JSON estático + API NiFi 2.12.0: servicio en vivo `ENABLED`, cero errores; export `DISABLED`; documentación REST 2.12.0 y [`CG14_RESTORE_VALIDATION.md`](CG14_RESTORE_VALIDATION.md) | VERIFIED_LAB | Copia segura importada: servicio DISABLED observado; no asumir equivalencia con el estado vivo del original |
| GOAL 31/37: restauración aislada real | Copia segura importada en `CNC-GUARD-CG14-RESTORE-TEST` desde Omarchy | HTTP 201, ID `5d4f0539-01a1-1000-4a08-0a3f4c8946d8`; `restore-upload-20261021T071342Z-ca97a554/result.json` registra original intacto; Chrome confirma 23/27/1 y Kafka3ConnectionService DISABLED; observación en `ui-validation-20261021T0715.json` | PARTIAL | Importación real y estado importado comprobados. No repetir upload. Referencias internas y bundles verificados en iteración 12; habilitación/validación runtime y fixtures pendientes; no prueba disaster recovery |
| Cliente de restauración: controles y regresión | TLS verificado, credenciales interactivas, detección de nombre existente, único POST sin reintento; conservación del resultado cuando falla un GET posterior | `PYTHONPATH=. ./.venv/bin/pytest -q`: 113 passed (regresión actual de iteración 12). `docker compose ... config --quiet`: 0. Pruebas del cliente con API simulada; detalle en el runbook | VERIFIED_LAB | Los tests del cliente son aislados; la importación real y el estado del servicio se acreditan por separado en la fila de restauración |
| CSV válido e inválido, cabecera, campos/tipos | Groovy validator dentro del grupo; fixtures sintéticos | E2E y provenance de runs del broker lab; detalle `deploy/cg14/README.md` | VERIFIED_LAB | No equivale al framing/mensajes reales CG13 |
| HTTP 2xx / 422 / 5xx / timeout | `InvokeHTTP` contra `mock-predict` opcional; retries limitados | 2xx histórico verificado; 422/5xx/timeout no acreditados aquí en runtime, véanse criterios 2 y 3 | PARTIAL | Ejecutar fixtures de error aisladas y obtener aprobación CG28 |
| Rechazo y DLQ persistente | `PutFile` a ruta local con permisos restrictivos | Persistencia/reinicio de DLQ validada en evidencia previa | VERIFIED_LAB | Definir sobre/destino compartido/retención con CG03/13 |
| Recuperación de Kafka tras caída | ConsumeKafka 2.12 lab y group/topic sintéticos aislados | Tres ensayos; cada uno 6/6 offsets, lag 0, seis RECEIVE/offsets/IDs únicos, sin nuevos DLQ; `iteration5-summary.json` | VERIFIED_LAB | CG13 real aún no confirmado; no supone exactly-once |
| Conteos y provenance | Atributos `event_id`, topic/partition/offset, FlowFile UUID y eventos NiFi | E2E lab consultó provenance; recuperación capturó RECEIVE y correlación por ID/offset | VERIFIED_LAB | No hay archivo de provenance externo/retención acordada |
| Idempotencia productiva y alertas sin duplicados | Worker opt-in con ledger API/worker/CG15 y recibos aceptados por stream; diseño en [`IDEMPOTENCY.md`](../deploy/cg14/IDEMPOTENCY.md) | Regresiones de replay/conflicto y HTTP/ES aislados; E2E previo del mock es histórico | PARTIAL | Revisión padre, Kafka/NiFi reales y destino de alertas CG28 |
| Contrato CG03 aprobado | Propuesta local `docs/CG14_VALIDATION_CONTRACT.md` | Aprobación del responsable no disponible | BLOCKED | Revisar schema, ID, unidades, timestamps, rechazo y retención |
| Kafka real CG13 y consumo autorizado | Broker de laboratorio no productivo | Sin endpoint/topic/group reales confirmados; no se consumieron datos reales | BLOCKED | Responsable CG13 confirma listeners seguros, formato, particiones, group, offsets/retención |
| API productiva CG28 | `scoring/score_api.py` contiene marcadores; mock no equivalente | Sin request/response productivos ejecutados | BLOCKED | Implementación/contrato API y destino de alertas |
| Acceso HTTPS local y autenticación | NiFi HTTPS en `127.0.0.1:18443` | Verificado previamente: HTTPS autenticado 200 y API anónima 401 | VERIFIED_LAB | Para LAN, preparar SSH con administración y validar segundo equipo |
| SSH/túnel desde compañero autorizado | Runbook y plantilla de SSH | Servicio inactivo por estado administrativo previo; no prueba desde otro host | NOT_TESTED | Requiere host keys/usuarios/ACL aprobados y cliente LAN |
| Revisión externa de issue #14 | Revisión por otro integrante con conclusión y fecha | No registrada en el repositorio | NOT_TESTED | Solicitar revisión independiente; no marcar el criterio 6 como cumplido |
| Acceso directo LAN bloqueado | Publicación de NiFi CG14 es loopback | Estado de binding registrado; no existe prueba remota nueva desde LAN | PARTIAL | Probar desde segundo equipo cuando SSH/LAN autorizado esté disponible |

## Decisión de cierre

**Cierre funcional de CG14 en laboratorio: VERIFIED_LAB** para validador,
pipeline sintético, recuperación del broker de laboratorio, provenance y DLQ,
según las evidencias citadas. No equivale a aceptación de issue #14 hasta completar
las rutas HTTP pendientes de evidencia y recibir la revisión requerida.

**Integración real CNC Guard: BLOCKED** por CG03/CG13/CG28, broker/tópicos no
confirmados para el grafo activo y falta de aceptación runtime. El checkout
incluye API canónica y worker durable opt-in; su existencia y validación local
no acreditan cableado del grafo NiFi activo ni aceptación de esos contratos.

**Acceso administrativo SSH/LAN: NOT_TESTED/BLOCKED** por intervención
administrativa y segundo equipo pendiente. Esto no invalida las pruebas
funcionales locales.

No se debe declarar CG14 globalmente DONE ni exactamente-once.


## Corte nuevo — iteración 12

- `RESTORE_IMPORT_VERIFIED`: HTTP 201 histórico preservado; sin nuevo upload.
- `RESTORE_STRUCTURE_VERIFIED`: definición viva descargada y comparada:
  23/27/1, bundles 2.12.0, propiedades/relaciones iguales y referencias internas
  resueltas. Evidencia local `restore-validation-20261021-iteration12/validation.json`.
- Servicio importado DISABLED observado; VALID/habilitación **NOT_TESTED**.
- `FUNCTIONAL_RESTORE_BLOCKED`: copia comparte topic/group, mock y DLQ con el
  original; no ejecutar hasta aislar efectos. Ninguna fixture nueva ejecutada.
- 113 tests pasan. Criterios oficiales 1 y 4 mantienen VERIFIED_LAB histórico;
  2, 3 y 5 PARTIAL; 6 NOT_TESTED. No hay aceptación productiva ni revisión externa.


### Iteración 13 — FUNCTIONAL_BLOCKED

Consulta Docker de sólo lectura: socket denegado (exit 1). Se detuvo la
preparación sin crear recursos ni modificar NiFi. Estructura VERIFIED según
iteración 12; fixtures A–E, offsets y nuevas pruebas provenance/DLQ NOT_TESTED.
El runner E2E existente apunta explícitamente al original y usa su DLQ: no
lanzarlo para RESTORE-TEST. Inventario, única operación manual de desbloqueo y
evidencia nueva en `CG14_RESTORE_VALIDATION.md` y
`deploy/cg14/data/evidence/restore-validation-20261021-iteration13/validation.json`.
Regresión ejecutada: 113 tests, py_compile y diff --check correctos.
No cambia la aceptación: criterios 2/3/5 PARTIAL y revisión externa NOT_TESTED.
Integración real REAL_INTEGRATION_PARTIAL/BLOCKED por contratos y servicios
CG03/CG13/CG28; no hay RESTORE_FUNCTIONAL_VERIFIED ni CG14 DONE.
