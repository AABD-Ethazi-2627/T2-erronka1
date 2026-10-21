# CG14: composición con PR42 y límites de integración

Esta rama complementaria parte de PR42 `9158193b32ad0ee37b1ce03967c6ece2b70392d2`
y contiene merges de PR57 `aace73cade05932e85a7a268fc1db288d4b60b4e` y PR59
`528bcadc1d845adc09475470419b8fecc2764fb6`. No modifica ni publica esas ramas.
Después se incorpora por merge PR42 `7983beef471dc2de2a9fd977f8596809dc7f665c`,
que ya incluye PR58, CG21 y la corrección de JSON recursivo. Se conservan sus
archivos sin reimplementarlos. Conserva la guía activa del README y el alcance CG14.
**No acredita CG14 DONE, RESTORE VERIFIED ni integración E2E funcional.**

## Compatibilidad implementada

`scripts/cg14_scoring_bridge.py` proyecta un evento CG14 ya normalizado al
contrato estricto `Telemetry` de `/predict`. Conserva ID, timestamp, URI y
referencia; retira `source.raw_record` de una copia y rechaza campos extra,
etiquetas, tipos inválidos, no finitos, fechas imposibles y Kelvin no positivo.
El original debe conservarse en auditoría. El puente no almacena ni envía HTTP.

El export fijado usa **`cg14-lab-kafka`**. RESTORE cambia ese kind a
**`restore-<run>`**; el alias debe coincidir exactamente, sin inferir SMB.

```bash
python -m scripts.cg14_scoring_bridge normalized-event.json \
  --expected-source-kind cg14-lab-kafka --source-kind lab_fixture \
  > scoring-request.json
```

Para RESTORE, sustituir el expected-kind por el valor exacto del manifiesto,
por ejemplo `restore-restoretest001`. Para source canónico se omiten ambos
argumentos. El CLI limita la entrada a 32768 bytes y falla sin emitir petición.
Python CG14 y la fuente Groovy ahora exigen Kelvin >0, otros sensores >=0 y
finitud; los cinco exports se regeneran desde esa fuente. Los tests ejecutan
Python y comparan los scripts incrustados; **no ejecutan Groovy en NiFi**.

## Contrato de ocurrencia, replay y entrega

Los IDs anteriores se preservan: PR42 calcula SHA256(kafka.key), con key de
Filebeat; el parser CG14 histórico calcula SHA256(versión + kind + raw).
Este último es un identificador de contenido heredado: puede colapsar dos
ocurrencias iguales y cambia con el alias de laboratorio. No permite inferir
equivalencia entre rutas. Ni el parser ni el puente cambian esos IDs existentes.

La migración explícita `scripts.cg14_occurrence.bind_occurrence()` define una
ocurrencia por **namespace estable del cluster/generación del log, topic,
partition y offset originales**. El namespace no es el alias de un run. Su
`event_id` es SHA256 de `cnc.occurrence.v1\n` más el array JSON compacto UTF-8
`[namespace,topic,partition,offset]`, en ese orden y sin escapes ASCII añadidos.
Dos filas iguales en offsets distintos son dos ocurrencias. Una repetición
de transporte conserva coordenadas originales y event_id. Una republicación
sin coordenadas originales es una nueva ocurrencia; no se deduplica por raw.

Cada publicación durable tiene un `delivery_id` asignado por su outbox/transporte;
la reentrega del mismo registro conserva ese ID, también ante un resultado
incierto. Una publicación nueva puede tener otro delivery_id conservando las
coordenadas de ocurrencia originales. PR58 fija el ID de cada registro Kafka
que consume como JSON compacto `["kafka",namespace,topic,partition,offset]`;
no se sobrescribe ni se confunde con el event_id de la ocurrencia. Al publicar
en otro topic, registrar el vínculo entre ambos IDs. Un identificador de intento,
si se necesita, es un campo de auditoría separado. La función exige el ID legacy
esperado y devuelve `telemetry` y
un sidecar `identity` que conserva legacy_event_id, legacy_source (incluido raw),
coordenadas, identity_version y delivery_id. Canonicaliza explícitamente el
source de la nueva telemetría por las coordenadas. Es una migración opt-in,
no una reinterpretación de eventos archivados. El sidecar no se envía a `/predict`.

