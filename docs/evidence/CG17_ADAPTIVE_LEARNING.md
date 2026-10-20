# CG17 — inicio del aprendizaje adaptativo y cambio de dataset

> Alcance retirado de la entrega por confirmación20Oct: usar solo AI4I reducido y
> clasificación del estado actual. Documento histórico; no activar pronóstico temporal
> ni sustituir el dataset. Véase [alcance vigente](CG17_CURRENT_STATE_SCOPE.md).

Estado histórico de primera fase. Las fases posteriores se implementan como laboratorio
en [CG17_ADAPTIVE_RUNTIME.md](CG17_ADAPTIVE_RUNTIME.md); validación física pendiente.
[Plan por fases](../superpowers/plans/2026-10-19-adaptive-maintenance.md).
No es Recursive Self-Improvement de código autónomo. Es la base de un ciclo medible
para aprender de nuevas observaciones, comparar candidatos y después decidir si
sustituir una versión. No se garantiza mejora continua ni se modifica la API activa.

## Qué funciona

`planning/adaptive.py` valida un manifiesto independiente del nombre de las columnas:
fuente, unidades declaradas, timestamp de observación, activo y ciclo de vida/componente.
Las declaraciones no acreditan por sí mismas autenticidad física; no se confía en ellas
para promover modelos. Falta cualquiera de los campos temporales y se rechaza el objetivo
sin fabricar datos. Una conversión de unidades requiere un adaptador explícito externo.

Por activo y ciclo, ordena cronológicamente y elimina duplicados exactos; si dos valores
contradicen el mismo instante rechaza el lote. A cada par: predice usando solo la última
observación y la pendiente aprendida hasta entonces; evalúa contra el valor siguiente;
solo entonces actualiza la pendiente con media exponencial. Referencia: último valor
observado. Compara exactamente los mismos pares tras warmup. Un hueco mayor al máximo
configurado reinicia el estado. No mezcla estado entre máquinas ni tras cambios de ciclo.

La predicción depende del horizonte solicitado (tiempo real entre observaciones), no
del valor futuro. Evaluación retrospectiva condicionada al siguiente instante observado:
no acredita un horizonte fijo5min ni anticipo de averías. No detecta por sí sola un
cambio de herramienta: el dataset debe declarar el nuevo ciclo. Cuenta estados repetidos
como diagnóstico; no certifica ausencia de replay. Todo permanece offline y sin promoción.

CLI: CSV+manifiesto → directorio nuevo con report.json y copia del manifiesto. Registra
hashes de bytes del CSV, manifiesto y evaluador, parámetros, predicciones emitidas,
observaciones, métricas por sensor/unidad y huecos por segmento. No sobrescribe salidas.
Un cambio de dataset exige nuevo dataset_id/manifiesto; no reutiliza estado previo.

## Reproducción y evidencia local

```sh
uv run --frozen python -m scripts.demo_adaptive --output outputs/adaptive-fixture-NUEVO
uv run --frozen python -m scripts.evaluate_adaptive \
  --data outputs/adaptive-fixture-NUEVO/observations.csv \
  --manifest contracts/examples/adaptive/manifest.json \
  --output outputs/adaptive-evaluation-NUEVO
uv run --frozen python -m unittest discover -s tests -p test_adaptive.py
```

Fixture sintético explícito:3series (tendencia constante, inversión, constante),120lecturas
por serie.351pares evaluados tras warmup: MAE de persistencia1.327635min frente a
0.045584min del estimador incremental. Es una prueba deliberadamente sencilla del
cálculo y adaptación, sin etiquetas de fallo ni pretensión de realismo. Alpha0.25 y
warmup2 son configuración experimental fija, no hiperparámetros optimizados.

El CSV AI4I actual, sin tiempo ni ciclo físico, se rechaza para esta evaluación. El
SMB replay no se emplea para demostrar degradación. No se toca el antiguo test reservado.

## Qué quedaba planificado tras primera fase

La implementación posterior y sus límites están en CG17_ADAPTIVE_RUNTIME.md.
El texto siguiente conserva el alcance de la primera entrega:

Registro de artefactos y estado de aprendizaje reanudable, selección champion/challenger,
comparación temporal por bloques y activos, incertidumbre y drift, aceptación futura
intacta y rollback. Después: pronóstico multivariable de márgenes físicos y propuesta
de intervención evaluada contra eventos verificados. Actualmente `promotion_allowed=false`
y `failure_eta_minutes=null` siempre. No hay entrenamiento programado, selección automática,
reanudación entre ejecuciones, despliegue ni aprendizaje del beneficio de mantenimiento.

Timestamp permite ordenar y medir duración; no determina por sí solo cuándo/cómo falla.
Para RUL o riesgo a horizonte hacen falta identidad y ciclo coherentes, eventos de inicio
de fallo y seguimiento/censura; para valorar intervenciones también acciones y resultados.
Con un dataset nuevo se comprobarán esos campos antes de fijar objetivos o prometer ETA.

Rúbrica: evidencia parcial de metodología reproducible, validación y evolución del sistema.
No implica revisión humana, aceptación docente, cierre de issue ni calificación.

Verificación:76 tests completos pasan,10 del evaluador adaptativo. Ruff check y
format pasan en los4 archivos nuevos. Revisión independiente de causalidad y
adaptador realizada; corregidos hash dependiente del cwd y cabeceras CSV duplicadas,
con regresiones. Esto es revisión técnica del agente, no aceptación humana de rúbrica.
