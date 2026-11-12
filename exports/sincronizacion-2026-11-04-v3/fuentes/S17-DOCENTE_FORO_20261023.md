# Material docente aportado el 23/10/2026: alcance, costes y defensa

Actualización documental sobre `55cfd63d71c848acbd7647eab7b69bec768b646d`
en `review/pending-20261023`, más documentación final del checkout compartido.
El registro inicial de [CG33](../rubrica/ACLARACIONES_20261023.md) y la
[matriz de 40 criterios](../rubrica/ESTADO_20261023.md) conservan como base
histórica `5005ccde81f16cd2deac6ee3b30085d773e0fc88`.

## Procedencia y cronología

El usuario aportó los cuerpos de dos posts atribuidos a **Aitor Aretxaga Agirre**.
Se inspeccionaron las transcripciones locales de su mensaje; no son descargas de
Moodle ni una comprobación independiente de autoría, publicación o cuentas
empresariales. Las horas siguientes son las indicadas en el material, sin zona
horaria acreditada. La declaración anterior del usuario, «Aún no hay respuesta
docente», queda parcialmente superada por este aporte posterior; no implica que
se haya enviado la consulta CG33 o recibido una respuesta individual a ella.

| Fuente aportada | Fecha indicada | Copia local y SHA-256 |
|---|---|---|
| Post sobre ausencia de timestamp y clasificación tabular | 21/10/2026, 14:51 | [forum-tabular.txt](../../outputs/academic-inputs-20261023/forum-tabular.txt), `262414f2008a4c0a9c5d8cb9c2b234b31ff3b347c58b68a2bcc2b1ed6a80ff23` |
| Post «Negozio-Kostuen Matrizea eta Atalase Optimoa» | 22/10/2026, 18:52 | [forum-costs.txt](../../outputs/academic-inputs-20261023/forum-costs.txt), `f292e1ff07785552ace80eaefaf0b7b2fd25ecfcb94aa45886c73affdbbaca32` |

Estos hashes identifican las transcripciones conservadas, no autentican un
servidor Moodle. No se observó sospecha de inyección de instrucciones en los
textos inspeccionados; su contenido se trata como evidencia del ejercicio y no
autoriza operar cuentas, servicios o sistemas externos.

## Costes del ejercicio y lectura marginal

El post de costes presenta esta tabla como **oficial para el ejercicio**. Esa
copia aportada basta para usar sus parámetros en la explicación; no se mantiene
una confirmación independiente como requisito previo para ese uso.

| Resultado | Coste fijado | Explicación atribuida al post |
|---|---:|---|
| FN | 5.000 € | Avería no detectada: tres horas a 1.200 €/h, más reparación urgente y piezas |
| FP | 200 € | Inspección innecesaria y breve parada; parámetro medio facilitado |
| TP | 300 € | Mantenimiento preventivo y coste de piezas |
| TN | 0 € | Funcionamiento sin incidencia |

El post llama «reales» a estos datos financieros y operativos de ARAKAIN
Makineria. Se registra esa declaración de la fuente; no se ha auditado su
contabilidad ni demostrado ahorro industrial. El resultado económico calculado
con la matriz es hipotético y depende de que las acciones tengan los costes y
efectos indicados.

Los cuatro importes coinciden con
[business-costs.json](CG34_20261023/business-costs.json) y con `config.cost_eur` de
[business-summary.json](CG34_20261023/business-summary.json). La configuración
registra su origen y su incorporación **posterior al preregistro y a los
resultados originales**; el
[informe CG34](CG34_EXPLORACION_20261023.md) ya conserva ese añadido. No se rehace
el estudio ni se recalculan sus 1.801 matrices. Los escenarios anteriores de
1.200 €/h se conservan con su fecha; no se sustituyen retrospectivamente.

