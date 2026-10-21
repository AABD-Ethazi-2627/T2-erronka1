# CG02: portabilidad del inventario, 21/10/2026

Corrección acotada de F2 (IMPORTANT) de la auditoría del 21/10. Base deliberada:
PR42, `feat/17-maintenance-planner`, commit
`28a77543bfd67a36b96ddc2f4acc103b13f62c2e`, para el alcance activo.
El script, los tests anteriores y el inventario son idénticos a los de PR33,
`14cb8c20b9c819d08113774f260bced1d95f72a6`; el defecto se hereda.

## Reproducción antes de corregir

Windows 11, Python 3.12.10: `--check` devuelve 1; los seis tests anteriores pasan.
La comparación completa encuentra exactamente cinco diferencias: `training.file`
y los cuatro `batches[*].file` contienen separadores `\` en vez de `/`.
Linux, FedoraLinux-43 en WSL2, Python 3.12.15: `--check` devuelve 0 y pasan los
seis tests. Los hashes de las cinco fuentes coinciden con el inventario en ambos.

Se añadieron dos tests antes de cambiar el script: igualdad completa contra el
inventario guardado y reconstrucción con rutas relativas PureWindowsPath y
PurePosixPath, conservando la lectura de los archivos reales. La variante Windows
falla con el código anterior también al ejecutarse en Linux. La comparación
nativa completa falla además en Windows.

## Cambio y comprobaciones

Solo se sustituyen las dos serializaciones `str(relative_path)` por
`relative_path.as_posix()`. El inventario guardado no se regenera.

Comandos desde la raíz, con los intérpretes indicados:

```text
python -m scripts.audit_cg02 --check
python -m unittest discover -s tests -p test_audit_cg02.py -v
ruff check scripts/audit_cg02.py tests/test_audit_cg02.py
ruff format --check scripts/audit_cg02.py tests/test_audit_cg02.py
git diff --check
```

Tras el cambio, `--check` y los ocho tests pasan en ambos sistemas, sin warnings
de unittest. Ruff 0.17.1 (Windows) y su comprobación de formato pasan, al igual que
`git diff --check`. El inventario completo es igual al guardado en ambos sistemas;
su JSON canónico (claves ordenadas, separadores `(',', ':')`, UTF-8, sin salto final)
tiene SHA-256 `cf09baecb859b9a886ce8471c8bc1941e093b9383077d0ab1005c909299c2f9c`.

Los hashes iniciales y posteriores de training, cuatro batches, sources.json e
inventory.json permanecen iguales entre plataformas. El SHA-256 de los bytes de
inventory.json sigue siendo
`e2b9239e295ae2dd9b397358e02da290fc8b833c9a9903dad0f9e3a4e8ee5af3`.
Se mantienen 8.000 filas de training y 40 observaciones en cuatro batches.
No se ha usado `--write`, descargado datos ni cargado o entrenado modelos.

## Límites y siguiente revisión

El chequeo adicional `python scripts/check_repository_layout.py` pasa en Linux,
sin arrancar servicios. En Windows devuelve 2: Compose interpreta `/dev/null`
como `D:\dev\null` y falla al leer ese archivo como env-file. Se conserva ese
límite del chequeo de estructura, ajeno a F2, sin alterar el script ni ese archivo.

La suite completa y la generación de modelos del workflow no se ejecutaron
localmente. No se lanzaron workflows manuales, peticiones a Copilot, pruebas del
test final, SMB/OT, despliegues ni operaciones sobre servicios compartidos.
La publicación como draft permite la revisión independiente posterior del padre;
no declara CG02 aceptada ni autoriza cierre o merge.