```python
from scripts.cg14_occurrence import bind_occurrence

bound = bind_occurrence(
    original_event,
    namespace="lab-cluster-generation1",
    topic=original_topic,
    partition=original_partition,
    offset=original_offset,
    delivery_id=persisted_delivery_id,
    expected_event_id=original_event["event_id"],
    expected_source_kind="cg14-lab-kafka",
    source_kind="lab_fixture",
)
# Antes de publicar: commit durable de bytes originales + bound["identity"].
# Después: publicar únicamente bound["telemetry"] al destino contractual.
```

Los tests prueban equivalencia de ID y sobre canónico entre entradas legacy
de ambas rutas, replay y dos ocurrencias legítimas iguales. La entrada PR42
de esa prueba es sintética: no acredita ejecución de Filebeat/Groovy.
**Este binding aún no está cableado al grafo NiFi activo.**

## Gate RESTORE reparado

Antes del único envío, el runner persiste un manifiesto de cinco entregas:
2xx, 422, 5xx, timeout y CSV inválido, con escenario, coordenadas esperadas,
record_ref, source, event_id cuando existe y hashes de raw/cuerpo normalizado.
El topic exclusivo, vacío y de una partición fija offsets 0–4. Un resultado
incierto del productor sigue prohibiendo reenviar. El CSV inválido mantiene
event_id=null y se correlaciona por entrega, sin inventar un evento válido.

`functional_pass()` exige el inventario completo, servicio habilitado VALID
observado y finalmente DISABLED, processors deshabilitados, colas vacías,
offset final 5/lag0 y consulta de provenance completa. Para cada entrega
correlaciona componente, relación, escenario, ID y coordenadas. Exige 200 por
Original y DROP en su sink, 422 por No Retry, y 503/timeout con intentos HTTP
0/1/2, incrementos 1/2/3 y ruta exhausted. Las cuatro DLQ deben ser distintas,
tener SEND de PutFile, filename correlacionado y contenido/source/raw correctos.
Los rechazos HTTP contienen la telemetría normalizada; sólo el CSV inválido
exige valid=false/MALFORMED_CSV. No basta contar cuatro ficheros.

El collector lee el detalle de provenance y conserva atributos allowlist,
referencias y hashes, sin publicar raw. Evidencia histórica sin manifiesto o
provenance suficiente queda NOT_VERIFIED. Esto acredita únicamente el contrato
del laboratorio mock cuando se ejecute, nunca scoring o archivo integrados.

La fuente Groovy modificada cambia el hash del export RESTORE a
`60048fc426b25d57dd4bb6f9c8c5c99a48a80e906865d3d49a210e7659f43f52`.
Se actualiza el pin explícito del preflight sin quitar la comprobación de hash.
La copia del host anterior ya no corresponde a esta definición: requiere
revisión/migración autorizada y readback de configuración antes de ejecutarla.
No se ha importado ni modificado ninguna copia runtime en este trabajo.

## Cableado durable P57-INTEGRATION-1

La capa posterior a PR62 implementa el recorrido operable en
[`scripts.run_durable_pipeline`](../scripts/run_durable_pipeline.py): journal
raw/identidad, proyección, API canónica con precondiciones, outbox JSON y archivo
CG15, más ES opt-in. Véase [operación y recuperación](CG14_DURABLE_PIPELINE.md).
El export staged NiFi es auxiliar y no posee offsets de origen. El plan que
sigue documenta las dependencias originales; la implementación del worker
no acredita el grafo NiFi activo, Kafka real ni aceptación E2E del laboratorio.

1. Conservar captura SMB y registro Filebeat existentes de PR42. En el broker
   autorizado, retener bytes y coordenadas originales; generar y persistir
   delivery_id antes de publicar. No duplicar captura.
2. Introducir un destino durable de auditoría para bytes y sidecar de identidad,
   separado del topic contractual. El sink estricto de CG15 no admite raw ni
   sidecar como Telemetry. Definir/implementar ese destino antes de habilitar
   el productor; un LogAttribute no acredita ese commit.
