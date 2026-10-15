# Validación y política de CI

Los PRs de trabajo se mantienen en borrador. No hay triggers `push`,
`pull_request` ni `pull_request_target`: abrir o actualizar un PR no ejecuta CI.
No se debe usar el workflow de sincronización de Projects como sustituto de CI:
puede modificar datos del planning si se ejecuta sin dry-run.

## Validación de ML antes del merge

`validate-manual.yml` solo admite `workflow_dispatch`. Tiene permisos
`contents: read`, no recibe secrets, no publica ni despliega y no ejecuta la
búsqueda completa de entrenamiento. Instala Python 3.14 y `requirements-ci.txt`.

1. Instala ruedas binarias de las dependencias fijadas, sin depender de paquetes del host.
2. Ejecuta Ruff sobre scripts, pruebas y los módulos de inferencia implementados.
3. Ejecuta todas las pruebas con unittest, incluida la comprobación real de hashes,
   particiones, etiquetas, puntuaciones de modelos recargados y métricas F1/F2.
4. Ejecuta las celdas de los notebooks entregados para detectar importaciones o
   dependencias ausentes; no vuelve a seleccionar modelos o umbrales.

La API `score_api.py` sigue siendo una plantilla incompleta. No se incluye en el
lint ni se afirma que se haya probado su arranque. Se deberá incorporar a la
validación cuando se implemente la integración HTTP/NiFi/Docker.

El workflow nuevo debe existir primero en la rama por defecto para poder
lanzarlo mediante workflow_dispatch. Hasta su primera integración, las pruebas
se reproducen localmente en un entorno limpio. Después, al preparar un merge:

```bash
gh workflow run validate-manual.yml \
  --repo AABD-Ethazi-2627/T2-erronka1 --ref NOMBRE_DE_LA_RAMA
```

Verificar que la ejecución corresponde al SHA exacto que se va a mergear y que
terminó correctamente. Cambiar la rama después exige volver a validar ese SHA.
No hay auto-merge ni comprobaciones remotas obligatorias configuradas por este PR.

## Reproducción local

```bash
python3.14 -m venv /tmp/cnc-ci-local
/tmp/cnc-ci-local/bin/python -m pip install --only-binary=:all: -r requirements-ci.txt
/tmp/cnc-ci-local/bin/python -m pip check
/tmp/cnc-ci-local/bin/ruff check scripts tests scoring/inference.py scoring/model_features.py
/tmp/cnc-ci-local/bin/ruff format --check scripts tests scoring/inference.py scoring/model_features.py
/tmp/cnc-ci-local/bin/python -m unittest discover -s tests -v
/tmp/cnc-ci-local/bin/python -m scripts.check_ml_artifacts
```

2026-10-15: reproducción local con instalación limpia y celdas de ambos notebooks;
no constituye una ejecución de GitHub Actions ni una prueba del runner Ubuntu.
La sintaxis de ambos workflows se verifica localmente con `actionlint`.

## Sincronización programada de Projects

Es una automatización administrativa independiente, cada ocho horas y manual.
Solo necesita Python estándar para sus pruebas propias. El nombre del repositorio
es `T2-erronka1`, mientras el campo del equipo se mantiene como `B-taldea`.

La última ejecución inspeccionada falló por falta de `PROJECTS_SYNC_TOKEN`:
[ejecución 38682511263](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/38682511263).
Requiere una credencial dedicada configurada por un administrador, luego dry-run,
aplicación y verificación de paridad. No se ha activado ni alterado esa credencial.
Detalles: [PROJECTS_SYNC.md](PROJECTS_SYNC.md).
