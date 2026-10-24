# Idempotencia de CG14: contrato legacy y origen estable

## Comportamiento legacy observado

Esta sección describe el parser y el laboratorio legacy. El contrato opt-in
vigente de ocurrencia y entrega está en
[CG14_PR42_INTEGRATION.md](../../docs/CG14_PR42_INTEGRATION.md).
`bind_occurrence` existe como primitiva offline; su cableado en el grafo activo
y la aceptación E2E durable siguen pendientes. El contrato de respuesta canónica
del API se documenta por separado en
[SCORING_REPLAY_CONTRACT.md](../../docs/SCORING_REPLAY_CONTRACT.md).

El validador calcula `event_id` como SHA-256 de `schema_version`, `source.kind` y
el registro CSV original. Por tanto, el mismo registro exacto desde el mismo tipo
de fuente produce la misma identidad; el offset Kafka identifica una ocurrencia
de transporte y no forma parte de la identidad de negocio. El E2E previo confirmó
que dos filas idénticas con offsets diferentes generan el mismo `event_id` y que
ambas alcanzaron el InvokeHTTP mock. No hay deduplicación persistente.

Esto deja una ambigüedad contractual: dos lecturas físicas legítimas pueden tener
el mismo contenido (por ejemplo, dos muestras iguales consecutivas). Un hash de
contenido las colapsaría si se adopta como identidad de negocio. CG03 debe
confirmar un identificador de ocurrencia estable emitido por el productor, o una
composición de campos que identifique inequívocamente la muestra. En el contrato
legacy, el offset del transporte actual sólo localiza la entrega. En el contrato
opt-in, namespace/generación/topic/partition/offset **originales** identifican una
ocurrencia estable y sí intervienen en `event_id`. Deben conservarse al republicar:
el nuevo offset pertenece a otra entrega (`delivery_id`) y no sustituye al origen.

Un retry de un FlowFile puede volver a llamar al endpoint. Un replay de Kafka
puede volver a producir la llamada. El estado de NiFi en memoria o el estado de
cola no evita esos efectos y no constituye una garantía de idempotencia.

## Diseño histórico y condiciones de integración

1. CG03 debe decidir si `event_id` representa contenido idéntico o una lectura
   física única, y si cambios de normalización, schema o fuente cambian identidad.
2. El límite que ejecuta el efecto (API/servicio de scoring) debe ofrecer una
   operación atómica respaldada por almacenamiento durable. Diseño orientativo:
   una tabla con clave única `(scope, event_id)`, hash canónico de la petición,
   estado (`IN_PROGRESS`, `COMPLETED`, `RETRYABLE`, `FAILED`), lease/versión para
   recuperar trabajo interrumpido y respuesta final persistida. La restricción
   única y una transición condicional/CAS resuelven carreras concurrentes.
3. Misma clave + mismo payload devuelve resultado estable sin repetir el efecto;
   misma clave + payload distinto produce conflicto auditable. Un `IN_PROGRESS`
   expirado se recupera con lease y política definida; no se marca `COMPLETED`
   hasta que los efectos exigidos por el contrato estén durables.
4. Si el scoring genera alertas, resultado/outbox se escriben atómicamente en la
   misma base transaccional. El publicador de outbox puede repetir entregas, por
   lo que el consumidor/destino de alertas también necesita una clave única
   durable. No existe una transacción atómica general entre NiFi, HTTP y una base
   remota.
5. NiFi debe conservar la misma clave al reintentar 5xx/timeouts. La identidad
   procede del contrato de evento: coordenadas originales preservadas en el
   binding opt-in, no el `kafka.offset` asignado a una republicación. Las
   coordenadas del transporte actual identifican la entrega y su provenance.
6. La retención de claves debe cubrir el máximo de retry, retención/replay Kafka,
   reprocesados operativos y ventana de alertas acordada. Expirar claves antes de
   esa ventana vuelve a permitir efectos duplicados.

Este diseño reduce duplicados en los límites que participan, pero no convierte
por sí mismo el flujo Kafka→NiFi→HTTP en una transacción exactly-once. Un timeout
puede ocurrir después de que el destino aplicó el efecto y antes de recibir la
respuesta; sólo una clave durable en el destino permite responder al replay sin
repetirlo. Si el destino no participa en el mecanismo, alertas repetidas siguen
siendo posibles. Sin contrato y almacenamiento idempotente del API/destino, la
garantía permanece pendiente. No se añadieron estados temporales en memoria ni
cambios a CG03/CG13.

## Validación requerida al confirmar el contrato

- Misma clave + mismo payload, primera solicitud: efecto aplicado una vez.
- Misma clave + mismo payload, replay tras respuesta perdida o reinicio: misma
  respuesta y ningún segundo efecto/alerta.
- Misma clave + payload diferente: conflicto y registro auditable.
- Dos ocurrencias legítimas con contenido idéntico pero IDs de negocio distintos:
  ambas deben conservarse, salvo que CG03 defina expresamente otra semántica.
- 422: rechazo permanente sin retry.
- 5xx/timeout: retry acotado con idéntica clave; agotamiento en DLQ durable.
- Concurrencia: dos solicitudes con la misma clave sólo aplican un efecto.
- Reiniciar NiFi, API y consumidores de alertas entre las solicitudes y verificar
  que las restricciones/estados persistentes impiden el duplicado.
- Reiniciar durante `IN_PROGRESS` y recuperar mediante lease/reconciliación sin
  dejar el evento bloqueado ni generar un segundo efecto.
- Error del destino y reintento/replay desde Kafka, conservando clave y respuesta
  coherentes.
- Expiración de clave después de la ventana contractualmente aprobada y prueba de
  replay dentro y fuera de dicha ventana.
- Caída entre persistencia del resultado y publicación de alerta: recuperación
  desde outbox sin pérdida ni doble alerta.

Estos escenarios no se ejecutaron contra un servicio real; el predictor desplegado
y su destino de alertas no forman parte del laboratorio CG14 disponible.
