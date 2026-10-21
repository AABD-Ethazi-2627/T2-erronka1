# CG14 — propuesta de contrato y validación de ingesta

Estado: **propuesta local, pendiente de aprobación de CG03 y CG13**.
Versión propuesta: `0.1.0`. Este documento no sustituye el contrato que se
apruebe en CG03.

## Alcance y separación de datos

`data/ai4i2020_train.csv` es un dataset histórico de entrenamiento: tiene 13
columnas, no tiene `timestamp`, `event_id` ni `schema_version`, y no se procesa
como si fuera un evento operativo. El evento que llega desde el simulador tiene
un timestamp UTC delante de esas 13 columnas (ejemplo del enunciado:
`2026-04-29T10:57:50Z,CNC-039,L,299.0,308.6,1587,38.6,124,0,0,0,0,0,0`).
La línea de streaming conserva por compatibilidad las 6 columnas de etiquetas,
que son ground truth para entrenamiento/evaluación y nunca features del
modelo. El adaptador CSV las valida como `0/1`, las elimina del evento
normalizado y, si alguna está activa (`1`), la registra como aviso
`TRAINING_LABEL_STRIPPED` conservando el original para auditoría: una fila de
fallo real nunca pierde su telemetría en inferencia. El replay offline en modo
`training` las conserva tal cual. En cambio, un evento JSON canónico que traiga
etiquetas en inferencia se rechaza (`TRAINING_LABEL_IN_INFERENCE`): el
productor JSON no debe enviarlas.

Los campos originales del dataset son:

| Campo | Tipo propuesto | Unidad / regla |
| --- | --- | --- |
| `machine_id` | string | `CNC-000` a `CNC-999`; origen del registro |
| `machine_type` | enum | `H`, `M` o `L` |
| `air_temp_K` | number finito >0 | Kelvin |
| `process_temp_K` | number finito >0 | Kelvin |
| `rpm` | number finito no negativo | revoluciones por minuto |
| `torque_Nm` | number finito no negativo | Nm |
| `tool_wear_min` | number finito no negativo | minutos |
| `machine_failure` | integer 0/1 | solo histórico; no entra en inferencia |
| `failure_TWF`, `failure_HDF`, `failure_PWF`, `failure_OSF`, `failure_RNF` | integer 0/1 | solo histórico; no entra en inferencia |

No se usan mínimos/máximos observados en entrenamiento como límites físicos.
Los límites operativos de cada sensor quedan **PENDIENTES** de confirmación con
mantenimiento/CG03; en esta fase solo se rechazan tipos inválidos, valores no
finitos, temperaturas Kelvin <=0 y otras magnitudes físicas negativas. El código
`NEGATIVE_PHYSICAL_VALUE` se conserva también para Kelvin cero. `machine_id` acepta el
formato `CNC-000`–`CNC-999` y no se restringe al rango observado `CNC-001`–`CNC-050`
verificado en el CSV (8.000 filas, 50 máquinas, tipos H/M/L); acotar el parque
de máquinas queda **PENDIENTE** de CG03.

## Metadatos operativos

Requeridos en el evento normalizado:

- `event_id`: SHA-256 hexadecimal en minúsculas. Si el productor no lo envía,
  el adaptador de referencia calcula `SHA256("cnc.telemetry.v0.1.0\n" +
  source_kind + "\n" + raw_record)`. Este ID de contenido heredado se conserva
  para compatibilidad; no distingue dos ocurrencias iguales. Para mezclar las
  rutas PR42/CG14 se requiere la migración explícita por coordenadas originales
  y sidecar descrita en [integración](CG14_PR42_INTEGRATION.md). No se recalculan
  IDs persistidos en el parser ni en el puente.
- `timestamp`: UTC ISO-8601 con `Z`, por ejemplo
  `2026-10-15T08:09:06Z`. No se aceptan offsets locales ni fechas imposibles.
- `schema_version`: `0.1.0` mientras CG03 no apruebe otra versión.
- `quality_flag`: `OK` para la ruta válida.
- `source`: `kind`, `uri`, `record_ref` y `raw_record`. `raw_record` conserva
  exactamente la línea recibida para auditoría y reprocesado.

`timestamp` proviene del mensaje operativo del simulador. `source.uri` y
`record_ref` provienen del adaptador de entrada (Filebeat/NiFi); no deben
confundirse con columnas históricas. La semántica final de `kind` y la
obligatoriedad de `raw_record` quedan **PENDIENTES** de ratificación en CG03.

## Reglas y rechazos

Se rechaza sin reparación silenciosa cuando falta un campo obligatorio, el
CSV no tiene exactamente timestamp + 13 columnas, aparece la cabecera como
dato (tanto la histórica de 13 columnas como la de streaming con prefijo
`timestamp`, detectada por contenido además de por longitud), un número no se
puede convertir, es `NaN`/infinito, el tipo de máquina no pertenece a `H/M/L`,
el timestamp no es UTC `Z`, una etiqueta sale de `0/1`, o hay etiquetas
activas en inferencia. Los códigos estables del validador son:

