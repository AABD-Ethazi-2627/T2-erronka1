# CG05/CG29: publicación de lotes y laboratorio pendiente

El tramo activo es SMB `ls/get` → captura local validada → directorio de CSV
inmutables → Filebeat **9.5.4** → Kafka. Filebeat no recibe credenciales SMB ni
lee un mount remoto directamente. La equivalencia SMB/NFS sigue pendiente del tutor.

## Protocolo de publicación

El productor debe escribir un nombre fuera del patrón final, por ejemplo
`cnc_batch_YYYYMMDD_HHMMSS_SEQUENCE.csv.part`, cerrar el archivo y renombrarlo al
nombre final dentro del mismo share. Desde ese momento los bytes y el nombre son
inmutables. No escribir progresivamente en un `.csv` ya visible. Esta condición
debe confirmarse con el responsable del simulador; no se ha comprobado en red.

`capture_once` compara el tamaño del listado previo, los bytes descargados y el
tamaño del listado posterior. Si cambia o desaparece, falla antes de publicar;
una nueva invocación vuelve a intentarlo. Esto detecta descargas cortas y cambios
de tamaño observados, **no** mutaciones del mismo tamaño, un prefijo estable que
el productor anuncie prematuramente como final, ni cambios posteriores al segundo
listado. No hay prueba universal de completitud sin el protocolo del productor.

Se exige cabecera del contrato y al menos una fila, UTF-8 sin BOM, delimitador
coma, campos sin comillas y líneas LF, incluida la última. Es el formato observado
de los snapshots, compatible con el filtro de cabecera y mensajes por línea.
No se normalizan ni reparan bytes. El auditor existente comprueba anchura,
campos vacíos, dominios numéricos y fechas UTC; NiFi conserva sus validaciones
adicionales. Un CSV inválido se guarda por SHA-256 en `quarantine/*.bin`, fuera del
glob de Filebeat. Un fallo de transporte no publica el temporal descargado.

La publicación local usa archivo temporal fuera del glob, flush/fsync y enlace
exclusivo. Un fallo antes del enlace deja el CSV ausente. El reinicio conserva
capturas previas y descarga nombres pendientes; una publicación explícita repetida
de bytes idénticos no cambia el archivo, y bytes distintos para el mismo destino
se rechazan. La captura no revalida nombres ya presentes: depende de su
inmutabilidad. No usar varios capturadores sobre el mismo directorio.

`--watch` termina ante errores; no es un servicio con recuperación automática ni
un timer instalado. Tras resolver la causa, relanzar el mismo comando con el
mismo `--output`. No borrar CSV, quarantine, registry ni histórico para ocultar
duplicados. La retención y la recuperación duradera posteriores pertenecen al
archive existente; este trabajo no cambia NiFi, scoring ni adaptadores Kafka.

## Qué demuestra la comprobación offline

```bash
python -m unittest discover -s tests -p 'test_smb*.py' -v
python -m scripts.smb_filebeat_fixture --output outputs/smb-filebeat-fixture
```

Ejecutar desde la raíz con Python 3.11/3.12 del entorno bloqueado; el directorio
de salida debe ser nuevo. La factoría no abre sockets ni ejecuta Filebeat.
`manifest.json` guarda origen, hash, tamaños, mensajes y claves esperadas:

- `ten_rows.csv`: copia byte idéntica del snapshot congelado, 10 filas, 850 B.
- `one_row.csv`: cabecera y primera fila congelada, 233 B, sin inventar fechas.
- `tiny_synthetic.csv`: 217 B; fecha e identidad congeladas, sensores/etiquetas
  centinela explícitamente sintéticos. No son mediciones ni datos de entrenamiento.
- `header_only.csv`, `partial.csv` sin LF final e `invalid.csv`: rechazo esperado
  por captura. No deben copiarse directamente al directorio vigilado.

Las pruebas usan dobles de `smbclient`/subprocess para fallos de conexión,
autenticación, acceso, lectura y timeout. Comprueban limpieza de auth0600,
ausencia de secretos en argumentos/errores, no publicación parcial, recuperación,
rename local y replay de bytes. El control estático comprueba los literales del
contrato en configuración; no reemplaza el parser de Filebeat.

El oráculo de clave calcula SHA-256 de **`|message|<línea>|`**, seguido de `:` y
el offset de byte inicial. Es la serialización del procesador `fingerprint`
para `fields: [message]`, no SHA-256 de la línea sola. El primer offset es 164.
No contiene path: rename o replay del mismo archivo conserva la clave esperada.
No diferencia dos archivos distintos con idéntica línea en el mismo offset;
esa es la semántica heredada, no una garantía de identidad universal.
No se emula registry, ACK, particionado, deduplicación ni ejecución NiFi.

## Comprobación futura con Filebeat real, sin Kafka

**Protocolo pendiente de ejecutar.** Requiere Docker local autorizado, imagen
9.5.4 ya disponible, directorio nuevo, disco local con enlaces/rename y acceso
de lectura/escritura a sus propios directorios. No descargar imágenes ni usar
volúmenes, contenedores o puertos de otros trabajos. Los siguientes comandos son
Bash para un laboratorio aislado; detenerse si el nombre ya existe.

