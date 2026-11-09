# Registro preparado de aclaraciones docentes — CG33/#82

Base del registro inicial: `5005ccde81f16cd2deac6ee3b30085d773e0fc88`.
Actualización documental del 23/10/2026 sobre el candidato local
`55cfd63d71c848acbd7647eab7b69bec768b646d`, más documentación final.
**Esta consulta no se ha enviado. El usuario ha aportado después dos posts
atribuidos al docente que aclaran parcialmente los puntos siguientes.** No es un
acta celebrada ni una respuesta individual a este registro. [Issue #82](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/82)
asigna portavoz a petiteiker y registro a Angiecrizu; tears-mysthrala/Niistal
aportan soporte técnico. Objetivo 27/10; seguimiento antes del 05/11.

La declaración inicial del usuario del 23/10/2026, «Aún no hay respuesta
docente», queda parcialmente superada por el material aportado después:
post de alcance del 21/10/2026, 14:51, y post de costes del 22/10/2026, 18:52,
ambos atribuidos a Aitor Aretxaga Agirre. Se usan las transcripciones del mensaje
del usuario, sin descarga ni verificación independiente de Moodle. El
[registro de fuentes y efectos](../evidence/DOCENTE_FORO_20261023.md) conserva
atribución, fechas indicadas, hashes y límites. No modifica las aceptaciones PM.

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
| A04 / G62 | Con el alcance tabular aclarado, ¿cómo se valorará el literal «histórico por máquina» de G62? ¿El ejemplo de cinco sensores excluye `machine_type` o admite las seis entradas actuales? | [Post de alcance, 21/10](../evidence/DOCENTE_FORO_20261023.md#alcance-tabular-y-discrepancia-de-entradas), [CG06](../evidence/CG06.md), [CG07](../evidence/CG07.md), [CV ampliada](../evidence/CG34_EXPLORACION_20261023.md): snapshots, desgaste como covariable y features físicas; groupby no crea historia causal | ACLARADO el alcance tabular / Aitor Aretxaga Agirre, atribuido / 21/10/2026, 14:51 / copia aportada por el usuario; PENDIENTES la valoración literal G62 y cinco sensores frente a `machine_type` | Sin timestamps en X, fechas inventadas, forecast, ETA/RUL o ventanas físicas de 24 h. Conservar bundle de cinco sensores + tipo y ledger idempotente; no cambiar modelo. tears-mysthrala prepara; petiteiker/Angiecrizu registran |
| A05 / G45, G61 | Con los costes fijados para el ejercicio, ¿cómo se valoran el recall de referencia y las políticas 0,15/0,70 ya aceptadas por PM? | [CG10 conciliado](../evidence/CG10_PRECISION_20261022.md), [decisión PM](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/10#issuecomment-6342069707), [economía del post](../evidence/DOCENTE_FORO_20261023.md#costes-del-ejercicio-y-lectura-marginal). Recall ≥76% es referencia literal; F1 perfecto no. CG34 ya incorpora la matriz facilitada | ACLARADA la justificación económica: FN→TP evita 4.700 €, frente a 200 € por TN→FP; equilibrio marginal 23,5 FP/TP / Aitor Aretxaga Agirre, atribuido / 22/10/2026, 18:52 / copia aportada. PENDIENTE la valoración académica específica de G45/G61 | No hay aprobación docente de un nuevo corte operativo. Conservar 0,15/0,70, clasificación contemporánea, límites CV, validación reutilizada y test antiguo excluido; no exigir otro test ni cambiar etiquetas. tears-mysthrala soporte; Angiecrizu registra |
| A06 / costes facilitados | Resuelto: ¿qué matriz usar para las curvas y la explicación económica del ejercicio? | [Post de costes y comprobación](../evidence/DOCENTE_FORO_20261023.md#costes-del-ejercicio-y-lectura-marginal): FN5.000€/FP200€/TP300€/TN0€, coincidentes con `business-costs.json` y `business-summary.json` de CG34; añadido posterior al preregistro, sin rehacer el estudio | RESUELTO como matriz oficial del ejercicio según la copia aportada / Aitor Aretxaga Agirre, atribuido / 22/10/2026, 18:52 / transcripción del mensaje del usuario | Usar estos parámetros sin pedir otra confirmación para ese uso. «Reales» es declaración del post, no auditoría financiera ni ahorro observado. Conservar escenarios previos de 1.200€/h y cronología. tears-mysthrala explica; Angiecrizu registra |
| A07 / #26, #27 | ¿Cuáles son los documentos/formato exigidos, canal, fecha/hora y duración de la defensa? | [Guía oral de seis páginas y captura del curso](../evidence/DOCENTE_FORO_20261023.md#entrega-y-presentación-oral): apoyan preparar la exposición, pero no fijan entrega final ni duración. El usuario dice «la entrega parece que será documentación y presentación en clase»: hipótesis. Objetivo 06/11 y ensayo 05/11; [guion](../demo/README.md), [ANEXO4 propuesto](../memoria/ANEXO4_CNC_Guard.md), [acta vacía](../demo/ACTA_PENDIENTE_20261022.md) | TENTATIVO documental/oral según el usuario y los materiales aportados; PENDIENTES los requisitos finales, canal, fecha/hora y duración / sin confirmación docente específica | Preparar documentación y presentación sin declarar modalidad final confirmada. Fechas objetivo por confirmar y justificante solo tras entregar. petiteiker confirma; Angiecrizu conserva recibo |

Para cada respuesta real, registrar: ID, pregunta, resumen fiel o cita breve,
persona/función, fecha, evidencia accesible y efecto sobre la matriz/paquete.
En los puntos sin respuesta, conservar PENDIENTE y explicar el límite en la defensa;
no volver a pedir de forma genérica lo que los posts ya aclaran.
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
- #27: congelar inventario de pendientes y paquete entregado, confirmar requisitos
  finales, canal, fecha/hora y duración de defensa; conservar el recibo después de
  la entrega efectiva. Objetivo 06/11 por confirmar; documentación y presentación
  en clase siguen siendo la hipótesis del usuario.

Estas condiciones no añaden otra revisión PM genérica a los cierres técnicos.
La evidencia conservada no acredita todavía esos tres actos humanos.
