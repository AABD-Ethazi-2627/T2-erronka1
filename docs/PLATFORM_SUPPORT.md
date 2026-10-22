# Contrato de plataforma y persistencia local

Python 3.11 y 3.12 son las versiones admitidas por el lock. Este proyecto es un
laboratorio educativo. La compatibilidad de código no constituye aceptación
docente, certificación industrial ni prueba de recuperación de infraestructura.

## Archivo CG15, journal CG14 y registros locales

El contrato depende de la plataforma y del filesystem. `durability_profile()` en
`scripts.platform_io` devuelve el perfil vigente; no son garantías equivalentes:

- **`posix-fsync`:** conserva el orden existente: escribir, flush/fsync del
  archivo, rename en el mismo filesystem, fsync del directorio y commit SQLite
  `synchronous=FULL` antes de ACK. También sincroniza los padres al recuperar
  directorios ya existentes. Un error de persistencia impide ACK. Requiere un
  disco local que respete esas primitivas; no certifica hardware/controladores,
  SMB/NFS, pérdida de disco ni una transacción distribuida exactamente una vez.
- **`windows-process-recovery`:** flush/fsync de archivos cerrados antes de
  instalarlos mediante `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)`, y commit
  SQLite `synchronous=FULL` antes de ACK. `sync_directory` valida la existencia
  del directorio, pero **no ejecuta ni simula un fsync POSIX de metadatos**.
  Admite recuperación tras muerte del proceso con el sistema operativo y disco
  disponibles. No promete persistencia de creación/rename de directorios ante
  corte eléctrico, caída del kernel o pérdida del volumen. No se solicita flush
  privilegiado del volumen ni se ha ensayado un corte de energía.

Para exigir el contrato con fsync de directorios, pasar
`require_power_loss_durability=True` a `archive_consumer.consume` o a `Pipeline`,
o `--require-power-loss-durability` a `scripts.kafka_archive` y
`scripts.run_durable_pipeline`. En Windows falla explícitamente antes de crear
estado o aceptar trabajo; en POSIX mantiene los requisitos de disco local.
La opción no convierte por sí sola un almacenamiento POSIX en hardware validado.

Los bloqueos son propiedad del sistema operativo: `flock` en POSIX y bloqueo de
un byte con `msvcrt.locking` en Windows. El archivo de bloqueo no se elimina.
El worker CG14 rechaza un segundo propietario sin esperar al intervalo de poll;
el watcher y el registro shadow esperan el bloqueo. Cerrar el descriptor o matar
el proceso libera el bloqueo. Los checksums, identidad de entrega, detección de
corrupción, recibos de archivo y orden de ACK conservan sus comprobaciones.

Las rutas almacenadas en los ledgers existentes conservan su codificación
histórica `str(Path)`. Copiar un journal entre Windows y POSIX no es una migración
admitida; esta corrección no reescribe claves, configuraciones ni hashes previos.

## Credenciales NiFi y SMB

`scripts.private_files` abre y valida el descriptor antes de leer secretos:

- POSIX exige archivo regular, `O_NOFOLLOW`, propietario UID actual y ausencia
  de permisos de grupo/otros. Rechaza FIFO sin bloquear.
- Windows exige un disco local con ACL persistentes, archivo regular sin
  reparse point final, propietario igual al usuario del proceso y DACL que solo
  conceda acceso a ese usuario, LocalSystem o Builtin Administrators. Rechaza
  UNC/dispositivos, alternate data streams, DACL nulas y ACE efectivas que no
  pueda interpretar. `chmod(0600)` no proporciona esa protección en Windows.

Los ancestros deben ser confiables; estas comprobaciones no aíslan del propio
usuario ni de administradores privilegiados. Los temporales SMB tienen permisos
privados desde la creación y pueden abrirse desde un subprocess. Se cierran y
eliminan al salir normalmente o por excepción; una muerte forzada puede dejar
temporales privados. No se promete borrado seguro. Se requiere un `smbclient`
compatible instalado por el operador; las pruebas locales no acreditan una
conexión SMB/NiFi real ni compatibilidad con todo binario Windows de smbclient.

## Herramientas, dependencias y pruebas

El RSS de CG23 usa `GetProcessMemoryInfo.PeakWorkingSetSize / 1024` en Windows
y `getrusage().ru_maxrss` normalizado a KiB en POSIX. Son medidas del proceso,
no capacidad del pipeline distribuido. Las rutas de dispositivo nulo usan
`os.devnull`. Los temporales compartidos se cierran antes de reabrirlos y las
fixtures SQLite cierran su conexión además de terminar su transacción.

joblib queda fijado en **1.5.3**: su loky consulta CIM en Windows antes del
fallback WMIC. No se filtran warnings ni se fija un número ficticio de núcleos.
El resto del lock se conserva. Las pruebas usan fixtures propias ya existentes
y pequeñas fixtures sintéticas; no autorizan reentrenar un bundle de entrega,
usar el test final ni asumir compatibilidad universal de pickles.

El runner operativo `deploy/cg14/scripts/run-restore-e2e.py` sigue requiriendo
host POSIX: su bloqueo rechaza Windows explícitamente. La importación y el plan
offline pueden comprobarse sin importar `fcntl` ni tocar el host NiFi/RESTORE.
Las suites herméticas no ejecutan operaciones sobre ese host.

Los servicios reales y los recursos compartidos requieren su propia evidencia.
Un skip por Elasticsearch no configurado sigue siendo cobertura pendiente.
Una revisión técnica y CI tampoco sustituyen la aprobación humana de main.

## Fuentes de las primitivas

- [Python 3.12: fsync y límites de chmod Windows](https://docs.python.org/3.12/library/os.html).
- [MoveFileExW y WRITE_THROUGH](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw).
- [FlushFileBuffers: permisos y alcance](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers).
- [Bloqueos msvcrt](https://docs.python.org/3.12/library/msvcrt.html#msvcrt.locking).
- [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo).
- [CreateFileW: reparse points y sharing](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
- [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo).
- [joblib 1.5.3: consulta CIM de loky](https://github.com/joblib/joblib/blob/1.5.3/joblib/externals/loky/backend/context.py).
