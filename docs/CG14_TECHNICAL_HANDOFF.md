# CG14 — technical handoff

Corte de publicación: 2026-10-21. Rama `feat/14-nifi-validation`; revisión en
Draft contra `main`. **Estado global PARTIAL; issue #14 debe seguir abierta.**

## Estado vigente para el revisor

La composición PR65 incorpora PR42 `53f342d` (PR62 y PR64). El
[worker durable opt-in](CG14_DURABLE_PIPELINE.md) y su
[corrección de recibos/JSON profundo](evidence/DURABLE_PIPELINE_FIX_R2_20261021.md)
tienen evidencia HTTP/disco y ES aislado separada del runtime histórico de
este handoff. Un recibo CG15 rechazado bloquea todos los replays, sin ACK.
Esto no habilita NiFi del host, no acredita RESTORE E2E y no cierra la issue.
El siguiente gate de PR65 es revisión padre del SHA publicado.

- VERIFIED histórico de laboratorio: pipeline de validación/rechazo, Kafka E2E,
  recuperación Kafka 3/3, provenance, DLQ y export de NiFi 2.12.0.
- RESTORE estructural VERIFIED: grupo existente
  `5d4f0539-01a1-1000-4a08-0a3f4c8946d8`, 23 processors, 27 conexiones y servicio
  `ce5c27e6-986a-3047-bead-420bdcc8ef65` importado DISABLED. No repetir upload.
- RESTORE funcional NOT_TESTED: no existe ejecución completa acreditada de
  fixtures en la copia ni habilitación ENABLED/VALID del servicio restaurado.
- Bloqueo comunicado por el operador: el mock independiente no estaba disponible
  durante el intento de test. El runner incluye `--resume`, pero eso no acredita
  que el bloqueo esté resuelto ni que el E2E haya pasado.
- Regresión de esta publicación: **209 passed** con
  `PYTHONPATH=. ./.venv/bin/pytest -q`; Compose config, sintaxis Python/shell,
  JSON y `git diff --check` correctos. Sin ejecutar E2E ni tocar Docker/NiFi.
- CG03/CG13/CG28 reales, idempotencia durable, SSH remoto y revisión de otro
  integrante siguen PARTIAL/NOT_TESTED o bloqueados por sus dependencias.

Procedimiento vigente para la copia existente:
[CG14_RESTORE_E2E.md](CG14_RESTORE_E2E.md).
[CG14_RESTORE_VALIDATION.md](CG14_RESTORE_VALIDATION.md) conserva la cronología;
no reutilizar los comandos históricos de importación o los runners del grupo
original para recuperar RESTORE-TEST.

Los JSON bajo `deploy/cg14/data/evidence/` son evidencias locales ignoradas y no
se publican en este PR. Las cifras siguientes proceden del historial documentado,
no de una nueva ejecución en esta publicación; el revisor debe contrastar esos
artefactos sanitizados con el operador si necesita comprobar el runtime.

## Historial técnico de laboratorio e iteraciones previas

## A. CG14 funcional en laboratorio

La instancia local usa Apache NiFi `2.12.0` en el Compose aislado
`deploy/cg14/compose.yaml`. `CNC-GUARD-CG14-DEV` tiene 23 processors, 27
conexiones y un `Kafka3ConnectionService` local. La lectura autenticada de la API
en esta consolidación encontró cero processors inválidos; 22 están detenidos y
uno deshabilitado. No se ejecuta el consumidor de laboratorio ni se activa una
lectura productiva.

El flow definition descargado de NiFi está en
[`cg14_validation_flow_nifi_2.12.0_live_20261020.json`](../nifi-flows/cg14_validation_flow_nifi_2.12.0_live_20261020.json).
Su SHA-256 es `c166f844066b0dc37e5fc25117a8b0added769287775e8ea82267c9496e62c4f`.
La comparación contra la API del grupo confirmó nombres, tipo/bundle de
processors y endpoints/relationships de las 27 conexiones. El
`Kafka3ConnectionService` coincide en tipo, bundle y propiedades no sensibles.
El JSON de flow definition lleva `scheduledState: DISABLED` para ese servicio;
la API viva informó `state: ENABLED`. El primero pertenece a la definición
versionada y el segundo al estado operativo actual. Interpretar el primero como
el estado solicitado por el importador es una inferencia todavía sin comprobar
en una restauración aislada. La
copia segura solicita que todos los componentes queden deshabilitados, pero
todavía no se había importado en esa consolidación histórica (véase resultado
actual arriba). No hay Controller Services externos referenciados ni
valores sensibles no vacíos en el snapshot. La explicación y el procedimiento
reproducible están en [`CG14_RESTORE_VALIDATION.md`](CG14_RESTORE_VALIDATION.md).
La evidencia acotada está en
`../deploy/cg14/data/evidence/2026-10-20/live-flow-export-audit.json` (evidencia local no publicada)
y el registro de esta consolidación en
`../deploy/cg14/data/evidence/2026-10-20/iteration6-handoff.json` (evidencia local no publicada).

Los exports previos se preservan: el base tiene 19/21/0 processors/conexiones/
services; el export con DLQ tiene 21/25/0. Ambos están obsoletos respecto al
grupo vivo: el último no incluye los dos processors de E2E Kafka ni el
Controller Service. No importar esos exports como si fueran el estado actual.
El nuevo snapshot incluye parámetros propios del broker de laboratorio y no es
un export de producción.

