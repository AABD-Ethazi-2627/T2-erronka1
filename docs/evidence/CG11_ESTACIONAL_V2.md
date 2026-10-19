# CG11 — dataset estacional sintético ampliado

Resultado: se generaron **245.376 filas horarias**, cuatro años de calendario
inventado y20 identidades SIM distintas (16 principales y4 de stress). No se añadieron filas a AI4I ni se modificó
su CSV, su test antiguo o su modelo de clasificación servido. El nuevo objetivo
es diferente: al menos un onset sintético en las próximas24h, no fallo actual.

La ampliación queda en `outputs/seasonal-v2/`, ignorada por Git. Código, parámetros,
semillas, métricas y hashes sí están versionados. Bundle local:
`outputs/seasonal-v2/dataset_bundle.zip` (Parquet por partición + manifiesto + aviso).
No contiene credenciales, datos SMB, pickles ni datos de operadores.

## Datos y supuestos

| Partición | Año | Máquinas | Filas | Onsets simulados | Ventanas positivas24h |
|---|---|---:|---:|---:|---:|
| train | 2022–2023 | 8 | 140160 | 229 | 5407 |
| validation | 2024 | 4 | 35136 | 60 | 1383 |
| evaluation | 2025 | 4 | 35040 | 55 | 1320 |
| stress | 2025 alternativo | 4 | 35040 | 119 | 2712 |

El conjunto principal (sin stress) contiene210.336 filas; stress aporta35.040
adicionales para sensibilidad. Train conserva139.968 filas etiquetadas tras
censurar24h finales por máquina. Seeds42/43/44/45 y cohortes disjuntas. Evaluación
2025 tiene55 onsets, no1.320 fallos independientes: son ventanas24h solapadas.

Patrón supuesto de interior industrial del hemisferio norte: anual±6K con máximo
hacia día205, diario±1,2K, tiempo autocorrelacionado, heterogeneidad de máquina y
carga semanal/diaria. La exposición de desgaste supuesta es2,5 minutos de corte
por hora ponderados por carga; no describe un ciclo CNC observado. Se inventan
riesgos estocásticos de calor/cooling, desgaste y arranque relativamente frío,
además de fallo aleatorio. Reparación inmediata y reemplazo preventivo entre
240–320min son políticas hipotéticas. No se atribuyen estas tasas al tutor, a
UCI ni a una fábrica. No se usaron meteorología real o historiales de mantenimiento.

AI4I aporta exclusivamente mediana de temperatura ambiente y torque calculadas
con sus5600 filas originales de train. Las señales/escala se contrastaron con
[fuente primaria UCI AI4I](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset).
Su descripción de sensores no acredita nuestras reglas temporales o tasas.

## Entrenamiento y comprobaciones

Se entrenaron13 candidatos prefijados: HistGradientBoosting con solo sensores,
con historial pasado y con historial+calendario cíclico, para cohortes anidadas de
1/2/4/8 máquinas; además RF con todas las features/8 máquinas. La duración de cada
cohorte es idéntica (dos años completos), conservando las cuatro estaciones.
Más máquinas cambian volumen y diversidad: no es un experimento causal puro de N.

Rolling24h/168h usa shift1 dentro de cada máquina. No entran IDs, onsets, etiquetas,
daño latente ni seed en predictores. Calendario usa seno/coseno anual, horario y
semanal; no códigos ordinales de estación. Imputación se ajusta solo en train.
Últimas24h censuradas; horizontes de train/validación no cruzan fronteras. Modelo
de tamaño completo elegido por AP de validación y umbral por F2 de validación,
con manifest persistido antes de predecir evaluación. Los13 puntos de la curva
se reportan completos sobre evaluación sintética fija; no se reelige ganador
mirando2025 ni se reajusta después con stress.

[JSON completo y hashes](CG11_seasonal_v2.json) · [Gráfico](CG11_seasonal_v2.png).

## Resultado que realmente se obtuvo

Seleccionado por validación: `history_8machines`. Evaluación2025: AP=0.0719, precisión=6.60%, recall=69.77%, Brier=0.0362.