3. Aplicar el binding explícito y el puente en el límite de normalización.
   Publicar telemetría sólo tras el commit durable. Conservar ID legacy,
   event_id común, delivery_id y hashes; no mezclar sobres raw y estrictos
   bajo la misma clave de archivo.
4. Cablear el adaptador existente de [PR58](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/58),
   head observado `847f77faa4062e9bed9f7bfef2d6a49f661a631d`:
   `scripts/kafka_archive.py`, CLI `scripts/archive_consumer.py`. Reutilizar
   su ack después del commit durable y namespace estable de entrega; no
   sustituirlo por el offset confirmado del ConsumeKafka CG14. El adaptador ya
   está integrado en la base actual PR42, incorporada aquí por merge; no se
   duplica ni se modifica su consumidor. Falta conectarlo al flujo CG14.
5. Conectar la proyección a `scoring-api:8000/predict` y publicar respuestas
   contractuales al destino de predicciones. El mock `/predict/<scenario>`
   no valida Telemetry ni produce Prediction. Revisar su grafo separado.
6. Incorporar el trabajo independiente de respuesta canónica antes de activar
   retries de scoring: persistir/reutilizar por clave de inferencia, sin
   rescoring silencioso ante resultado HTTP incierto. Esta rama no cambia
   score_api, scored_at ni detección de conflictos del archivo.
7. En laboratorio propio autorizado, ensayar caída antes/después de ambos
   commits, ack/commit Kafka fallido, rebalance y reinicio; comparar enviados,
   archivados, rechazados, replays y acks por delivery_id. Ejecutar NiFi real
   con 2xx/422/5xx/timeout, límites de retry y rutas terminales observadas.
   Sólo esa evidencia y revisión padre/equipo permitirán decidir aceptación.

## Prerrequisitos y comprobaciones

Usar Linux/fcntl. En la máquina de validación la distro se llama
`FedoraLinux-43`, pero `/etc/os-release` dice **Fedora Linux 44 (WSL)**;
Python existentes 3.11.15/3.12.15. Las regresiones offline no necesitan CA,
credenciales, broker, Docker en ejecución ni modelos de entrega.

`pytest==9.1.1` está fijado en dev y uv.lock. Delta propio del lock respecto a
PR42 `7983bee`: pytest y sus
dependencias nuevas colorama, iniconfig, pluggy y pygments; se conservan las
versiones preexistentes, incluido kafka-python de PR58. CI conserva `--extra kafka`
y ejecuta explícitamente `pytest tests/test_cg14_*.py`
y conserva unittest/auditoría; triggers, permisos y entrenamiento ya existente
del workflow permanecen iguales. No se lanzó CI manual. El doble TLS se limita
al test HTTP406; producción sigue verificando TLS con su contexto real.

Para el futuro ensayo RESTORE hacen falta las imágenes/digests locales de
`deploy/cg14/compose.yaml`, memoria/disco suficientes, red/binds dedicados,
CA confiable, puerto 127.0.0.1:18443 y la copia runtime revisada de IDs exactos.
El runner no instala un host vacío. Exige componentes detenidos y colas vacías;
`--resume` no repite productor incierto ni upload. No borrar recursos para
forzar esas condiciones. Filebeat necesita CSV sintético completo >228 bytes y
registro persistente. SMB real requiere autorización y secretos privados 0600.

La evidencia de esta implementación se resume en
[CG14_INTEGRATION_20261021](evidence/CG14_INTEGRATION_20261021.md).
Las brechas runtime anteriores permanecen abiertas; ASGI/dobles, comparación
de exports y mocks offline no sustituyen un ensayo integrado.

Tras incorporar PR58 se reproduce además un hallazgo heredado en Python 3.11:
el import de kafka-python 3.0.11 emite 218 DeprecationWarning de la API legacy
importlib.resources. Sus unittest no fallan, pero el runner estricto general
devuelve 1 por esos avisos. En 3.12 el probe no emite avisos. No se filtran ni se
modifica Kafka fuera de alcance. El informe registra INHERITED-KAFKA311-WARN-1
como OPEN: esta rama no acredita la matriz estricta general limpia de 3.11.
