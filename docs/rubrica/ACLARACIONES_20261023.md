# Registro preparado de aclaraciones docentes — CG33/#82

Base: `5005ccde81f16cd2deac6ee3b30085d773e0fc88`. Preparado por el agente revisor
el 23/10/2026. **No se ha enviado esta consulta ni se ha recibido una respuesta
docente en esta revisión.** No es un acta celebrada. [Issue #82](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/82)
asigna portavoz a petiteiker y registro a Angiecrizu; tears-mysthrala/Niistal
aportan soporte técnico. Objetivo 27/10; seguimiento antes del 05/11.

El usuario confirmó en esta conversación, el 23/10/2026: «Aún no hay respuesta
docente». Es información aportada por el usuario; no equivale a una respuesta
del docente ni modifica las aceptaciones PM existentes.

La [matriz actual](ESTADO_20261023.md) y el
[feedback de objetivos del PM](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/27#issuecomment-6359282684)
conservan las decisiones existentes. Este registro permite anotar una respuesta
o un pendiente explícito; no exige obtener una aprobación ficticia para documentar
la consulta ni reabre las issues técnicas ya aceptadas.

| ID / criterio | Pregunta preparada | Evidencia y alternativa que se presentan | Respuesta docente / quién / fecha / fuente | Efecto actual y responsable |
|---|---|---|---|---|
| A01 / versión | ¿Sigue vigente la copia del Excel cuyo SHA-256 es `e3e05d6fe408e163f6f8247cd7054f2a4ce4de6aa5757048ba432cd682139463`? | [Extracción exacta](fuente.json), hoja Zereginak, 40 descriptores G; sin confirmar versión online | PENDIENTE / no consta / no consta / no consta | Conservar fuente exacta y su incertidumbre; petiteiker consulta, Angiecrizu registra |
| A02 / pesos y modalidad | ¿Cómo interpretar H5 `15%%`, IAS sin pesos visibles y evaluación individual/transversal? | [Objetivos originales](OBJETIVOS_Y_ETAPAS.md#decisiones-y-dudas-que-debe-resolver-el-equipo-con-el-tutor); no sumar módulos ni inventar nota | PENDIENTE / no consta / no consta / no consta | No completar pesos ni modalidad por inferencia; petiteiker/Angiecrizu |
| A03 / G49, G92 | ¿Cómo se valora académicamente la equivalencia SMB y el reparto NiFi/worker ya aceptados por PM? | [P36 SMB](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/36#issuecomment-6342088143), [P14 worker](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/14#issuecomment-6342057992), [mismo evento](../evidence/CG20_SAME_EVENT_20261022.md). NFS/InvokeHTTP nativos no se declaran ejecutados | PENDIENTE / no consta / no consta / no consta | Mantener aceptación PM; no rehacer el grafo ni exigir NFS automáticamente. petiteiker canaliza; Niistal apoya |
| A04 / G62 | ¿Cómo acreditar histórico por máquina sin tiempo/identidad física fiables? | [CG06](../evidence/CG06.md), [CG07](../evidence/CG07.md), [CV ampliada](../evidence/CG34_EXPLORACION_20261023.md): EDA, features físicas, ablación/CV y agregación descriptiva de emisiones; groupby no crea historia causal | PENDIENTE / no consta / no consta / no consta | Explicar el límite; sin fechas inventadas, forecast, ETA/RUL o ventanas físicas de 24 h. tears-mysthrala prepara; petiteiker/Angiecrizu registran |
| A05 / G45, G61 | ¿Cómo se acredita el compromiso recall/costes manteniendo 0,15/0,70 y el alcance contemporáneo? | [CG10 conciliado](../evidence/CG10_PRECISION_20261022.md), [decisión PM](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/10#issuecomment-6342069707). Recall ≥76% es referencia literal; F1 perfecto no. Paradoja explicada y aceptada PM; no consulta docente acreditada | PENDIENTE / no consta / no consta / no consta | Conservar políticas, validación reutilizada y test antiguo excluido; no exigir otro test ni cambiar etiquetas. tears-mysthrala soporte; Angiecrizu registra |
| A06 / costes facilitados | ¿Se mantiene para la explicación la matriz FN5.000€/FP200€/TP300€/TN0€ aportada por el usuario y atribuida al docente? | [Informe y atribución exacta](../evidence/CG34_EXPLORACION_20261023.md): dato aportado por el usuario, posterior al preregistro; no respuesta obtenida por este agente. Convive con escenarios de 1.200€/h, sin sustituirlos retrospectivamente | PENDIENTE de confirmación directa / no consta / no consta / texto del usuario ya atribuido en informe | Separar origen, cronología y coste hipotético; no usarlo como prueba de ahorro industrial. tears-mysthrala prepara; Angiecrizu registra |
| A07 / #26, #27 | ¿Cuál es el canal, formato, fecha/hora y modalidad de entrega/defensa? | Objetivo de planificación 06/11, ensayo 05/11. [Guion](../demo/README.md), [ANEXO4 propuesto](../memoria/ANEXO4_CNC_Guard.md), [acta vacía](../demo/ACTA_PENDIENTE_20261022.md) | PENDIENTE / no consta / no consta / no consta | Fecha/hora/canal reales y justificante siguen pendientes. petiteiker confirma; Angiecrizu conserva recibo solo tras entregar |

Para cada respuesta real, registrar: ID, pregunta, resumen fiel o cita breve,
persona/función, fecha, evidencia accesible y efecto sobre la matriz/paquete.
Si no hay respuesta, conservar PENDIENTE y explicar el límite en la defensa.
No insertar firmas, asistencia, respuestas o aceptación por otra persona.

## Paquete y evidencia humana todavía pendientes

La preparación local permite comprobar el SHA/árbol final, manifiesto CG25,
matriz, memoria, ANEXO1/4, guion, exports y respaldo offline identificado. La
[revisión por issue](../evidence/PENDING_REQUIREMENTS_20261023.md) enumera el
trabajo restante y las fechas objetivo. Preparar el paquete no demuestra entrega.

- #37: cuatro explicaciones reales con palabras propias, entrada/salida/error/límite
  y una pregunta fuera de la especialidad de cada integrante; primera ronda 28/10.
- #26: ensayo objetivo 05/11 del caso válido hasta panel, rechazo, replay y errores
  409/422/503 según guion; participante/fecha/versión/resultado reales en acta posterior.
- #27: congelar inventario de pendientes y paquete entregado, confirmar canal/hora
  y conservar el recibo después de la entrega efectiva; objetivo 06/11 por confirmar.

Estas condiciones no añaden otra revisión PM genérica a los cierres técnicos.
La evidencia conservada no acredita todavía esos tres actos humanos.