`MISSING_REQUIRED_FIELD`, `MALFORMED_CSV`, `HEADER_ROW`, `INVALID_NUMERIC`,
`NON_FINITE_NUMERIC`, `INVALID_TIMESTAMP`, `INVALID_MACHINE_TYPE`,
`NEGATIVE_PHYSICAL_VALUE`, `INVALID_EVENT_ID`, `UNSUPPORTED_SCHEMA_VERSION`,
`INVALID_QUALITY_FLAG`, `INVALID_SOURCE`, `UNEXPECTED_FIELD`, `INVALID_TYPE`, `INVALID_MODE`,
`MESSAGE_TOO_LARGE`, `TRAINING_LABEL_IN_INFERENCE` e `INVALID_LABEL`.
Aviso no bloqueante: `TRAINING_LABEL_STRIPPED` (etiquetas de ground truth
retiradas de la telemetría de inferencia, original conservado).
`INVALID_MODE` cubre un modo desconocido en el adaptador de referencia; NiFi
debe tratarlo como error de configuración, no como dato rechazable de rutina.

Todos los rechazos son permanentes: reprocesar los mismos bytes da el mismo
veredicto, así que NiFi los envía a `cnc.rejected` sin reintento (ver
`cg14_validation/resilience.py`: `is_permanent_rejection` / `should_retry`).
Solo las señales de transporte (`KAFKA_UNAVAILABLE`, `PUBLISH_FAILED`,
`CONSUME_TIMEOUT`, `SCORING_TIMEOUT`, `SCORING_5XX`, `ES_UNAVAILABLE`) admiten
reintentos acotados con backoff (`retry_delays`), y después van a
retry/dead-letter, nunca se descartan en silencio.

Resistencia a entradas no confiables: el adaptador rechaza sin excepción
entradas no textuales (`INVALID_TYPE`) y líneas que superen
`CG14_MAX_LINE_BYTES` (defecto 8192) o campos de más de
`CG14_MAX_FIELD_CHARS` (defecto 512) con `MESSAGE_TOO_LARGE`, conservando solo
un prefijo para auditoría. Los sensores ausentes o inválidos nunca se rellenan
con cero: se rechazan con `INVALID_NUMERIC`.

El rechazado conserva el payload original, el código, el campo afectado, el
mensaje, `source` y la hora de rechazo añadida por NiFi. La lista final de
campos del sobre de error y su retención quedan **PENDIENTES** de CG13.

Las discrepancias históricas conocidas (fallo principal frente a subtipos,
incluidos subtipos activos sin fallo principal y varios subtipos) no se
corrigen ni eliminan automáticamente. Se conservan en el dataset de
entrenamiento y se documentan como calidad histórica para una decisión de
modelado posterior.

## CSV y entradas incompletas

Filebeat debe descartar la cabecera antes de Kafka, pero NiFi vuelve a detectar
`HEADER_ROW` como defensa. Un CSV malformado, incompleto o con columnas de más
va a `cnc.rejected`; nunca se rellena con ceros ni se publica parcialmente.
El registro original se conserva en el rechazo. La fixture de tests es
sintética y no modifica el CSV de entrenamiento.

## NiFi: flujo versionable (generado, no desplegado)

Existe artefacto versionable sin credenciales:

- `nifi-flows/cg14_validate.groovy`: única fuente de verdad de la validación
  (motor Groovy, NiFi 1.25.0). Replica regla por regla el contrato v0.1.0 y el
  validador Python, con los mismos códigos estables y `event_id` determinista
  SHA-256.
- `nifi-flows/cg14_validation_flow_v0.1.0.json`: template generado por
  `scripts/build_cg14_nifi_flow.py` (no editar a mano; regenerar).
  Ruta `ConsumeKafka → procedencia → ExecuteScript → RouteOnAttribute →
  PublishKafka`, con reintento acotado (3) y dead-letter auditable. Topics,
  broker y presupuestos viajan en el contexto de parámetros `CG14-params`.
- `tests/test_cg14_nifi_flow.py`: exige script incrustado idéntico al
  `.groovy`, parámetros resolubles, versiones fijadas y cableado válido/
  rechazado/reintento. El esqueleto `cnc_fase1_INCOMPLETO.json` queda intacto.

La configuración anterior solo contenía `ConsumeKafka`, un `ConvertRecord`
incompleto y Elasticsearch; sin servicios de controlador, topics CG13 ni ruta
auditable de rechazos.

Cuando CG13 confirme nombres, claves y grupos, en NiFi basta importar el
template y enlazar `CG14-params`:

1. `ConsumeKafka` lee el topic raw con el grupo dedicado `cnc-nifi-cg14`.
2. `UpdateAttribute` fija procedencia (`source.kind/uri/record_ref`) y
   presupuestos sin tocar el contenido.
3. `ExecuteScript` valida, genera `event_id` determinista y escribe JSON
   normalizado (válidos) o sobre de error (rechazados); los fallos del motor
   van a su propia ruta `failure`, separada de los rechazos de validación.
4. `RouteOnAttribute` separa `valid` → `cnc.telemetry.validated` y
   `rejected`/`unmatched` → `cnc.rejected`, con `machine_id` como atributo
   para particionado futuro (clave definitiva PENDIENTE de CG13).
5. Los fallos de publicación reintentan acotados y terminan en dead-letter
   (`LogAttribute`), nunca desaparecen en silencio; sin afirmar exactly-once.

Lo que impide darlo por probado: CG03 (esquema), CG13 (topics/keys/grupos/
retención/rechazo) y NiFi/Kafka vivos (sin Groovy/Java locales ni broker).
No se ha realizado prueba de integración NiFi/Kafka/Elasticsearch.
