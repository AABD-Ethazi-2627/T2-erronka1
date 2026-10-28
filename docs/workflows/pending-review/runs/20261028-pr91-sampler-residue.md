# PR91: residuo F3 del muestreador

Base revisada: `41d6922b92f8442ddc6a8adc9ea93e56e9a9e747`.
Informe independiente: `D:/reviews/pr91-recheck-20261028-41d6922/report.md`.

El muestreador perdía el lag leído si Docker fallaba antes de añadir la muestra.
Su excepción quedaba en un hilo sin comunicación al principal y una corrida
podía terminar `completed`. Se conserva la muestra Kafka antes de consultar
Docker y se ejecuta el muestreador como Future. Su error cancela la oferta,
se propaga al principal y queda en `observer_errors`; un error durante el último
drenaje también falla después de guardar la evidencia y cerrar el observador.

Cuatro regresiones inertes cubren lag excesivo seguido de Docker fallido,
fallo sin exceso, fallo al final del drenaje y recorrido real
`run → measure → finalize_run` con recibo `failed` y cleanup de servicios.
Las fronteras de servicios se simulan; no se ejecuta campaña nueva.

Validación del padre: 51 pruebas CG32 y nueve subpruebas pasan. Suite general
con Python 3.11.9 existente y `-W error`: 722 passed, 14 skipped y 361 subtests
passed. Los skips ambientales se conservan; no acreditan servicios/bundle/TLS
opt-in ni POSIX en Windows. Logs y comandos propios en
`D:/reviews/pr91-sampler-fix-20261028/`.

Unittest: 434 tests, OK (skipped=14). CG25 pasa 40 criterios, 90 enlaces,
260 hashes vivos y 18 históricos; CG02, repository layout, Ruff check/format
y diff-check pasan. El script checks.ps1 termina con exit 0. Sin campañas,
builds/escaneos nuevos ni servicios compartidos.

Solo cambia el hash vivo de `scripts/cg32_lab.py`; no se reescriben crudos,
imágenes, excepciones de seguridad o snapshots históricos. Revisión del arreglo
por el padre; las revisiones independientes anteriores no se atribuyen al nuevo
SHA. CI y aprobación remota se evalúan aparte antes de integrar.
