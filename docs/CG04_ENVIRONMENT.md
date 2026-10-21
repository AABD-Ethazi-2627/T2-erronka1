# CG04 — entorno reproducible y contrato

Python integra pandas, scikit-learn y Pydantic tanto en entrenamiento como en
inferencia (G52). El Pipeline serializado evita repetir transformaciones en otro
lenguaje. La separación (G55) permite probar carga (`data`), validación (`schemas`),
selección (`features`) y entrenamiento (`train`) sin ejecutar la interfaz notebook.
El lock fija dependencias; Python 3.12 es la versión verificada.

Desde la raíz, sin PYTHONPATH ni instalaciones globales:

```bash
uv sync --frozen --python 3.12 --group notebook
uv lock --check
uv run --locked --group notebook python -m ipykernel install --prefix .venv --name cnc-guard --display-name 'CNC Guard (proyecto)'
uv run --locked --group notebook jupyter lab notebooks/02_training_TEMPLATE.ipynb
```

Seleccionar **CNC Guard (proyecto)**, cuyo kernelspec apunta al Python absoluto de
`.venv`. Registrarlo de nuevo al mover el checkout. Ejecución sin interfaz:

```bash
uv run --locked --group notebook jupyter nbconvert --to notebook --execute notebooks/02_training_TEMPLATE.ipynb --ExecutePreprocessor.kernel_name=cnc-guard --output cg04-executed.ipynb --output-dir .venv
```

Si `models/cnc_failure_model.pkl` existe, conservarlo y cambiar MODEL_PATH a una
ruta nueva. Solo usar overwrite=True tras decidir explícitamente sustituirlo.
La segunda ejecución predeterminada falla sin modificar el artefacto.

## Integración CG03 / CG28

SensorReading representa solo los seis predictores CG03: tipo H/M/L,
temperaturas Kelvin positivas, rpm/torque/desgaste no negativos y números finitos.
No acepta strings numéricos. Alineado con telemetry.schema.json de PR42
`28a77543bfd67a36b96ddc2f4acc103b13f62c2e`, consultado 2026-10-21.
prepare_inference_features acepta DataFrames sin target, conserva índice y orden,
y rechaza campos extra. Entrenamiento selecciona los sensores antes de validarlos
y separa un target binario. El Pipeline guarda la misma transformación para predict.

CG28 deberá validar primero el sobre CG03 (identidad, timestamp UTC, versión,
calidad y source), rechazar etiquetas/raw/temporales y proyectar los seis sensores.
No debe quitar etiquetas silenciosamente para aceptar un payload inválido.
Pydantic ValidationError, subclase de ValueError, identifica campo/motivo; HTTP
podrá traducirlo a 422. No se implementan aquí endpoints, lifespan, carga ni el
sobre completo. Clasificación de estado actual, sin ETA/RUL ni predicción temporal.
La accuracy es de desarrollo; no acredita evaluación final ni operación industrial.
