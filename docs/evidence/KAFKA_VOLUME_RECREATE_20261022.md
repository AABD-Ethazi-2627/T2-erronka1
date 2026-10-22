# Persistencia Kafka tras recreación, 2026-10-22

Corrección de PR68 sobre PR42 `85cd1d0c8da1b57dd8b1083ee2ff43e4e4e18eab`.
Worktree exclusivo `D:/github/_worktrees/t2-kafka-volume-20261022`, rama local
`fix/pr68-kafka-volume-20261022`. El merge normal de la base es
`babbc028878c920c554aab916e3d3df138f10d76`, árbol
`28a3547c8c28e28af06dbcfb76d5536107c01a1c`. No se hizo force push ni merge
de PR68. La revisión independiente del padre sigue pendiente.

## Defecto y corrección

El Kafka histórico `t2-real-20261022-0937-kafka`, ID
`28d70b96fca30458914c3f8cb26fe7bcc388778bcb78f7b5cb35d38a5463b464`, escribió
en `/tmp/kafka-logs` de su capa. El restart histórico preservó ese contenedor;
no probó la persistencia en su volumen. Su inspect completo antes/después de
esta corrección es idéntico: continúa detenido y conserva todos sus mounts.
No se extrajeron, movieron ni borraron sus datos.

El arranque nuevo pasa un fichero de propiedades explícito directamente a
`kafka-storage.sh` y `kafka-server-start.sh`, sin defaults del entrypoint:

- `log.dirs=/var/lib/kafka/data` y
  `metadata.log.dir=/var/lib/kafka/metadata`, ambos dentro del bind de D:.
- Bind adicional al destino exacto `/var/lib/kafka/data`: la imagen 3.7.2
  declara un `VOLUME` ahí que oculta un bind al directorio padre. Se descubrió
  y conservó el intento inicial que permitió identificarlo.
- Capa de sólo lectura; logs y temporales Java en `/lab/runtime`, otro bind
  de D:. TMPDIR/TEMP/TMP y opciones JVM sólo en procesos propios.
- El arranque prueba escritura en ambos directorios y rechaza metadata
  parcial o cluster ID distinto; no reformatea almacenamiento existente.
- Compose y el guard de RESTORE verifican los destinos nuevos. El export
  NiFi staged conserva su función de bridge y no adquiere propiedad del
  broker ni de sus offsets.

El Compose opcional sigue fijado a Kafka 4.3.1; no se arrancó ni recreó esa
instancia. El ensayo nuevo usa exclusivamente la imagen oficial 3.7.2 ya
instalada, ID `sha256:8bd63e1bd445e5e19427a4bdbcc3d23bf6efd774b058a41b36ba87fda7623e34`,
con `--pull=never`, puerto aleatorio loopback, label único y binds de D:.

## Ensayo nuevo realmente ejecutado

Evidencia local: `D:/github/_local/t2-babysit-20261021/kafka-volume-fix/`.
Resultado completo `recreate-06/results.json`, label
`t2.kafka.volume.run=t2-volume-2ae1c6a12277`:

- Primer ID: `3ae7f07746981d252936afd2519090f7e894168afc122dc70246e186279ce0cf`.
  Producción de seis mensajes con claves/bytes/offsets exactos0–5; consumer
  con coordinación de grupo recibe0–2 y confirma offset3.
- Parada controlada con shutdown completo de BrokerServer; eliminación sólo
  de ese ID propio. La JVM devuelve143 tras SIGTERM; el gate exige además
  cierre completo y ausencia de OOM, y rechaza137/cierre incompleto.
- Segundo ID distinto:
  `7e06a058f92b5ee295f6dbf58285ac9517762c138f9845c553d030814246d929`.
  Mismos binds `recreate-06/storage`, metadata KRaft idéntica byte a byte,
  offset retenido3, rejoin real, lectura3–5 y commit6 confirmado. Otro grupo
  reproduce los seis mensajes con las mismas claves/bytes/orden/offsets.
- Capa sin cambios frente a los puntos de montaje materializados por Docker.
  El rootfs es read-only y todos los mounts son binds explícitos, sin
  almacenamiento anónimo del broker.
