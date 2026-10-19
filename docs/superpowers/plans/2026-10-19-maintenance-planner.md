# CG17 — planificador de mantenimiento asistido, sin ETA ficticia

Autorización: usuario solicita hacer viable el calendario ante incoherencia entre
AI4I y rúbrica. Rama feat/17-maintenance-planner, base84dfb7c. No merge/producción,
no escritura SMB ni calendarios externos. La fuente actual es replay UCI y sus
IDs no acreditan activos físicos: la demo genera tareas de revisión de señales y
calidad; no órdenes de reparación automáticas.

Capas: predicción actual existente → política configurable → cola deduplicada →
calendario propuesto de revisiones con capacidad limitada → aprobación humana.
H/M/L llega al modelo y se conserva como contexto; no se convierte en probabilidad
fija ni se usa H=alto riesgo. SLA de revisión no es tiempo hasta fallo. ETA=null.

Política inicial local: CRITICA/P1 revisar en30min, AVISO/P2 en8h laborables,
anomalía/P3 en16h laborables, estado OK sin tarea automática. Conflictos, fuente
replay, identidad no verificada o dato obsoleto cambian acción a revisar datos;
no borran un riesgo alto. Estas duraciones son supuestos configurables para
planificar trabajo humano, no recomendaciones del fabricante ni garantías.

Calendario: Europe/Madrid, lunes–viernes09–17, revisiones30min, un recurso lógico,
capacidad configurable. P1 primero; no solapar recursos; marcar incumplimiento
si la capacidad/horario impide el plazo. Jamás retrasar deadline para fingir éxito.
Una propuesta por activo/tipo de tarea, conservandoevent_ids y escaladas. No
contar emisiones repetidas como confirmación independiente. Registro de acciones
approve/reject/complete con hora, actor de laboratorio y motivo, sin envío externo.
ExportJSON/CSV/ICS marcados DRAFT y vista HTML estática; ICS no es invitación enviada.

Entrada validada y límites de NaN/tiempos/identidad; tests de umbrales, conflictos,
deduplicación, independencia H/M/L, fin de semana/DST, capacidad, escalada y revisión.
Demostración con últimas lecturas de snapshot SMB actual y HTTP API real validado;
replay enas_of explícito, sin afirmar mantenimiento observado o ahorro real.
Trazar rúbrica G5/G14/G41/G61/G65/G72/G104/G105 como parcial, revisión humana pendiente.

## Rectificación solicitada por el usuario

El usuario quiere recomendaciones aprendidas, no plazos elegidos por el agente.
Se retiran los SLA por defecto y se ordena por score del modelo; fechas de recurso
no se presentan como mantenimiento predicho. El objetivo de aprender cuándo y qué
mantener queda pendiente: no existen etiquetas de mantenimiento/tiempo restante
real. No usar fechas generadas para ocultar esta ausencia.
