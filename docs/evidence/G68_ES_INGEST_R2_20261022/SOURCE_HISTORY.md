# Fuentes publicadas de PR74 y revisión de mantenimiento en PR75

Los logs, respuestas HTTP, resultados, comandos registrados y sellos de esta
carpeta describen ejecuciones anteriores. Se conservan sin modificación. Esta
revisión de mantenimiento no atribuye esas ejecuciones a los scripts corregidos.
El informe y el procedimiento originales de PR74 conservan su alcance histórico.

Antes de editar se copiaron los cuatro scripts publicados en el commit
`50d5268b5ef85e2c9779c00b1ab05f9241a75032` (idénticos a los de la base PR42
`ac4cf855d330050eb884a924b1b14d00bbb62ed0`). Las copias son datos históricos
en texto, con sus bytes intactos; las versiones `.py` siguen siendo código
ejecutable y participan en las comprobaciones globales sin exclusiones nuevas.

| Versión de mantenimiento | Copia de los bytes publicados anteriormente |
| --- | --- |
| [documented_setup.py](documented_setup.py) | [documented_setup.py.txt](original-sources/documented_setup.py.txt) |
| [red_assertions.py](red_assertions.py) | [red_assertions.py.txt](original-sources/red_assertions.py.txt) |
| [red_probes.py](red_probes.py) | [red_probes.py.txt](original-sources/red_probes.py.txt) |
| [run_checks.py](run_checks.py) | [run_checks.py.txt](original-sources/run_checks.py.txt) |

[source-versions.json](source-versions.json) identifica el commit de procedencia,
los hashes anteriores y los de mantenimiento. Los hashes actuales del manifest
CG25 cambian deliberadamente para estos cuatro scripts y se añaden las copias y
esta explicación. `historical_snapshot`, los digests de resultados y los demás
hashes existentes permanecen intactos.

Cambios: formato Ruff 0.17.1, orden de imports, eliminación de 18 imports sin
uso y cinco argumentos explícitos `check=False`, que conservan el valor previo
de `subprocess.run`. En las dos sondas, `validators` pasa a importarse dentro de
`main`, junto a la fixture sintética, después de configurar la ruta de módulos.
La construcción de un registro con `dict(clave=valor)` pasa a literal de
diccionario con las mismas claves, valores y orden, para resolver C408 al
comprobar el formato nuevo con las reglas predeterminadas.
Las rutas originales y el alcance de los arneses se conservan; no son un CLI
portable ni un nuevo resultado de integración.

La comparación del AST comprueba el inventario exacto de imports retirados y
la igualdad del resto del programa al normalizar imports, `check=False` y esa
construcción equivalente del diccionario de registro.
Un control con una constante alterada confirma que detecta cambios adicionales.
Controles locales de los helpers comprueban éxito, error de subproceso, rechazo
de estado HTTP inesperado y conservación de códigos y hashes de logs del runner.
Las aserciones rojas se repiten contra el mismo `red-result.json`, tanto con la
copia como con el script corregido: tres fallos esperados y cero errores en cada
caso. Ese resultado es un control negativo, no un gate aprobado.

La evidencia de esta revisión está en
`D:/github/_local/t2-babysit-20261021/evidence-lint-20261022`.
No se repiten los ensayos Docker ni la suite de 77 pruebas; no cambia código de
producto, contratos, datos, modelos, configuración Ruff ni dependencias. Esta
revisión no ejecuta servicios, entrenamiento, inferencia, bundle o test final.