- Probe propio con el mismo bind en sólo lectura:
  `56b755af846a59614d519f077d86df7a167dddfb033b97dc36a371bdea80fd32`.
  Falla con exit1 y `Read-only file system` antes de arrancar el broker;
  metadata conservada. No hay fallback a la capa ni ACK/commit de prueba.

Los dos contenedores finales quedan detenidos y el bind conserva sus datos.
`preservation.json` acredita los 88/88 contenedores existentes antes del primer
intento; `recreate-06/results.json`, los 95/95 antes del ensayo final. No se borraron volúmenes, imágenes ni
redes. Intentos anteriores propios detenidos, binds y logs se conservan.

## Integración de la base y validación

El único conflicto del merge fue `docs/memoria/manifest.json`: se conservó el
manifiesto base y se calcularon las huellas de pyproject, lock y test durable
combinados. Las huellas de RESTORE/test se actualizan con esta corrección.
Los helpers de PR67 (`platform_io`, `private_files`, locks, fsync y paths) y
los consumidores de archivo/pipeline quedan idénticos a la base actual.

Validación final y huellas de los logs:
[`KAFKA_VOLUME_RECREATE_20261022.json`](KAFKA_VOLUME_RECREATE_20261022.json).

- Fedora44/WSL, Python3.11.15 y3.12.15: **242 tests +106 subtests por versión**,
  warnings como errores, sin fallos ni skips.
- Windows nativo, Python3.11/3.12: **150 tests focales por versión**, sin
  fallos ni skips; no se repite la suite global ni se extrapola su resultado.
- Ruff0.17.1 E,F,I,PLW1510 sobre Python rastreados y formato de los cuatro
  Python cambiados; CG02, CG25, lock, audit, layout, actionlint, Compose y
  diff del rango base/candidato. Audit:57 paquetes, cero vulnerabilidades.

Se conservan también los
fallos iniciales del harness y del entorno: opción de AdminClient incompatible,
montaje oculto por VOLUME, guard excesivo del script read-only, expectativa de
exit0, comparación incorrecta de puntos de montaje Docker, Ruff E501 y pytest
FD-capture/0600 sobre DrvFS sin metadata. Ninguno se cuenta como un gate pasado.

Las pruebas Windows focales pasan en los venv existentes de D:. Para POSIX,
la distro `FedoraLinux-43` informa Fedora44. DrvFS sin metadata falla doce
pruebas por permisos; una vista privada con metadata resuelve once, pero aún
falla la lectura de un descriptor abierto tras unlink. No se cambia el helper
para acomodar esa semántica de DrvFS.

La validación POSIX final usa una imagen ext4 de 512MiB en
`kafka-volume-fix/posix-temp.ext4`, montada en `process-temp-posix` bajo D: sólo
dentro de un namespace privado; usuario Fedora y TMPDIR/TEMP/TMP por proceso.
`posix-mount-proof.json` acredita ext4 en el namespace del runner y DrvFS sin
cambios en el host. La herramienta de formato se extrajo de RPM oficiales de
Fedora a D:, sin instalar paquetes en el sistema. El fichero ext4 se conserva.
No se usa `/tmp` nuevo. Pytest usa captura `sys`; no se omiten pruebas ni se
relajan las comprobaciones de permisos o unlink.

## Límites

Ensayo de un broker con parada controlada y recreación, no caída del host,
corte eléctrico, pérdida de disco, multinodo ni rebalance durante escritura.
No se repiten la ruta NiFi/API/CG15/ES ni las doce tandas de capacidad: su
evidencia histórica permanece en `REAL_KAFKA_NIFI_20261022.md`. No cambia la
lógica de esos consumidores y se ejecuta su regresión focal. No hubo acceso
a SMB/OT, NiFi compartido, modelos de entrega, entrenamiento ni testfinal.

CI del nuevo SHA, revisión independiente, merge, aceptación docente y
producción son estados separados. Los dos checks de `aa079c7` son históricos
y no validan esta corrección.
