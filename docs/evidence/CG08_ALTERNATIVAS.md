# CG08 — alternativas al RF y complementariedad de anomalías

Experimento de desarrollo del 19/10/2026. No sustituye el modelo servido ni
convierte AI4I en predicción a 24h. Código y resultados permiten cuestionar la
elección RF+IF sin presuponer que una librería más compleja ganará.

## Diseño y reproducción

19 configuraciones individuales: dummy, logística con física, RF original,
RF más profundo, RF calibrado por sigmoid dentro del entrenamiento, ExtraTrees
(2), HistGradientBoosting (4), GradientBoosting clásico (2), CatBoost (3), SVM
RBF (2), BalancedRandomForest. Dos reglas de mezcla equiponderada: RF + mejor
candidato fuera de rf_* y los tres individuos con mayor AP. Los miembros se
eligen dentro del entrenamiento de cada evaluación, no mirando validación.

Fuente y particiones originales: 5600 train (190 positivos), 1200 validación
reutilizada (41 positivos), 1200 test antiguo excluido. La primera etapa replica
exactamente los cuatro folds originales y el AP RF 0,9089647747455067.
La segunda reconstruye selección de candidato, miembros y umbral dentro de cada
outer-train: 3 outer ×3 inner. Cada una de las 5600 filas se evalúa una vez como
outer-held. Umbral F2 se calcula solo con scores OOF inner. No se comparte
preprocesamiento ajustado entre folds. CSV se lee con float_precision=round_trip
para no desplazar decisiones justo en el umbral por redondeo del parser.

CatBoost utiliza la misma codificación one-hot de H/M/L que los demás; esta
búsqueda no explota su tratamiento categórico nativo. Presupuestos pequeños y
no iguales en tiempo: no prueba superioridad universal ni agota cada familia.
No se ajusta XGBoost/LightGBM ni redes neuronales en este ensayo.

```bash
uv sync --frozen --python 3.11 --group research
# Prerrequisito: outputs/cg08/report.json original (scripts.experiment_rf).
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --frozen --group research python -m scripts.experiment_alternatives
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --frozen --group research python -m scripts.experiment_alternatives_nested
uv run --frozen --group research python -m scripts.report_alternatives
uv run --frozen --group research python -m unittest discover -s tests -v
```

Los experimentos rechazan sobrescritura. Outputs/ conserva scores por fila,
modelos propios y manifiestos completos de folds; el JSON compacto versionado
contiene sus hashes. Report_alternatives regenera el JSON/gráfico, verifica
particiones y reproduce exactamente métricas de validación antes de exportar.
CatBoost1.2.10 está en grupo research y no se añade a requisitos de la API.
El primer ensayo nested-v1 conservado localmente permitía rf_deep como challenger;
la evidencia final usa nested-v2 con la misma exclusión rf_* de la búsqueda amplia.
No se presenta aquel ensayo previo como la evaluación de la regla corregida.

## Resultados

Resultados completos: [JSON](CG08_alternatives.json) y [gráfico](CG08_alternatives.png).

Búsqueda amplia OOF: RF AP0,908965; GradientBoosting depth3 AP0,913894;
mezcla top3 AP0,916005. La mejora de AP de la mezcla no implica dominar en errores.

Auditoría nested final: 190 positivos evaluados entre las 5600 filas train.
Umbrales F2 determinados dentro de cada outer-train, no con outer-held.

| Procedimiento | AP outer | Fallos detectados /190 | Fallos omitidos | Falsas alarmas |
|---|---:|---:|---:|---:|
| RF referencia | 0.905673 | 164 | 26 | 25 |
| GradientBoosting depth3 | 0.909436 | 160 | 30 | 8 |
| RF + challenger elegido dentro de cada outer-train | 0.913239 | 163 | 27 | 19 |
| Mezcla top3 elegidos dentro de cada outer-train | 0.911855 | 163 | 27 | 23 |
| Selección completa por AP inner | 0.911520 | 163 | 27 | 22 |

Con FP100€/FN1200€ y estos puntos F2 nested: RF cuesta33.700€ hipotéticos;
GradientBoosting36.800€; RF+challenger34.300€. Con FP300€/FN600€,
GradientBoosting pasa a20.400€ frente a23.100€ de RF. Son aritmética de escenarios
sobre recuentos de desarrollo, no ahorro observado ni umbrales optimizados por coste.

