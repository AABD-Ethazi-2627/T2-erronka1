# CG14 y el camino integrado de scoring

Corte revisado: PR57 `aace73cade05932e85a7a268fc1db288d4b60b4e`,
`main` `9be87b66207c2b7a2a74f5bd1a15b104c5937b6e` y PR42
`f446ddaac911431b598e0ecfa961c3caff4164f2`. Este documento describe
compatibilidad local. No acredita NiFi, Filebeat, Kafka, SMB ni RESTORE vivos.
La [matriz de PR57](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/aace73cade05932e85a7a268fc1db288d4b60b4e/docs/CG14_ACCEPTANCE_MATRIX.md)
conserva sus estados parciales y evidencias históricas.

## Dos rutas existentes

PR42 ya contiene `nifi-flows/cnc_lab_completed.json`,
`nifi-flows/normalize_csv.groovy`, `/predict`, captura SMB y configuración
Filebeat. PR57 añade otro laboratorio, con su propio mock y flujo de validación.
Las descripciones de PR57 que llaman a la API un esqueleto se refieren a su
base `main`; no describen la integración actual de PR42.

El normalizador de PR42 produce el sobre estricto CG03 y guarda el raw como
atributo de auditoría. El validador de PR57 produce `source.raw_record`; ese
campo, que puede contener etiquetas, es rechazado por la API integrada.
Los tipos `cg14-kafka-lab` y `restore-<run>` tampoco pertenecen al enum de la API.
Además, CG14 Python admite temperatura cero, Groovy admite temperaturas
negativas, y la API requiere Kelvin estrictamente positivo.

`scripts/cg14_scoring_bridge.py` prepara únicamente el cuerpo de petición desde
un evento **ya normalizado** de CG14. Conserva `event_id`, timestamp, URI y
referencia; retira `source.raw_record` de una copia y aplica el validador
`Telemetry` de la API. No altera el original. Las etiquetas como campos JSON,
campos desconocidos, valores no finitos, fechas inválidas y Kelvin no positivo
siguen rechazados. El adaptador no parsea CSV ni sustituye el normalizador
existente de PR42.

Un alias de origen exige configurar el valor de entrada exacto y el destino.
No se infiere que un laboratorio sea SMB. El operador debe conservar el evento
original y sus bytes en el archivo de auditoría antes de publicar la petición;
la función y el CLI no implementan ese almacenamiento ni realizan llamadas HTTP.

```bash
# Desde la raíz del checkout, con el entorno Python de PR42.
# normalized-event.json debe ser un evento CG14 sintético retenido localmente.
python -m scripts.cg14_scoring_bridge normalized-event.json \
  --expected-source-kind cg14-kafka-lab --source-kind lab_fixture \
  > scoring-request.json
```

La salida es el cuerpo JSON de `/predict`. Un fallo devuelve código 1 sin
emitir petición ni contenido de entrada en el diagnóstico. Para origen ya
canónico se omiten ambos argumentos de alias. El límite del fichero CLI es
32768 bytes. Una respuesta 503 de la API sin bundle acredita validación de
petición y ausencia de modelo preparado, nunca scoring satisfactorio.

## Identidad y transporte pendientes

PR42 calcula `event_id = SHA256(kafka.key)`; Filebeat forma la key con su
fingerprint de `message` y `log.offset`. PR57 calcula el hash de versión,
`source.kind` y línea original. La misma fila puede tener IDs diferentes según
la ruta; dos ocurrencias idénticas pueden colapsar en PR57. El puente conserva
el ID recibido y no resuelve esa decisión contractual. No deben mezclarse ambos
productores como si fueran la misma identidad ni archivarse el sobre original
y su proyección como dos telemetrías con igual ID y contenido diferente.

Los dos laboratorios tampoco comparten broker, topic, grupo, red ni endpoint:
PR42 usa `kafka:9092`, topics `cnc-sensors-lab-v2`/`cnc-sensors-smb-v1` y
`scoring-api:8000/predict`; CG14 usa `cg14-kafka-test:9092`, topics por run,
red `cg14-nifi` y `/predict/<scenario>` del mock. Unir las redes o cambiar sólo
la URL no implementa el contrato, la identidad ni el archivo durable.
El adaptador Kafka→archivo se desarrolla por separado; aquí no se duplica.