**La precisión es insuficiente para tratarlo como un sistema de avisos útil.**
No se oculta tras accuracy o recall de eventos. Detecta51/55 onsets con una señal
previa, pero marca como alerta13.955 de34.944 horas (39,94%). Esa carga de avisos
impide presentar92,73% de detección de eventos como un éxito operativo aislado.
La anticipación mediana de24h tampoco demuestra aviso específico: alertar a menudo
facilita cubrir cualquier ventana. FP/FN por hora no son órdenes de mantenimiento.

| Variante HGB | Máquinas train | Filas train etiquetadas | AP en2025 sintético |
|---|---:|---:|---:|
| sensors | 1 | 17496 | 0.0631 |
| history | 1 | 17496 | 0.0625 |
| seasonal | 1 | 17496 | 0.0598 |
| sensors | 2 | 34992 | 0.0639 |
| history | 2 | 34992 | 0.0601 |
| seasonal | 2 | 34992 | 0.0595 |
| sensors | 4 | 69984 | 0.0783 |
| history | 4 | 69984 | 0.0617 |
| seasonal | 4 | 69984 | 0.0756 |
| sensors | 8 | 139968 | 0.0760 |
| history | 8 | 139968 | 0.0719 |
| seasonal | 8 | 139968 | 0.0622 |

Con solo sensores, pasar de1 a8 máquinas mejora AP0,0631→0,0760 en este ensayo,
pero4 máquinas obtuvo0,0783: **no hay mejora monótona**. Añadir calendario a8
máquinas dio AP0,0622, peor que sensores y que historial. La estación ya afecta
las temperaturas observadas; añadir el nombre/fecha de estación no garantiza
información nueva ni compensa la aleatoriedad del generador.

Métricas del modelo seleccionado por estación (ventanas horarias, no onsets):

| Estación | Positivos / filas | AP | Precisión | Recall |
|---|---:|---:|---:|---:|
| winter | 240 / 8544 | 0.0622 | 4.68% | 44.58% |
| spring | 216 / 8832 | 0.0423 | 4.89% | 75.00% |
| summer | 595 / 8832 | 0.0959 | 9.12% | 75.13% |
| autumn | 269 / 8736 | 0.0673 | 5.93% | 76.21% |

Stress modifica ambiente+3K y cooling−1,5K, con otro seed y nuevas máquinas.
AP no se compara aisladamente con el ensayo principal: hay119 onsets frente a55
y cambia la prevalencia. No se usa para ajustar el modelo. No se reduce ese
ensayo a una afirmación de robustez industrial ni se suman sus filas al train.

## Reproducir sin sobrescribir resultados

```bash
uv sync --frozen --python 3.11
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --frozen python -m scripts.train_seasonal_v2
uv run --frozen python -m scripts.report_seasonal_v2
uv run --frozen python -m scripts.package_seasonal_v2
uv run --frozen python -m unittest discover -s tests -v
```

El trainer rechaza outputs existentes; usar --output con una versión nueva.
El reporter y empaquetador aceptan --root para revisar otra versión.
El bundle existente solo se reutiliza si todos sus bytes y hashes coinciden. Datos están en Parquet, con source_kind=synthetic_seasonal_v2 en
cada fila; el manifiesto del bundle declara finalidad y semillas. Modelos locales
son propios con SHA y recarga idéntica, no pickles de terceros.

Pruebas cubren horizonte excluyendo el instante actual, censura, causalidad del
histórico, repetibilidad, verano más cálido, identidades entre semillas, exclusión
de etiquetas/daño/IDs del modelo y auditoría por onset frente a ventanas repetidas.
El calendario futuro y las series son inventados: un seed distinto comprueba
consistencia del simulador, no independencia de reglas ni validez en fábrica.

**Decisión:** entregar el dataset y la demo de investigación, conservar RF actual
en la API y no prometer mayor precisión real. Para un forecast estacional útil
hacen falta señales previas informativas, política de mantenimiento/costes y
series fechadas de fallos observados. Aumentar frecuencia puede repetir información;
el sampler no crea evidencia de mecanismos que no se han medido.
