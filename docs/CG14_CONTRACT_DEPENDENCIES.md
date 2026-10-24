# CG14 — dependencias de contratos para integración

Estado: documento de compatibilidad y preguntas pendientes; no modifica
contratos de otros equipos. Responsables descritos por módulo porque no hay
asignación nominal confirmada en el checkout. Las propuestas locales no se
consideran decisiones aprobadas.

## CG03 — evento de telemetría

| Confirmación necesaria | Propuesta/observación local | Responsable | Bloqueo que resuelve |
|---|---|---|---|
| Versión y evolución de `schema_version` | Propuesta `0.1.0` en `docs/CG14_VALIDATION_CONTRACT.md` | Responsable CG03 | Evitar aceptar o serializar versiones incompatibles |
| Identidad de una ocurrencia: definición de `event_id` | Ahora SHA-256(schema + `source.kind` + bytes raw) si el productor no lo envía; dos filas idénticas comparten ID | Responsable CG03/productor | Distinguir replay de dos muestras legítimas con igual contenido |
| Campos requeridos, nombres, tipos, unidades y límites físicos | Propuesta: machine id/type, temperaturas K, rpm, torque Nm, desgaste min y timestamp UTC; límites de parque/sensor pendientes | Responsable CG03 + mantenimiento | Fijar esquema validable sin reglas inventadas |
| Semántica de `timestamp`, zona y precisión | Propuesta UTC ISO-8601 `Z` | Responsable CG03/productor | Normalización y orden temporal |
| `machine_id`, `machine_type`, valores enumerados y etiquetas | Propuesta local `CNC-000..999`, `H/M/L`; etiquetas sólo entrenamiento | Responsable CG03 | Validación y separación de inferencia |
| Política de rechazo y sobre de error | Códigos locales documentados; forma final, campos y retención sin aprobar | Responsable CG03 + CG13 | Interoperabilidad de rechazos y replay |
| `source`, raw original y privacidad/retención | Contrato local propone source/ref/raw; obligatoriedad/retención sin ratificar | Responsable CG03 | Trazabilidad sin persistir datos excesivos |

## CG13 — Kafka y transporte

| Confirmación necesaria | Valor actual | Responsable | Bloqueo que resuelve |
|---|---|---|---|
| Bootstrap y `advertised.listeners` del broker autorizado | Sólo `cg14-kafka-test:9092` en broker aislado de laboratorio; ningún endpoint real confirmado | Responsable CG13/infra | Conexión al entorno correcto |
| Protocolo TLS/SASL, truststore y provisión de credenciales | Lab `PLAINTEXT` en red Docker privada, sin publicación de host; no es política de producción | Responsable CG13/seguridad | Evitar credenciales/datos en transporte no confiable |
| Topic RAW y entorno (dev/test/prod) | No confirmado; no consumir | Responsable CG13 | Evitar topic inventado o lectura de datos reales |
| Formato por mensaje: una fila CSV, JSON o lote; encoding/delimitador | No confirmado; afecta `FLOW_FILE` frente a `DEMARCATOR`/`RECORD` y `record.count` | Responsable CG13 + CG03 | Preservar límites de registros y `event_id` |
| Particiones, key, orden y máximo tamaño | No confirmado; key no se fija por intuición | Responsable CG13 | Escalado y semántica de orden |
| Consumer group y ownership | El lab crea groups únicos por run; ningún group productivo confirmado | Responsable CG13 | Evitar competir con consumidores del equipo |
| Commit/offset, replay, retención y garantía de entrega | En NiFi lab `Commit Offsets` activo; recovery probado con offsets/lag; no exactly-once | Responsable CG13 | Diseñar recuperación compatible con política real |
| Topic/sobre de rechazo y dead-letter | Sólo DLQ local persistente; nombre/retención Kafka de rechazo no definidos | Responsable CG13 + CG03 | Acordar clasificación, replay y operación |

## CG28 — API de scoring y efectos

| Confirmación necesaria | Valor actual | Responsable | Bloqueo que resuelve |
|---|---|---|---|
| URL base, método y auth de scoring | `scoring/score_api.py` tiene marcadores pendientes; mock local no es `/predict` real | Responsable CG28 | Llamada de integración productiva |
| Request JSON y transformación desde evento CG03 | Sin contrato real aprobado | Responsable CG28 + CG03 | Compatibilidad de campos y tipos |
| Response: score, umbral/alerta, explicación y `model_version` | No implementado/confirmado en el servicio disponible | Responsable CG28 | Interpretación segura del score; no inferir riesgo cero ante error |
| Correlación `event_id` y propagación | No confirmada por API | Responsable CG28 + CG03 | Trazabilidad extremo a extremo |
| HTTP 422, 5xx, timeout, rate limit y retry-after | Se simulan respuestas con mock local; política real pendiente | Responsable CG28 | Distinguir rechazo permanente de fallo transitorio |
| Clave de idempotencia, dedupe durable y respuesta repetida | Sin API/destino durable disponible | Responsable CG28 + dueño de almacenamiento/alertas | Evitar doble efecto tras replay/timeout |
| Alertas: destino, outbox, retención, deduplicación | No disponible en laboratorio | Responsable CG28/operaciones | Evitar alertas finales duplicadas o perdidas |

## Secuencia de integración al recibir confirmaciones

1. Registrar las versiones aprobadas CG03/CG13/CG28 y cambios como decisión de
   integración; conservar estas propuestas y sus versiones históricas.
2. Ajustar configuración parametrizada de broker, auth, topic, group, schema y
   API en entorno de desarrollo aislado. No introducir secretos en Git.
3. Actualizar el Process Group independiente `CNC-GUARD-CG14-DEV` sin iniciar el
   consumo; validar propiedades/Controller Services en NiFi `2.12.0`.
4. Probar con fixture acordada y destino no productivo: offsets, errores, DLQ,
   retries, provenance, identidad y reinicio. Confirmar primero que mensajes no
   contienen lotes o definir split que conserve offset y `event_id` por registro.
5. Revisar idempotencia y retención con el dueño del efecto final. Sólo activar
   consumo al aprobar cambio, ventana de prueba y rollback.

No hay responsables nominales confirmados; asignarlos es parte del handoff.