La ruta de laboratorio valida CSV con el Groovy versionado, enruta válidos y
rechazados, llama a un mock HTTP explícitamente local, limita retries y conserva
rechazos en la DLQ local persistente. La recuperación tras outage del broker de
laboratorio quedó demostrada en tres ensayos separados; los detalles y offsets
están en `deploy/cg14/data/evidence/2026-10-20/iteration5-summary.json` y los
JSON de cada run. El script delega en `deploy/cg14/scripts/run-kafka-outage-recovery.py`.
Es evidencia de laboratorio sintético, no del broker CG13.

### Arranque y validación no destructiva

Con `.env` local ya inicializado (no copiarlo a Git):

```bash
cd deploy/cg14
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f compose.yaml up -d nifi
docker compose --env-file .env -f compose.yaml ps
```

URL local: <https://localhost:18443/nifi>. El puerto del host está publicado
solo en loopback. Para revisar el estado, usa `docker compose ... ps`, la URL y
el certificado local configurado en `deploy/cg14/secrets/`; no imprimas `.env`,
`docker inspect Config.Env` ni credenciales. El test completo Python puede
repetirse con `PYTHONPATH=. ./.venv/bin/pytest -q`. Para parar sin borrar datos:

```bash
docker compose --env-file .env -f compose.yaml stop nifi
```

Para reanudar: sustituye `stop` por `start`. No uses `down -v`; conserva
volúmenes y DLQ. El broker de laboratorio sólo se inicia con el perfil opcional
`kafka-test`; la prueba E2E crea topics/grupos sintéticos retenidos, por lo que
no debe repetirse de forma rutinaria ni contra topics reales.

## B. Integración real CNC Guard

**Bloqueada** por contratos y servicios externos aún no confirmados:

- CG03: existe una propuesta local `docs/CG14_VALIDATION_CONTRACT.md`, no una
  versión aprobada. En particular, `event_id` actual se deriva del esquema,
  tipo de fuente y bytes raw; no diferencia dos ocurrencias legítimas idénticas.
- CG13: no hay broker, listener seguro, topic RAW, formato/framing, group,
  retención o política de offsets confirmados para CG14. El consumidor está
  detenido y no usa datos reales.
- CG28: `scoring/score_api.py` sigue con marcadores de implementación; no hay un
  predictor productivo `/predict` ejercitado por este grupo. El `mock-predict`
  es sólo fixture de integración.
- Idempotencia durable: no está implementada en un destino persistente real.
  El E2E anterior demostró que dos solicitudes con el mismo `event_id` pueden
  llegar dos veces al mock.

Las decisiones y preguntas contractuales están separadas en
[`CG14_CONTRACT_DEPENDENCIES.md`](CG14_CONTRACT_DEPENDENCIES.md). No anunciar
exactly-once, eliminación de duplicados ni entrega a alertas productivas.

## C. Acceso administrativo SSH/LAN

NiFi CG14 continúa limitado a loopback. SSH remoto y prueba desde un segundo
equipo no son prerrequisito para validar el pipeline local, pero sí bloquean el
handoff remoto solicitado. El servicio SSH quedó inactivo al último estado
registrado y habilitarlo requiere administración aprobada, claves host válidas,
cuentas/claves individuales, restricción de forwarding y ACL de LAN. Seguir
`deploy/cg14/ssh/README.md`; no activar consumo de los datos reales por resolver
SSH.

## Seguridad y riesgo externo

Se detectó una credencial antigua en claro en el `README.md` público de la rama
default remota. El valor se omite deliberadamente. Rotar cualquier instancia
que pudiera seguir activa y coordinar retirada del archivo/historial con quien
administra esa rama; esta iteración no modifica el remoto ni el historial.
Los archivos locales actuales se revisan por separado. No se realizó commit,
push, merge o PR.

## Estado y revisión

Consultar [`CG14_ACCEPTANCE_MATRIX.md`](CG14_ACCEPTANCE_MATRIX.md) para criterio,
evidencia y bloqueos. Otro integrante ya puede revisar el validador, el flujo
local 2.12.0, la evidencia sintética y este handoff. No debe aprobarse como
integración real hasta que CG03, CG13 y CG28 confirmen contratos y se pruebe el
destino productivo con identidad/idempotencia acordadas.


## Actualización de restauración — iteración 12 (2026-10-21)

La copia existente `5d4f0539-01a1-1000-4a08-0a3f4c8946d8` tiene importación y
estructura verificadas: 23 processors deshabilitados, 27 conexiones, un
Kafka3ConnectionService DISABLED, bundles 2.12.0 y referencias resueltas. Se
comparó el export vivo descargado con la copia segura; no se repitió upload.
El original fue consultado sin mutaciones y conserva 0 running/colas vacías.

La prueba funcional queda **FUNCTIONAL_RESTORE_BLOCKED**: topic/group Kafka,
mock HTTP y DLQ son compartidos con el original. No se habilitó ningún servicio
ni processor. Servicio DISABLED no equivale a VALID: habilitación/validación y
fixtures de esta copia son NOT_TESTED. No es recuperación ante desastre.

Regresión nueva: **113 passed**; Compose config y git diff --check: exit 0.
Cliente, export seguro y result.json HTTP 201 sin cambios. Evidencia ignorada:
`deploy/cg14/data/evidence/restore-validation-20261021-iteration12/`.
Detalles y bloqueo reproducible en `CG14_RESTORE_VALIDATION.md`.

Revisión por otro integrante: comprobar hashes y comparativa de definiciones,
referencias internas/servicio DISABLED, límites del laboratorio, los seis
criterios de la matriz y evidencias históricas E2E/recovery/provenance. No
volver a ejecutar --execute. Registrar nombre, fecha y conclusión reales;
para cerrar los criterios HTTP, aislar la copia y acreditar 422/5xx/timeout,
retries y DLQ. CG03/CG13/CG28, SSH remoto e idempotencia durable siguen pendientes.


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
