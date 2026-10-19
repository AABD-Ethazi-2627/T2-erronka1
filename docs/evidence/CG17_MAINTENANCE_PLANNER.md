# CG17 — calendario asistido ante la incompatibilidad AI4I/rúbrica

Implementado en `feat/17-maintenance-planner`, sobre PR41. Estado: evidencia local,
propuesta de laboratorio; revisión por otro miembro pendiente. No hay mantenimiento
físico autorizado, ETA validada, aceptación docente adicional ni calificación garantizada.

AI4I permite clasificar el estado de una muestra. El SMB actual repite estados UCI;
fechas añadidas y más filas no aportan tiempos reales hasta avería. La solución entrega
un **calendario de revisión basado en condición**: ayuda a priorizar el trabajo humano,
conservando la separación entre riesgo actual, anomalía y fecha de revisión.

## Política explícita y configurable

- CRITICA >=0.70: P1, revisión en30 minutos de reloj.
- AVISO >=0.15: P2, revisión en8 horas laborables.
- Solo anomalía: P3, revisión en16 horas laborables.
- OK: sin tarea automática. No sustituye revisiones preventivas del fabricante.

Son supuestos de laboratorio, no tiempos de fallo ni recomendaciones industriales.
Horario Europe/Madrid, lunes–viernes09–17, bloques30min y un revisor por defecto.
Capacidad y plazos configurables en `build_plan`. No se solapan recursos; un plazo
imposible queda marcado, incluso fuera del horario. H/M/L se conserva; no se
convierte H en riesgo alto fijo. Todos los activos actuales siguen sin identidad física
verificada: acción `REVIEW_DATA_AND_RISK`, ETA nula, criticidad temporal desconocida.

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

Ejecución19Oct:50 IDs puntuados por API,3 tareas (2P1,1P3),1plazo incumplido.
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

Verificación local:64 tests completos pasan,9 específicos del planificador. Ruff
check y format pasan sobre los4 archivos Python nuevos. La comprobación global
encuentra formato previo pendiente en8 archivos ajenos a este cambio; no se
reformatean en esta rama. La suite emite ResourceWarning de streams anyio en tests
existentes de API, sin fallos. Vista de resultado comprobada sin errores de consola.