```bash
docker image inspect docker.elastic.co/beats/filebeat:9.5.4
python -m scripts.smb_filebeat_fixture --output outputs/cg29-lab-fixture
mkdir -p outputs/cg29-lab/{watched,empty,registry,result}
docker run --pull=never --rm --network=none \
  docker.elastic.co/beats/filebeat:9.5.4 version
docker run --pull=never --rm --network=none \
  -v "$PWD/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro" \
  docker.elastic.co/beats/filebeat:9.5.4 \
  filebeat test config -e --strict.perms=false
docker run --pull=never -d --name cg29-filebeat-offline --network=none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro" \
  -v "$PWD/outputs/cg29-lab/watched:/mnt/cnc-smb:ro" \
  -v "$PWD/outputs/cg29-lab/empty:/mnt/cnc-stream:ro" \
  -v "$PWD/outputs/cg29-lab/registry:/lab-registry" \
  -v "$PWD/outputs/cg29-lab/result:/lab-output" \
  docker.elastic.co/beats/filebeat:9.5.4 filebeat -e --strict.perms=false \
  -E path.data=/lab-registry -E filebeat.registry.flush=0s \
  -E output.kafka.enabled=false -E output.file.enabled=true \
  -E output.file.path=/lab-output -E output.file.filename=events \
  -E 'output.file.codec.format.string=%{[@metadata.cnc_line_sha256]}:%{[log.offset]}|%{[message]}'
python -c 'from pathlib import Path; from scripts.capture_smb import publish_snapshot; publish_snapshot(Path("outputs/cg29-lab-fixture/ten_rows.csv").read_bytes(), "outputs/cg29-lab/watched/batch.csv")'
```

Registrar digest de imagen, versión, comandos, logs y hashes sin secretos.
Esperar de forma acotada hasta 10 líneas en los archivos `result/events*.ndjson`;
si vence el plazo, guardar el fallo, no afirmar PASS. Comparar cada línea con
`key + "|" + message` del manifiesto, como multiconjunto, sin cabecera. Detener
con `docker stop --time 20 cg29-filebeat-offline`, conservar logs y registry.
Renombrar `batch.csv` a `renamed.csv` dentro de `watched`, ejecutar
`docker start cg29-filebeat-offline`, observar un plazo acotado y detener otra vez:
el total esperado sigue siendo 10. Repetir un restart adicional sin cambiar nada.
Guardar offsets, claves, archivos de salida y estado antes/después; ni un plazo
sin mensajes ni un simple contador prueban por sí solos ausencia de pérdida.

En directorios de laboratorio **nuevos** y con registry independiente, repetir
con `one_row.csv` y `tiny_synthetic.csv`, un registro cada uno. Para replay con
registry perdido usar otro directorio nuevo; esperar 10 eventos con las mismas
claves y conservar evidencia del duplicado. No eliminar el registry anterior.
Las fixtures comparten prefijo y pueden compartir identidad de fichero: no
mezclarlas en un mismo input/registry para probar el tamaño.

La configuración mantiene offset 164/length 64 y los IDs existentes. El umbral
estático sería 228 B, no 264. En v9.5.4 `growing` es verdadero por defecto y usa
bytes disponibles en archivos pequeños con contenido posterior al offset.
No se cambia el fingerprint ni se migra registry en esta PR. Confirmar ingestión
de la fixture de 217 B con el binario, sin deducirla de nuestro oráculo.

## Aceptación que aún requiere laboratorio autorizado

La salida a fichero anterior solo comprobaría harvester, filtro, procesador y
registry local. Para #36 faltan Kafka **aislado y propio**, output Kafka activo,
captura de claves/payloads y offsets reales de topic/partición, restart con ACK
pendiente y desconexión/reconexión del broker. Usar los contratos y el adaptador
del proyecto, sin inventar otro consumidor ni afirmar exactly-once.

Para #5 faltan un share de prueba propio con cuenta de solo lectura y secretos
fuera de Git, `smbclient` versionado, protocolo de publicación confirmado y
autorización para interrumpir ese servidor de prueba. Medir caída durante `ls`
y `get`, autenticación incorrecta, recuperación, mutación y rename del productor;
conservar bytes/hashes y resultados negativos. No apagar el SMB compartido.
Revisión del padre, otro miembro y tutor, incluida equivalencia SMB/NFS, pendientes.

Referencias oficiales consultadas el 21/10/2026:
[serialización del procesador v9.5.4](https://github.com/elastic/beats/blob/v9.5.4/libbeat/processors/fingerprint/fingerprint.go),
[growing v9.5.4](https://github.com/elastic/beats/blob/v9.5.4/filebeat/input/filestream/identifier_fingerprint.go),
[scanner v9.5.4](https://github.com/elastic/beats/blob/v9.5.4/filebeat/input/filestream/fswatch.go),
[salida de fichero](https://www.elastic.co/docs/reference/beats/filebeat/file-output).
