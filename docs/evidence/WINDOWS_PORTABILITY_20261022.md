# Portabilidad Windows: comprobación del 22/10/2026

Proyecto educativo, no MKDL. Base PR42:
`8caf98962175fabcf13fbc1584dc890cf4f0135f`, árbol
`82a69eba2754045619a2c2d218473605183bb9c3`. Rama del cambio:
`fix/windows-portability-20261022`. El SHA publicado pertenece a la PR del cambio;
este informe no constituye merge, aceptación docente ni aprobación de main.

## Reproducción y causas

Se repitió la suite estricta de la base exacta con Windows Python 3.11.9 y
3.12.10: cada vuelta reproduce **4 failures y 84 errors**, con un aviso de WMIC
en la primera vuelta. Coincide con la atribución previa base/candidato de PR66.
No son 88 defectos independientes: importaciones `fcntl`/`resource`, primitivas
POSIX de permisos/directorios, temporales no reabribles y conexiones SQLite que
seguían abiertas producen múltiples diagnósticos derivados.

La base exacta también se ejecutó dos veces por versión Fedora: **284 tests,
3 skips, cero failures/errors/warnings/unraisables**. La distribución seleccionada
es explícitamente `FedoraLinux-43`; su OS identifica **Fedora 44**. Intérpretes:
3.11.15 y 3.12.15. Los temporales POSIX usan `/tmp` sobre el filesystem Linux.

## Resultado final ejecutado

En **cada una de las cuatro combinaciones Windows/Fedora y Python 3.11/3.12**:

- `tests/run_strict_resources.py`: **303 tests por vuelta, dos vueltas**;
  3 skips y cero failures, errors, warnings o unraisables en ambas.
- `python -B -W error -m pytest -p no:cacheprovider -q tests`:
  **558 passed, 3 skipped, 250 subtests passed**, exit 0.

Ambas capas se solapan; sus recuentos no se suman como pruebas independientes.
Los tres skips existentes corresponden a Elasticsearch sin servicio desechable
configurado. No se añadieron skips ni filtros de warnings para ocultar fallos.
Los mensajes de fixtures negativas de modelos/parser permanecen en stderr.

Full pytest descubrió además **51 fallos Windows** en el journal local de las
fixtures RESTORE, que unittest no ejecutaba. La escritura pura ahora usa las
primitivas de plataforma. El bloqueo operativo RESTORE sigue rechazando Windows
antes de crear estado o acceder a login/red. Las pruebas sustituyen DEPLOY por
su propio temporal y no contactan con el host NiFi/RESTORE.

La revisión independiente R1 reprodujo una regresión de importación de CG23 al
ejecutar directamente el archivo. Se corrigió y se añadió una prueba desde otro
directorio sin PYTHONPATH. R2 ejecutó las cuatro ayudas directas con exit 0 y
cerró F1; no encontró otros hallazgos accionables en su alcance. R2 inspeccionó
RESTORE y los registros de suites del autor; no se atribuyen esas suites al
revisor. La aprobación del padre sigue siendo una fase distinta.

## Contratos conservados y límites

El [contrato de plataforma](../PLATFORM_SUPPORT.md) describe fsync POSIX,
bloqueos nativos, propietario/DACL Windows y el perfil explícitamente más débil
de recuperación de proceso Windows. Los tests incluyen muerte de procesos,
replay, corrupción, rechazo de recibos, orden de ACK y ausencia de otro worker.
No se afirma durabilidad Windows ante corte eléctrico, caída del kernel o
pérdida de disco. El requisito de fsync de directorios puede exigirse y se
rechaza explícitamente en Windows antes de aceptar trabajo.

Las identidades, configuración de journal, claves, hashes y codificación de
rutas históricas no se migran. Copiar journals entre POSIX/Windows no es una
migración admitida. Las fixtures SQLite conservan su contexto de transacción y
añaden cierre determinista. La captura SMB cierra los temporales antes de una
segunda apertura o publicación mediante hard link.

Solo cambia una dependencia: **joblib 1.4.2 → 1.5.3**, cuyo loky usa CIM antes de
WMIC. La comparación estructural del lock conserva 58 registros y solo cambia
joblib y su requisito raíz. Se conserva sklearn 1.5.0, NumPy 1.26.4, DuckDB 2.0.0,
PyArrow 23.0.1 y el wheel Kafka parcheado. PyPI confirma URL, tamaño y SHA-256
del sdist/wheel; wheel `joblib-1.5.3-py3-none-any.whl`: **309071 bytes**,
SHA-256 `5fc3c5039fc5ca8c0276333a188bbd59d6b7ab37fe6632daa76bc7f9ec18e713`.
La sonda de núcleos con `-W error` pasa en los cuatro entornos.

Se reutilizaron intérpretes y cachés existentes y se crearon cuatro venv frozen
en D:, sin instalar en los venv anteriores. Los inventarios de paquetes quedan
en la evidencia. Los bytes lógicos de los venv se inventarían por separado;
no se presentan como consumo físico adicional por el uso de enlaces/cachés.

Las pruebas usan el bundle existente `synthetic-matrix-only` y fixtures propias;
los tests heredados incluyen pequeños fits sintéticos. No se ejecutó un
experimento de entrenamiento, empaquetado del bundle de entrega ni evaluación
del test final. Los hashes RF/IF/manifest/ledger existentes y las otras ramas
locales permanecen idénticos; no se limpiaron clones, datos o recursos ajenos.

## Checks y trazabilidad

Ruff **0.17.1** default, `E,F,I,PLW1510` y format; lock --check; auditoría de
57 paquetes; CG02; CG25; layout; actionlint y diff del rango completo: exit 0.
La auditoría no encuentra vulnerabilidades conocidas ni estados adversos;
conserva el aviso de que `uv audit` es experimental. CG25 conserva sus
metadatos, histórico y `human_review=pending`; no se inventa una firma humana.

El [resumen sellado](WINDOWS_PORTABILITY_20261022.json) incluye comandos,
resultados, hashes de logs, inventarios y hashes de las fuentes revisadas.
Las trazas completas y las rondas fallidas se conservan en
`D:/github/_local/t2-babysit-20261021/windows-portability/`, junto con los
controladores `control.py`, `prepare.py`, `checks.py` y los informes R1/R2.
Los sellos R2 y de cierre comprueban las fuentes estables; los runners originales
no tomaban un hash del árbol al principio de cada subprocess. Se conserva ese
límite de atribución, sin presentar evidencia reconstruida como sello en vivo.

Incidencias de ensayo retenidas: WSL/Service/WSAETIMEDOUT; un intento Fedora
parcial cancelado; puntero Git absoluto Windows no válido en la copia Fedora,
corregido a relativo; tres skips extra por faltar la fixture sintética en esa
copia, recuperada sin entrenamiento; primer intento de inventariar symlinks
Linux desde Windows, corregido con lstat. Ninguno acredita un pase inicial.

No se crearon contenedores, redes ni volúmenes persistentes para este cambio.
Solo se usaron archivos, subprocesses y sockets loopback temporales de tests.
Kafka/NiFi/SMB/Elasticsearch reales, capacidad sostenida, apagado, recuperación
del host, despliegue y aceptación humana requieren su propia evidencia.
