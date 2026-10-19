# CG17 — calendario asistido ante la incompatibilidad AI4I/rúbrica

Implementado en `feat/17-maintenance-planner`, sobre PR41. Estado: evidencia local,
propuesta de laboratorio; revisión por otro miembro pendiente. No hay mantenimiento
físico autorizado, ETA validada, aceptación docente adicional ni calificación garantizada.

AI4I permite clasificar el estado de una muestra. El SMB actual repite estados UCI;
fechas añadidas y más filas no aportan tiempos reales hasta avería. La solución entrega
un **calendario de revisión basado en condición**: ayuda a priorizar el trabajo humano,
conservando la separación entre riesgo actual, anomalía y fecha de revisión.

## Corrección: el modelo no aprendió plazos de mantenimiento

El usuario rechazó correctamente los plazos predeterminados30min/8h/16h: eran
reglas introducidas por el implementador y no una recomendación aprendida. Se
retiran del comportamiento por defecto. `review_due_at=null` y
`review_deadline_missed=null` indican que no hay plazo estimado. Opcionalmente un
operador puede aportar un SLA explícito; se identifica como EXPLICIT_OPERATOR_POLICY.

Las alertas de riesgo se ordenan por score descendente del modelo, incluso dentro
del mismo nivel. Anomalías sin alerta de riesgo se mantienen después como cola
separada: no se confunde su score con probabilidad de fallo. Los niveles de alerta
siguen el contrato docente0.15/0.70; no son umbrales aprendidos de mantenimiento.
Los huecos propuestos son asignación de recursos, **no fechas de mantenimiento
predichas**. Horario de laboratorio Europe/Madrid, lunes–viernes09–17,
capacidad1 y bloques30min son parámetros operativos explícitos, no aprendidos.
H/M/L influye a través del modelo ya entrenado y se conserva como contexto.

**Objetivo del usuario pendiente:** que un modelo aprenda qué mantenimiento proponer
y cuándo. El conjunto actual no etiqueta decisiones de mantenimiento, sus resultados
ni tiempos físicos hasta avería. No se entrenará un modelo con plazos inventados
para presentarlo como evidencia real. La simulación temporal separada permite
investigar hipótesis, con evaluación limitada al simulador, no validar este objetivo.

Agrupa por ID, conserva IDs de eventos y la mayor prioridad del lote. Repeticiones
no cuentan como confirmaciones independientes. Advierte antigüedad, tipos incompatibles
y predicciones distintas con igual timestamp. Rechaza IDs de evento contradictorios,
fechas futuras, tiempos sin zona y scores inválidos. Es un plan de un lote: no una
cola persistente ni reconciliación automática entre ejecuciones. El historial de
approve/reject/complete devuelve una copia auditable con actor, motivo y hora;
su persistencia e identidad autenticada quedan pendientes de integración de aplicación.

## Reproducción y resultado observado

```sh
uv run --frozen python -m unittest discover -s tests
uv run --frozen python -m scripts.demo_maintenance \
  --snapshot outputs/smb-eta-2026-10-19 \
  --output outputs/maintenance-demo-NUEVO
uv run --frozen python -m scripts.plan_maintenance \
  --predictions outputs/maintenance-demo-NUEVO/predictions.json \
  --as-of 2026-10-19T10:21:55Z --output outputs/calendar-NUEVO
```

La demo requiere API local en127.0.0.1:18001 con artefactos confiables existentes.
No envía targets al modelo ni escribe en SMB/Kafka. Selecciona una última fila por
ID (timestamp, fichero, número de fila): es una vista de muestra, **no resolución de
los conflictos del snapshot** documentados en CG02. as_of pertenece al replay.

Ejecución inicial19Oct:50 IDs puntuados por API,3 tareas (2P1,1P3). El plazo
incumplido informado entonces pertenecía a la política manual retirada, no al modelo.
CNC-030/M y CNC-042/L producen P1; CNC-004/H produce anomalía P3. No implica una
comparación causal entre tipos. Exporta JSON,CSV e ICS tentativo sin asistentes ni
envío a calendarios. Todas las tareas siguen PROPOSED; ningún test acredita revisión
humana real. Salida local `outputs/maintenance-demo-2026-10-19/` fuera de inputsFilebeat.

## Trazabilidad y límite para evaluación

CG17/G5/G61/G104: política, agrupación y revisión humana explícita; evidencia parcial.
G14/G41/G65/G72/G105: calendario exportable y trazabilidad aportan evidencia auxiliar;
no sustituyen los demás entregables ni sus criterios completos. No marcar como10.

Para cubrir una exigencia estricta de predicción temporal real sigue faltando historia
física etiquetada. Propuesta defendible al tutor: evaluar por separado clasificación
AI4I, simulación temporal estacional y planificación asistida. El sistema puede después
aceptar un modelo temporal validado; hoy no transforma simulación en precisión real.

Verificación tras corrección:66 tests completos pasan,11 específicos del planificador. Ruff
check y format pasan sobre los4 archivos Python nuevos. La comprobación global
encuentra formato previo pendiente en8 archivos ajenos a este cambio; no se
reformatean en esta rama. La suite emite ResourceWarning de streams anyio en tests
existentes de API, sin fallos. Vista de resultado comprobada sin errores de consola.
