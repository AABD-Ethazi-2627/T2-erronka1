# Almacenamiento propio para los verificadores ES

Los verificadores opt-in de contrato e ingestión no pueden reutilizar datos
anteriores. Antes de cualquier `docker run`, reservan en el host del motor un
directorio nuevo y sus tres hojas `data`, `java-temp` y `logs`. No borran datos
si falla una comprobación; conservan incluso un árbol parcial para inspección.

`--engine-work-dir` ahora designa una ruta final **inexistente**, bajo un padre
existente en `/mnt/d`. Este contrato sustituye al anterior que pedía preparar
un directorio ya existente. No crear previamente esa ruta ni sus hojas. Se
rechazan directorios vacíos o con contenido, archivos y symlinks, incluidos
enlaces en los ancestros. La comprobación se hace mediante descriptores
`O_NOFOLLOW` en el host del motor, no con `Path.resolve()` del cliente Windows.
Desde la raíz del sistema de archivos montado, los ancestros deben pertenecer
al operador o root y no permitir sustituciones por terceros: se rechazan
directorios compartidos escribibles sin protección sticky. Un árbol final
privado no basta si otro usuario puede renombrarlo desde su padre.

El motor debe seleccionarse con `--docker-host unix:///ruta/al/socket`. En
Windows, los dos verificadores con binds requieren `--docker-via-wsl DISTRIBUCION`;
no se presume que el sistema de archivos del cliente sea el de Docker Desktop.
El intérprete POSIX y el motor local elegido deben ver el mismo `/mnt/d`.
No se admiten sockets remotos ni se formatea o monta almacenamiento nuevo.

Ejemplo, con motor e imagen ya preparados y usando rutas nuevas:

```text
PYTHONPATH=.:tests python tests/verify_elasticsearch_contract.py \
  --work-dir D:/lab/recibos-nuevos \
  --docker-via-wsl FedoraLinux-43 \
  --docker-host unix:///mnt/d/lab/docker.sock \
  --engine-work-dir /mnt/d/lab/ext4/ensayo-nuevo
```

`--work-dir` conserva recibos locales y también debe ser nuevo. Si se omite
`--engine-work-dir`, se reserva un hijo `engine-<UUID>` dentro del directorio de
recibos visto desde el motor. No se usan las antiguas hojas `work/data` por
suposición. El recibo registra las tres fuentes reales de los binds.

El host prepara almacenamiento para el UID1000 de la imagen ES. El operador
debe ser UID1000 o root. Root cambia propiedad solo de los inodos recién
creados; no hay `chown` recursivo ni permisos globales. El sistema de archivos
debe poder conservar propiedad y permisos privados; si no, la reserva falla
antes de arrancar el contenedor. Un directorio NTFS compartido que no respete
estos permisos no se considera equivalente a ext4.

La reserva no protege frente a un administrador o proceso del mismo usuario
que sustituya deliberadamente el árbol entre la reserva y el montaje por Docker.
Usar almacenamiento privado del operador y un motor local de confianza. No
apuntar a datos de otros ensayos, servicios o usuarios.

`tests/test_es_workspace.py` comprueba reserva exclusiva, contenido conservado,
symlinks/escapes, errores de permisos y rechazo de ambos verificadores antes de
invocar Docker. La CI POSIX ejecuta los casos de sistema de archivos que no
pueden ejecutarse en Windows. Son pruebas inertes; no validan una nueva campaña
real de Elasticsearch, el bundle CG32 o aceptación humana.