Para una cohorte fija, el coste es `5.000·FN + 200·FP + 300·TP + 0·TN`.
Recuperar un FN como TP reduce el coste en `5.000 − 300 = 4.700 €`; convertir un
TN en FP añade `200 − 0 = 200 €`. Si al bajar un umbral aumentan TP y FP,
el cambio reduce el coste cuando `4.700·ΔTP > 200·ΔFP`. Para `ΔTP > 0`, el
equilibrio marginal es **23,5 FP adicionales por cada TP adicional**. El cociente
`5.000/200 = 25` citado por el post compara los costes brutos; la decisión
marginal incluye los 300 € del TP. Los campos marginales de `business-summary`
ya contienen 4.700, 200 y 23,5, comprobados en esta revisión.

Bajo el supuesto de una probabilidad `p` **calibrada para la población de uso**
y de dos acciones con los efectos y costes exactos de esta tabla, alertar tiene
coste esperado `300·p + 200·(1−p)`, y no alertar, `5.000·p`.
La igualdad da `p = 200/(4.700+200) = 0,0408163265…`.
Es un umbral teórico condicionado a calibración y a que la intervención evite
la pérdida según la matriz. No demuestra que los scores actuales cumplan esos
supuestos ni constituye un corte operativo aprobado. Se conservan las políticas
**0,15/0,70**, las etiquetas y la aceptación PM de su justificación.

El post respalda explicar y graficar el compromiso económico; menciona una
valoración adicional si se incorpora al notebook de fase 2 y a la presentación.
Se conserva como criterio expresado en la copia, sin atribuir una nota obtenida
ni acreditar una inserción o defensa humana ya realizadas. A05 queda aclarada
en su parte económica; sigue pendiente la valoración académica específica de
G45/G61 y sus políticas existentes. **A06 queda resuelta como parámetro del
ejercicio.**

## Alcance tabular y discrepancia de entradas

El post del 21/10 aclara que el ejercicio trata **clasificación tabular de
snapshots**, con variables físicas del estado actual. No exige convertir el
dataset en una serie temporal ni añadir timestamps a X. `tool_wear_min`
representa desgaste/exposición acumulada como covariable de la fila: por sí sola
no aporta una trayectoria ordenada, identidad física fiable ni historial causal
por máquina. Se mantienen clasificación contemporánea, límites de CV y
validación reutilizada, y las 1.200 filas del test antiguo inspeccionado
**excluidas**; el post no convierte esos resultados en test final independiente.

Las features propuestas por la fuente son coherentes con estudiar relaciones
físicas: diferencia de temperaturas y producto `rpm * torque_Nm`. Este último
es un **proxy de potencia**. Con rpm y N·m, la conversión a vatios requiere
`P_W = (2·π/60)·rpm·torque_Nm`; el producto sin ese factor no se etiqueta como W.
La explicación del post sobre el riesgo de usar fechas se registra en este
contexto, sin afirmar que todo timestamp cause fuga en cualquier problema.

El ejemplo del post selecciona solo cinco sensores:
`air_temp_K`, `process_temp_K`, `rpm`, `torque_Nm`, `tool_wear_min`.
La preparación activa documentada en [CG07](CG07.md) y el paquete de CG34 usan
**cinco sensores más `machine_type`**. Queda una pregunta concreta en A04:
**¿El ejemplo de cinco sensores excluye `machine_type` como entrada, o admite
las seis entradas actuales?** No se elimina la feature ni se cambia bundle,
entorno o modelo para resolver esa discrepancia por inferencia.

La inferencia por fila descrita como *stateless* se refiere a que el scoring no
necesita una secuencia de lecturas. Es compatible con conservar el
[ledger idempotente](../SCORING_REPLAY_CONTRACT.md) para identidad, respuestas y
replay; el post no obliga a borrarlo. Tampoco acredita una nueva medición de
latencia del grafo. El alcance tabular queda aclarado, mientras la **valoración
literal de «histórico por máquina» de G62** continúa sin respuesta específica.
No se inventan fechas, forecast, ETA/RUL o ventanas físicas de 24 horas.

