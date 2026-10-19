# CG17 — ciclo adaptativo completo de laboratorio

Estado: mecanismos de fases2–4 implementados y ensayados en laboratorio sintético.
Validación física y promoción operativa pendientes de un dataset adecuado. Complementa
[la primera fase](CG17_ADAPTIVE_LEARNING.md); no implica RSI de código que se reescribe.

## Componentes

- `planning/online.py`: predicción incremental por activo/ciclo, horizonte fijo solicitado,
  evaluación de pronósticos previamente emitidos, actualización posterior, diagnóstico
  de cambio de tasas. Snapshot JSON con checksum, identidad del manifiesto y hash del
  código: una modificación de implementación requiere migración/reentrenamiento explícito.
- `planning/selection.py`: partición cronológica global60/20/20 por instantes únicos.
  Selecciona alpha entre0.1/0.25/0.5 en validación temprana. Solo el elegido y la referencia
  vigente ven la aceptación posterior. Los parámetros quedan fijos; el estado incremental
  sigue actualizándose causalmente. No se evalúa una elección sobre todos los candidatos
  del periodo final. Un campeón registrado se restaura desde su estado real; no se refita
  silenciosamente. Sus observaciones deben ser posteriores al estado ya procesado.
- `planning/registry.py`: versiones inmutables por hash, puntero de evaluación paralelo,
  bloqueo entre procesos, comparación de versión esperada, promoción local y rollback
  auditados con actor/motivo/hora. La aceptación queda vinculada a la versión del campeón,
  su manifiesto, horizonte y configuración. Un candidato comparado solo con persistencia
  no puede reemplazar a un campeón. El registro es un mecanismo local para artefactos
  propios; no es firma de resultados ni frontera de autenticación para informes externos.
- `planning/cycle.py`: lotes reanudables, identidad/hash del lote, duplicado idempotente,
  rechazo de modificación de un lote anterior y orden temporal incorrecto. Admite continuar
  desde informe de entrenamiento, versión registrada o checkpoint sin perder alpha/horizonte.
- `planning/mechanisms.py`: adaptador explícito de márgenes del generador AI4I: potencia,
  disipación conjunta y sobreesfuerzo condicionado por L/M/H. No adapta por sí solo sensores
  de otro fabricante. No inventa tiempo/ciclo, y no convierte desgaste aleatorio en regla exacta.
- `scripts/adaptive_cycle.py`: train/update/propose/status/activate/rollback. `train` con un
  registro existente toma automáticamente el campeón correcto y rechaza mezclar datasets,
  unidades o horizontes. Activar afecta solo el registro local, nunca `/predict` ni equipos.
- `scripts/watch_adaptive.py`: consumo local de lotes preparados, por defecto una pasada;
  `--watch` habilita sondeo explícito. `.ready` aporta nombre CSV y SHA256, evitando leer
  archivos a medio publicar. Checkpoint y resultados usan escritura temporal+fsync+reemplazo
  atómico, bloqueo y recuperación idempotente. Un fallo conserva el último lote completado;
  una pasada de varios lotes no es una transacción única. No es certificación de integridad
  del sensor: verifica bytes/identidad del productor local. Rechaza fuentes modificadas y
  cambios de manifiesto. `--seed` permite arrancar desde el modelo seleccionado.

## Criterios de selección y límites estadísticos

Métrica MAE por sensor/unidad y mismo horizonte, con warmup. Cada sensor debe aportar
al menos20 pares de aceptación y mejora estricta en4 bloques temporales; se exige cobertura
por activo y se rechaza regresión media en cualquier activo. Se calcula un intervalo
bootstrap de medias de bloques (semilla42). Son controles experimentales conservadores,
no garantías de confianza ni sustitutos de un futuro conjunto de aceptación intacto.
No se suman directamente errores de distintas unidades: selección en validación normaliza
cada MAE por el de persistencia; aceptación aplica controles separados por sensor.

Una ejecución repetida sobre el mismo conjunto no crea un test independiente. Las
comparaciones/umbrales del algoritmo aún requieren verificación en nuevos periodos y
activos; el flujo no convierte el informe sintético en aceptación industrial. Los controles
reducen regresiones observadas; no garantizan que una nueva versión mejore en el futuro.

## Propuesta calculada por el modelo

