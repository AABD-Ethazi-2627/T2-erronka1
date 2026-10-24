# PR65: recibos durables y validación HTTP acotada

Proyecto educativo; no se aplica política MKDL. Corrección de F1 BLOCKER/P1
(nuevo en PR65) y F2 IMPORTANT/P2 (heredado), ambos de confianza alta, de la
revisión independiente del head `ae1343b8b6fdbc88333158f37de084e3a4822f6b`.
La rama autora incorpora mediante merge normal PR42
`53f342df39ff7e8d744186c22d61b456bb8f6d7a`, árbol
`5383a7edf91c89200ed98d32601cedaf75720308`, con PR62 y PR64. No hubo conflictos.
Esto no implica merge de PR42 en main ni aprobación de PR65.

## Contratos corregidos

- Cada salida CG15 de un job pendiente o completado exige recibo `stored` o
  `duplicate` y hash del stream/bytes esperados. El replay de un `rejected`
  no satisface el destino aunque sus contadores indiquen `rejected=0`.
  Se conserva la consulta read-only previa para completados y la verificación
  de todos los objetos de CG15. No cambia archive_consumer ni se edita un
  recibo para convertir un rechazo en éxito.
- La API mantiene 32.768 bytes/413 antes de cualquier decisión de profundidad,
  también con cuerpo fragmentado. Más de 64 contenedores JSON da 422 antes
  del parsing; cadenas UTF-8 y escapes no cuentan como contenedores. El error
  de validación conserva una ubicación de campo acotada sin serializar input,
  claves extra, valores, mensajes del cliente ni contexto recursivo. No hay
  captura nueva de MemoryError ni de errores internos.

## Evidencia y reproducción

Directorio local de tarea: `_local/t2-babysit-20261021/durable-pipeline-fix-r2`
fuera del repositorio; `procedure.md`, `run.py`, `extras.py`, logs y JSON
conservan comandos, exits y resultados. No se redistribuyen modelos o datasets.

`test_durable_receipts_http.py` usa HTTP Uvicorn por loopback, SQLite y Parquet
reales, con dobles de modelos sintéticos en memoria. Conflictos previos con
rpm=1501 frente a rpm=1500 bloquean cuatro intentos de cada stream, sin ACK ni
completed y con bytes previos intactos. Se comprueba commit de origen incierto,
recibos completados inválidos y recuperación sin inferencia adicional.

Las regresiones ejecutadas contra las fuentes originales obtenidas mediante
`git show` fallan antes del arreglo. El probe original reproduce ACK en el
segundo intento de F1 y HTTP500/RecursionError con 4.001 bytes en Python 3.12;
en Python 3.11 ese mismo cuerpo es rechazado por el parser con 400. Esa
diferencia se conserva en los logs y no se presenta como 500 en ambas versiones.
Las pruebas corregidas exigen 422 acotado en ambas, cuerpos profundos de objetos,
listas y mezclas, malformed JSON, UTF-8/escapes y límites 32.768/32.769 bytes.
Los inválidos no puntúan ni crean ledger; Telemetry válida sin modelo da 503.

El primer manejador fijo de 422 rompía el contrato `detail[0].loc` existente;
el estricto lo detectó. Se conservó el test original y se corrigió el manejador
para mantener ubicación acotada. Los logs fallidos permanecen como evidencia.

Los crashes de procesos propios `os._exit(73)` ejercitan HTTP incierto,
archivo de Prediction y antes del ACK. Otro crash antes de archivar conserva
un conflicto de Telemetry durante cuatro replays en procesos nuevos. Un trigger
SQLite aborta realmente la transición a completed: rollback, cero ACK y replay
posterior sin nueva inferencia. No es pérdida eléctrica ni RESTORE del host.

`verify_durable_pipeline.py` usa ES 9.5.4 real de imagen local existente,
`--pull=never --network=none`, sin puertos ni volúmenes compartidos, datos tmpfs
y curl por docker exec a su loopback. Comprueba operación normal y replay,
rechazos persistidos de ambos streams antes de contactar ES y conflicto real
ES `_create`/GET antes de ACK. Todos sus recursos son propios y se retiran.

## Límites y aceptación

La evidencia de ejecución local, estáticos y captura CI exact-head se cierra
en el REPORT.md local. No hay entrenamiento, modelos de entrega, test final,
Apache Kafka real, NiFi vivo, SMB/OT, RESTORE del host ni infraestructura
compartida. Los seis skips del estricto conservan su condición de skips.
La revisión padre sobre el SHA publicado y la aceptación del equipo siguen
pendientes. No se declara CG14 DONE, RESTORE VERIFIED ni exactly-once distribuido.
