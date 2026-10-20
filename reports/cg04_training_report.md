# CG04 — Informe de reproducibilidad

## Configuración del entrenamiento
- Modelo: RandomForestClassifier
- Número de estimadores: 200
- Semilla aleatoria: 42
- División de evaluación: 80 % entrenamiento / 20 % prueba
- Ponderación de clases: balanced

## Versiones
- Python: 3.12
- NumPy: 2.2.6
- pandas: 2.2.2
- scikit-learn: 1.5.0
- joblib: 1.4.2

## Artefacto local
- Archivo: `models/cnc_failure_model.pkl`
- SHA-256: `0F60AAC60D0A150766F70E153458D427977F3DF424E798A90B298BBFF8F58349`

El modelo se conserva localmente y no se versiona en Git. El hash permite identificar el artefacto exacto.

## Validación
- Pruebas automatizadas: 14 pasadas.
- Resultado de desarrollo; no constituye una evaluación independiente final del modelo.