El modelo aprende la tasa de cambio. Proyecta cruce de límites documentados; genera
escenarios con residuos históricos de tasas (cuantiles10/90) y proyección central. Esto
no es un intervalo de confianza calibrado ni un pronóstico multivariable probabilístico.
Los márgenes derivados permiten representar mecanismos conjuntos; se extrapolan sus
series, no se simula una distribución conjunta completa de sensores.

La ventana de revisión deriva del primer cruce entre los escenarios, sin plazos manuales
30min/8h/16h. La ventana es una propuesta de revisión antes del límite proyectado, no
una intervención óptima ni una fecha de avería aprendida de mantenimientos realizados.
Cruces más allá del horizonte evaluado se etiquetan como extrapolación adicional no
validada: la prueba de5min no acredita automáticamente una proyección de18min.
Escenarios sin cruce se marcan censurados; sin historia suficiente no se propone plazo.
La acción requiere revisión humana y comprobación de vigencia de datos. Un límite ya
rebasado se muestra como revisión de incumplimiento observado al instante de emisión.
`failure_eta_minutes` sigue nulo y `operationally_validated=false`.

Fuentes de los límites de ejemplo: [generador sintético AI4I/UCI](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset).
`contracts/examples/adaptive/ai4i-mechanisms.json` es plantilla, no evidencia física.

## Reproducir el ciclo completo

```sh
uv run --frozen python -m scripts.demo_adaptive_cycle \
  --output outputs/adaptive-complete-NUEVO
uv run --frozen python -m unittest discover -s tests -p test_adaptive_runtime.py
```

Demo determinista, explícitamente sintética:400lecturas de tendencia estable, después
400lecturas con aceleración y80 pares de aceptación a5min por fase. Primera elección
alpha0.1. Segunda elección alpha0.5 frente al campeón restaurado: MAE0.8 frente a2.4min
sobre el sensor ficticio. Activa ambas versiones en registro de laboratorio, prueba
rollback a la primera y continúa un estado de entrenamiento sin reiniciarlo.

El cruce del límite ficticio3500 desde el instante2026-01-02T06:40Z genera una ventana
hasta aproximadamente06:58Z, calculada por el modelo. Es salida de un fixture, no cita
real ni plazo aplicable a una CNC. Worker procesa2lotes y conserva checkpoint.
Salida observada: `outputs/adaptive-complete-2026-10-19-v3/summary.json`.

## Operación continua preparada, no activada como servicio

Ejemplo para una fuente temporal validada y lotes publicados atómicamente:

```sh
uv run --frozen python -m scripts.watch_adaptive \
  --inbox outputs/adaptive-inbox --manifest PATH_TO_MANIFEST \
  --work outputs/adaptive-worker \
  --seed PATH_TO_TRAINING_RESULT_JSON --watch --poll-seconds 30
```

No se ha instalado timer ni daemon. La prueba ejecuta una pasada acotada sobre fixtures.
El worker aprende nuevas observaciones; búsqueda de candidatos se invoca mediante `train`,
y activación/rollback mediante comandos explícitos, separados de la API. No hay agente
que cambie su propio código o que se promocione a equipos industriales. La vigencia de
checkpoints se verifica por hashes; no se modifica un modelo congelado ya publicado.

Antes de operar: nuevo dataset con identidad física/ciclo y tiempo de observación coherentes,
eventos/follow-up para validar averías y censura; límites del activo y costes de intervención.
Calibrar escenarios/errores al horizonte real y validar beneficio de mantenimiento por separado.
SMB replay y AI4I sin timestamp siguen sin habilitar ETA industrial. Sin nuevas etiquetas de
avería sí puede evaluarse pronóstico de sensores, no eficacia causal del mantenimiento.

## Verificación y revisión

94 tests completos pasan, incluidos18 del nuevo ciclo adaptativo. Ruff check/format
pasan sobre los11 archivos Python de planning y del nuevo flujo comprobados.
Demo CLI completa reproducida: entrenamiento de dos versiones, comparación con
campeón restaurado, activación local, rollback, continuación y propuesta, worker.

Dos revisiones técnicas independientes detectaron: incompatibilidad entre salida
de entrenamiento y continuación; publicación parcial de resultados/versiones; y
reemplazo sin evaluación contra el campeón. Se reprodujeron fallos, se corrigieron
y se añadieron regresiones de recuperación, versión y configuración. No es revisión
humana del tutor ni aceptación de rúbrica. La suite conserva ResourceWarning anyio
de tests API anteriores, sin fallos. Sin dependencias nuevas ni cambio de stack activo.