## Entrega y presentación oral

El PDF aportado, de seis páginas, es una guía de comunicación oral en euskera
de Normalkuntza taldea, Uni Eibar-Ermua, curso 2026–2027. La copia local
[oral_guide.pdf](../../outputs/academic-inputs-20261023/oral_guide.pdf) tiene
SHA-256 `ab3782ac487f4f3b7b9c0349bbf87e0aa4a638fe5344956b914b053ec6072318`;
su procedencia consta en el [recibo](../../outputs/academic-inputs-20261023/receipt.json).
Original aportado:
`C:/Users/unaiu/.t3/userdata/attachments/2b3d281e-e5ca-4618-99d1-43bcad6bc49d-95e18226-cd53-4140-8ca0-82675db208b3-pdf.pdf`.
Se inspeccionó la [extracción completa](../../outputs/academic-inputs-20261023/oral-guide.txt).
La guía orienta estructura, diapositivas como apoyo, expresión oral, ensayo y
gestión del tiempo; no fija duración total ni condiciones de entrega del reto.

La [captura del curso](../../outputs/academic-inputs-20261023/course_screen.png),
SHA-256 `d2411f79f4d9a485f4d44cff4ba00c426046340c295aa4af11837b929dda6250`,
muestra el recurso de guía oral y entregas anteriores: contrato del 10/09 y
propuestas del 13/10 y 14/10. No acredita fecha/hora, canal de entrega final ni
duración de defensa.

El usuario dice «la entrega parece que será documentación y presentación en
clase». **Es una hipótesis de modalidad**, apoyada parcialmente por los
materiales de presentación, no confirmación de los requisitos finales. A07
mantiene pendientes documentos/formato exigidos, canal, fecha/hora y duración.
Ensayo 05/11 y entrega objetivo 06/11 son planificación por confirmar. Tampoco
se acreditan todavía explicaciones personales de 4/4 integrantes, acta de ensayo,
defensa celebrada ni recibo de entrega.

## Efecto sobre el cierre y comprobaciones

- **A01/A02:** vigencia de la rúbrica, pesos y evaluación individual/transversal
  siguen sin respuesta. Los posts y la guía no alteran `fuente.json`.
- **A03:** G49/SMB y reparto NiFi/worker siguen sin valoración docente específica;
  se conservan las aceptaciones PM existentes y sus límites.
- **A04:** resuelto el alcance tabular; pendientes valoración literal G62 y
  cinco sensores frente a `machine_type`.
- **A05/A06:** economía y matriz del ejercicio aclaradas; no hay nuevo corte
  operativo aprobado ni aceptación académica específica de G45/G61.
- **A07:** preparación documental/oral tentativa; requisitos finales y actos
  humanos pendientes.

Comprobaciones documentales ejecutadas en esta actualización: **40 filas** con
sus objetivos, referencias E y aceptaciones P conservados; **121 enlaces/anchors
locales** válidos; cuatro costes coincidentes en ambos JSON y aritmética
`4.700/200 = 23,5`, con umbral teórico condicionado `0,040816…`.
`py -3 -B -m scripts.check_cg25_memory` pasó: **40 criterios, 90 enlaces/anchors,
191 hashes actuales y 18 históricos**. Fuente literal, cuatro cortes sellados y
manifiesto CG25 permanecen intactos. Las 41 referencias externas de estos tres
documentos se conservan sin nueva consulta de red. Los scripts, logs y recibos
quedan en `D:/github/_local/t2-review-20261023/academic-input/`, en particular
`reviewer-checks.py`, `reviewer-checks.json` y `reviewer-cg25.log`.
No se repiten entrenamiento, inferencia o matrices del estudio, ni se modifican
las 191 entradas del manifiesto, sus hashes históricos o las aceptaciones PM.
La actualización local no acredita CI nueva, publicación, entrega ni aprobación
académica global.
