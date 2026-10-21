# CG04 — integración con el camino activo de PR42

Base deliberada: PR42 `28a77543bfd67a36b96ddc2f4acc103b13f62c2e`, rama
`feat/17-maintenance-planner`. Se adapta la separación data/schemas/features/train
de PR43 `a0c33600b99c9af9decb90d8129306244d59b35d`; no se importa su lock ni se
sustituye la API. El ejercicio 80/20 permanece en esa PR como trabajo separado.

Python permite usar pandas, Pydantic y el Pipeline de scikit-learn en preparación
y entrenamiento sin traducir transformaciones a otro lenguaje (G52/G55).
`cnc_guard.data` delega en `scoring.scope.load_training_source` (bytes autorizados)
y `scoring.preparation.split_development` (membresía exacta). `features` valida los
seis predictores, separa el objetivo y conserva índices. `train` reutiliza
`scripts.experiment_rf.pipeline`, incluida la transformación física serializable
de `scoring.preparation.features`; no duplica esas fórmulas. El notebook invoca
el módulo desde la raíz mediante su propio intérprete: funciona también al
abrirlo desde `notebooks/`, sin PYTHONPATH ni instalación global del proyecto.

## Preparación sin entrenamiento

Desde la raíz en FedoraLinux-43, usando uv 0.13.1 y un entorno **propio del clon**:

```bash
uv sync --frozen --python 3.11
uv lock --check
uv run --frozen python -m scripts.cg04_preparation
uv run --frozen python -m unittest discover -s tests -p 'test_cg04_reconciliation.py' -v
```

El comando de preparación solo compara índices y sus hashes. Usa las etiquetas
para reconstruir la estratificación, sin estimadores, predicciones ni métricas
del test. Confirma 5600/1200/1200, disjunción, cobertura y cero filas excluidas en
fit. Reproduce el solapamiento histórico de 394/1200 en el fit 6400 del ejercicio
80/20. Eso demuestra incompatibilidad de promoción, sin atribuir fraude ni una
afirmación de evaluación independiente a PR43.

El notebook se puede ejecutar con herramientas efímeras, sin cambiar el lock:

```bash
uv run --frozen --with ipykernel==6.30.1 --with nbconvert==7.16.6 jupyter nbconvert --to notebook --execute notebooks/02_training_TEMPLATE.ipynb --ExecutePreprocessor.kernel_name=python3 --output cg04-index-only.ipynb --output-dir outputs/cg04-reconcile
```

No importa el grupo notebook de PR43. Las salidas van a `outputs/`, ignorado por
Git. Esta ejecución no produce modelos. La revisión del notebook por otro
miembro y su aceptación docente siguen pendientes; tener pruebas no las suple.

## Separación entre demostración y bundle

`cnc_guard.train.train_model(path)` es una demostración opcional en memoria:
fit solo sobre el 70%, accuracy sobre el 15% de **desarrollo reutilizado**, y el
15% ya inspeccionado queda excluido. Devuelve `(model, report)`; no guarda pickle
ni manifiesto. No reproduce la búsqueda CG08, selección de umbral o canal IF.
El informe lleva `artifact_role=CG04_DEVELOPMENT_ONLY`. Las pruebas entrenan
únicamente con una fixture sintética de 100 filas, en memoria.
La firma adaptada no acepta `model_path` ni `overwrite` de PR43; no se deben
superponer su notebook o `train.py` sobre este camino activo.

`scripts.package_model` rechaza ese rol, un informe sin particiones o membresías
distintas de las canónicas **antes de leer/copiar artefactos**. Conserva la ruta
CG08 → RF + CG09 → IF → bundle v4. La API sigue leyendo `manifest.json`, `rf.pkl`
e `if.pkl`, validando alcance, versión sklearn y hashes antes de deserializar.
La prueba API usa un manifiesto incompleto que solo contiene `artifact_role`:
demuestra rechazo por falta de scope antes de deserializar, no un guard API de
ese rol. El rechazo explícito del rol pertenece al empaquetador. La prueba usa
HTTPX ASGI con lifespan explícito, sin depender del helper de PR51 ni cambiar
la API de producción.
Un modelo de CG04 aislado no satisface ese contrato. Los manifiestos e informes
son declaraciones en un directorio de confianza, no firmas de procedencia;
esta barrera evita promoción accidental, no falsificación deliberada.
El empaquetado requiere el `report.json` original de CG08, con sus listas de
índices; el resumen compacto `docs/evidence/CG08_results.json` no lo sustituye.
Un bundle existente no se modifica ni necesita volver a empaquetarse por este
cambio. No reconstruir ni atribuir membresías a un artefacto sin procedencia.

## Versiones y artefactos

- Camino activo: lock Python `>=3.11,<3.13`, NumPy 1.26.4, pandas 2.2.2,
  scikit-learn 1.5.0, joblib 1.4.2; Docker/API usa Python 3.11.
- PR43: Python `>=3.12`, NumPy 2.2.6 y un lock propio. Compartir sklearn 1.5.0
  no prueba compatibilidad binaria ni equivalencia de preparación/particiones.
- Esta integración mantiene `pyproject.toml`, `uv.lock`, requirements y API de
  PR42. No carga pickles entre esos entornos, no cambia bundles ni vuelve a
  entrenar la entrega. Las versiones verificadas están en el registro local.

Para cualquier futura promoción se necesita el entorno de entrenamiento y
dependencias compatibles, la misma preparación y membresía, y revisión del
bundle completo; no copiar ni probar a cargar el pickle del ejercicio. La
[documentación de persistencia de scikit-learn 1.5](https://scikit-learn.org/1.5/model_persistence.html#workflow-overview)
requiere las mismas versiones del entorno y no respalda cargar modelos con
versiones diferentes de sklearn o posiblemente de NumPy/SciPy. No se afirma que
la API actual compruebe todas las versiones: su guard explícito sigue siendo
sklearn, además de alcance y hashes. Armonizar toda la pila queda fuera de esta
corrección.

Evidencia de esta reconciliación: [registro](workflows/cg04-reconcile/runs/2026-10-21.md)
y [membresía por índices](evidence/CG04_split_membership.json). No acredita
evaluación independiente, ETA/RUL, operación industrial ni aceptación final.