El flow de CG14 confirma offsets al consumir. Falta probar el límite de fallo
entre ese punto y la persistencia del destino. El archivo durable de PR42 no
está cableado a los sinks de CG14. Un `event_id` compartido no garantiza
deduplicación de alertas ni entrega exactly-once.

## Prerrequisitos concretos del laboratorio

1. Usar host Linux con Python 3.11/3.12 y dependencias bloqueadas de PR42.
   RESTORE requiere `fcntl`; no se ejecuta de forma nativa en Windows.
   Las regresiones del puente usan transporte ASGI y no requieren servicios,
   modelos de entrega ni acceso al dataset de test final.
2. Para repetir los tests de PR57 hacen falta pytest y una corrección del test
   `test_login_406_aborts_before_confirmation_or_upload`: construye TLS usando
   un certificado local ignorado antes de su doble HTTP. En checkout limpio
   falta ese fichero. El test debe inyectar su contexto TLS, sin depender de
   secretos locales. El entorno bloqueado de PR42 no declara pytest y su CI
   ejecuta unittest; las funciones pytest de PR57 no se ejecutarán allí.
3. Para laboratorio CG14 vivo, disponer previamente de NiFi 2.12.0, Kafka
   4.3.1 y Python Alpine con los digests de `deploy/cg14/compose.yaml` de PR57.
   Su configuración reserva hasta 5 GiB/3 CPU para NiFi, 1 GiB/1 CPU para Kafka
   y 128 MiB/0.25 CPU para cada mock. Se necesita margen del host y disco para
   repositorios/provenance. No se descargaron imágenes en esta revisión.
4. El runner RESTORE está ligado a la copia existente por IDs e inventario;
   **no sirve para un host vacío**. Requiere el grupo y servicio exactos del
   inventario, CA confiable con nombre localhost, NiFi en 127.0.0.1:18443,
   contenedores `cnc-cg14-nifi`/`cnc-cg14-kafka-test`, red `cg14-nifi`, binds
   Kafka/DLQ esperados, imagen mock ya local y colas vacías/componentes detenidos.
   El Compose raíz de PR42 usa otros nombres, puerto 18080 e imagen NiFi 2.0
   local por defecto; no satisface esas guardas.
5. Inspeccionar primero el manifiesto persistente de RESTORE. `--resume` sólo
   reanuda el mock propio de un run preparado sin test/producer previo;
   resultado incierto de productor exige `--verify`/`--stop`, nunca replay.
   No repetir upload ni usar los runners del grupo original sobre la copia.
6. Para Filebeat aislado, crear un directorio nuevo con CSV sintético completo
   y cabecera; el archivo debe superar los 228 bytes exigidos por el fingerprint
   (`offset=164`, `length=64`). Mantener su volumen de registro durante reinicios;
   no reiniciar offsets borrando el registro. Fijar explícitamente topics/grupos
   de ensayo, una línea UTF-8 por mensaje y conservación de key/metadatos.
7. La captura SMB real requiere `smbclient`, acceso de sólo lectura y fichero
   privado modo 0600 con `SMB_HOST`, `SMB_SHARE`, `SMB_USERNAME`, `SMB_PASSWORD`
   y opcional `SMB_TIMEOUT` (1–60 s). No es requisito para las pruebas offline.
   Los scripts de captura/validación ya existen: queda conectar y reconciliar
   captura→Filebeat→Kafka→NiFi→API→archivo con evidencia de reinicio. No se
   accedió a SMB ni a infraestructura compartida en esta revisión.

## Integración y aceptación pendientes

La composición PR57+PR42 tiene conflicto en `README.md`: conservar la guía
activa de PR42 y añadir un enlace a CG14 sin reemplazarla por el alcance antiguo.
No se publicó ni modificó la rama ajena de PR57.

Antes de ejecutar y aceptar RESTORE, reforzar `functional_pass()` de PR57:
actualmente no utiliza el inventario y acepta un mapa vacío de processors y
cuatro objetos DLQ vacíos si se aportan los demás atributos. Debe reconciliar
IDs de componentes, escenarios por evento, resultados DLQ y reintentos, y
rechazar evidencia incompleta. Esto es independiente de las guardas runtime
que sí comprueban identidad/configuración. Un chequeo de estructura JSON no
demuestra la ejecución real de fixtures.

Quedan la ejecución HTTP 2xx/422/5xx/timeout, habilitación VALID de la copia,
reconciliación durable de destino y revisión independiente del padre/equipo.
Los tests nuevos no resuelven esos gates ni aceptan CG14 globalmente.