En la validación reutilizada con umbrales nuevos elegidos en OOF: RF30TP/11FN/8FP;
GradientBoosting31TP/10FN/4FP; top3 igual31TP/10FN/4FP. Aplicando umbrales de coste
FP100€/FN1200€ aprendidos en OOF: RF32TP/9FN/11FP y RF+GradientBoosting32TP/9FN/10FP.
Una falsa alarma de diferencia en41 positivos no acredita superioridad definitiva.

Latencia warm en proceso, 30 filas secuenciales; excluye HTTP y no mide carga:

| Modelo | p50 ms | p95 ms | Artefactos bytes |
|---|---:|---:|---:|
| RF | 7.55 | 9.83 | 1128056 |
| GradientBoosting | 4.11 | 5.23 | 358203 |
| Mezcla top3 | 18.17 | 24.01 | 2954686 |

Anomalías: IF detecta1/41 fallos y16FP; LOF20 detecta16/41 y8FP;
LOF50 detecta17/41 y12FP. Ninguno recupera fallos omitidos por la mezcla elegida.
Sus avisos adicionales son16/8/11 falsas alarmas respectivamente. No equivalen
a calidad de detección de anomalías sin verdad etiquetada de anomalía.


## Qué implica para la decisión

AP mide ordenación de casos, no define por sí sola la política de mantenimiento.
Un modelo puede ganar AP y perder recall en el punto de operación elegido.
La calibración, umbral, coste de inspección y coste de omitir un fallo deben
considerarse por separado. Los niveles docentes .15/.70 no se trasladan sin más
a los scores de otro modelo ni sustituyen un umbral de decisión validado.

Las nueve combinaciones de coste FP=25/100/300 € y FN=600/1200/4800 € son escenarios,
no costes observados. Para cada modelo se minimiza coste empírico OOF train y se
aplica ese umbral a la validación reutilizada. Esta parte NO es nested y NO se usa
para declarar vencedor final. No se ajusta umbral sobre validación para mejorar
la nueva comparación. La cifra histórica RF 32/41 y9FP procede de un umbral
previamente ajustado en esa validación; se conserva como referencia histórica,
no como estimación nueva comparable al procedimiento nested.

Isolation Forest y LOF20/50 se ajustan solo con train etiquetado normal. Sus
umbrales usan cuantil .99 de scores normales OOF train, nunca validación.
Failure=0 es proxy, no garantía de normalidad; no hay verdad etiquetada de anomalías.
LOF supera a IF en detectar etiquetas de fallo en este ensayo, pero no aporta
fallos adicionales a la mezcla supervisada elegida. No unir automáticamente
sus avisos al aviso de fallo; mantenerlos como canal exploratorio separado.

**Recomendación:** conservar RF en la API mientras se revisa el coste de errores.
GradientBoosting clásico es el challenger individual más prometedor por AP,
precisión y tamaño; la mezcla mejora algo el ranking, con más coste de inferencia
y sin dominar a RF en fallos omitidos. El 10 debe defender la comparación y sus
límites, no declarar ganador por una centésima o por tener más modelos.

## Límites y revisión

Los outer-held evitan fuga dentro del procedimiento nested, pero el proyecto ya
ha explorado este dataset; no hay test final nuevo e independiente. Bootstrap
pareado sobre scores OOF es descriptivo y no prueba significación entre algoritmos
tras selección. Una fuente sintética, una semilla y pocos positivos no garantizan
rendimiento industrial, por temporada ni fuera de distribución. Ningún score
implica una probabilidad industrial calibrada. Se requieren datos nuevos y
revisión humana antes de promoción; no se cierra issue ni se atribuye nota.

Referencias primarias consultadas: [ensembles scikit-learn](https://scikit-learn.org/stable/modules/ensemble.html),
[CatBoost tuning](https://catboost.ai/docs/en/concepts/parameter-tuning),
[anomalías/novelty](https://scikit-learn.org/stable/modules/outlier_detection.html).
Las versiones ejecutadas son las de uv.lock; la documentación stable puede ser
posterior y no reemplaza verificar compatibilidad con sklearn1.5.0.
