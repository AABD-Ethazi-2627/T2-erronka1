# Aplicación de la guía oral a la defensa de CNC Guard

Preparación documental del 23/10/2026 para `AABD-Ethazi-2627/T2-erronka1`, rama `review/pending-20261023`. HEAD contrastado: `55cfd63d71c848acbd7647eab7b69bec768b646d`, con documentación final adicional en el checkout compartido.

El resultado es un [guion editable en euskera](DEFENTSA_GIDOIA_20261023.md), con cuatro ideas principales y relevos propuestos para cuatro integrantes. Separa el apoyo visual de las notas del orador e incluye respuestas a preguntas previsibles. Es un outline Markdown: no se ha creado un PPTX, realizado un ensayo ni obtenido validación humana del euskera.

## Fuentes académicas y procedencia

**Guía PDF aportada por el usuario:** *Ahozko komunikaziorako euskarazko gida*, portada atribuida a Normalkuntza taldea, Uni Eibar-Ermua, curso 2026-2027. Tiene seis páginas físicas, correspondientes a la paginación 0-5; la portada corresponde al 0, sin numeral visible. SHA256: `ab3782ac487f4f3b7b9c0349bbf87e0aa4a638fe5344956b914b053ec6072318`.

La copia preservada se identifica como `outputs/academic-inputs-20261023/oral_guide.pdf`; la extracción completa está en `outputs/academic-inputs-20261023/oral-guide.txt` y los renders son `guide-page-01.png` a `guide-page-06.png` en ese mismo directorio. Se ha leído la extracción entera e inspeccionado visualmente las seis páginas. Se consigna su procedencia y hash sin enlazar a la ruta externa del adjunto. Estos materiales locales aportados no acreditan una descarga ni autenticación en Moodle.

**Captura del curso aportada por el usuario:** `outputs/academic-inputs-20261023/course_screen.png`, SHA256 `d2411f79f4d9a485f4d44cff4ba00c426046340c295aa4af11837b929dda6250`. La imagen muestra el recurso de guía oral y entregas anteriores: contrato del 10/09/2026 y propuestas del 13/10/2026 y 14/10/2026. Sus fechas y horas pertenecen a esas entregas. La captura no confirma fecha, hora, canal final ni duración de la defensa.

**Posts transcritos desde el mensaje del usuario, atribuidos a Aitor Aretxaga Agirre:**

- Costes, fecha indicada 22/10/2026 a las 18:52: `outputs/academic-inputs-20261023/forum-costs.txt`, SHA256 `f292e1ff07785552ace80eaefaf0b7b2fd25ecfcb94aa45886c73affdbbaca32`.
- Alcance tabular, fecha indicada 21/10/2026 a las 14:51: `outputs/academic-inputs-20261023/forum-tabular.txt`, SHA256 `262414f2008a4c0a9c5d8cb9c2b234b31ff3b347c58b68a2bcc2b1ed6a80ff23`.

Son cuerpos aportados por el usuario, no una descarga de Moodle ni una comprobación independiente de autoría o de contabilidad industrial. No se ha identificado sospecha de inyección de instrucciones en el material inspeccionado. Su contenido se usa como fuente académica; no autoriza operaciones sobre cuentas o servicios.

## Aplicación de las seis páginas

1. **Página física 1 / paginación 0, portada:** identifica título, equipo, centro y curso de la guía. Se conserva esa atribución como procedencia; no se deducen de ella condiciones de entrega.
2. **Página física 2 / impresa 1, organización y recursos:** recomienda introducción, desarrollo y cierre, con un máximo de tres o cuatro ideas principales. El guion contiene exactamente cuatro: alcance actual, evaluación, medición y costes. La introducción va en el primer bloque y el cierre en el cuarto. Se aplica la recomendación de diapositivas ligeras y letra grande separando texto de pantalla y notas. Las indicaciones de voz, pausas, mirada y ensayo se traducen en recordatorios por bloque y una lista de comprobación. La observación sobre la importancia de los primeros dos minutos no fija la duración total de la defensa.
3. **Página física 3 / impresa 2, introducción y transiciones:** el guion abre con saludo, pregunta concreta, objetivo y recorrido. Cada relevo anuncia el tema siguiente y a la persona propuesta, sin inventar nombres ni participación ya realizada.
4. **Página física 4 / impresa 3, ejemplos, gráficos y cierre:** se incorpora un ejemplo aritmético de costes, una explicación de los ejes y unidades de la curva existente, y un cierre con las cuatro ideas y turno de preguntas. Se evita convertir una frase persuasiva en evidencia: el gráfico se presenta con su alcance OOF train y la falta de evaluación final independiente.
5. **Página física 5 / impresa 4, atribuciones y opiniones:** se atribuyen los posts a su autor indicado y se separan parámetros académicos, observaciones guardadas e hipótesis. Las opiniones o expectativas no sustituyen mediciones; las respuestas incluyen fórmulas para reconocer lo que falta por comprobar.
6. **Página física 6 / impresa 5, debate y acuerdo:** se prepara un turno de preguntas con respuestas breves y límites explícitos. El reparto entre cuatro integrantes se propone para el ensayo; deberá acordarlo el grupo. No se presenta como reparto ejecutado ni como participación evaluada.

## Qué cambia con los posts y qué sigue pendiente

Los posts aportan respuestas concretas sobre **costes y alcance tabular**. Por tanto, no se mantiene la afirmación genérica de que no existe respuesta docente sobre esos dos asuntos. La atribución y las fechas siguen siendo las indicadas en la transcripción del usuario.

La matriz FN 5.000 €, FP 200 €, TP 300 € y TN 0 € coincide con [business-costs.json](../evidence/CG34_20261023/business-costs.json) y con `config.cost_eur` de [business-summary.json](../evidence/CG34_20261023/business-summary.json). El cálculo de cuatro celdas es `C = 5000·FN + 200·FP + 300·TP + 0·TN`. Las [curvas Python existentes](../evidence/CG34_20261023/business-cost-curves.png) y las [tablas del añadido económico](../evidence/CG34_20261023/business-tables.md) ya están disponibles: no se rehace el estudio.

El ejemplo del guion usa el valor marginal `5000 - 300 = 4700 €` y el equilibrio `4700 / 200 = 23,5` FP adicionales por cada FN convertido en TP, manteniendo lo demás constante. Ambos valores están en el resumen económico. Es aritmética del escenario, sin afirmar causalidad, ahorro observado ni una regla universal de operación. El post menciona una valoración académica favorable del análisis; no acredita una nota u honor concedidos.

El post de alcance encuadra el trabajo como clasificación de snapshots. El guion mantiene `tool_wear_min` como covariable de desgaste y evita describirla como historial temporal. `timestamp` queda fuera de X; su uso como metadato no contradice ese alcance. La inferencia por fila es compatible con el [ledger idempotente de respuestas](../SCORING_REPLAY_CONTRACT.md); no obliga a borrarlo. Se precisa que `rpm * torque_Nm` es un proxy: para potencia en W se requiere el factor `2π/60`. Estas precisiones no añaden features ni cambian el código.

Quedan delimitadas estas incertidumbres:

- **`machine_type`:** el ejemplo de X del post solo enumera cinco sensores, mientras que el [contrato de entradas del bundle CG26](../evidence/CG26_REHEARSAL_2026-10-21.json) incluye esos cinco más `machine_type`. Falta aclarar la admisibilidad de la variable adicional. No se elimina la feature ni se modifica el bundle.
- **Entrega:** «documentación y presentación en clase» es una hipótesis comunicada por el usuario. No hay confirmación de formato final, fecha, hora, canal ni duración oficial. Los 10 minutos del [README de demo](README.md) sirven de orientación ajustable para ensayar. La guía PDF no impone esa duración y el tiempo de preguntas también queda por confirmar.
- **Validación humana:** el guion y los relevos están preparados, pero no ensayados ni revisados por una persona competente en euskera. No se acredita aprobación docente, aceptación del grupo o entrega realizada.

## Cifras y límites trasladados al guion

- **Identidad:** [CG26](../evidence/CG26_REHEARSAL_2026-10-21.json), [modelo CG32](../evidence/CG32_ORIGINAL_MODEL_20261023.json), [piloto CG32](../evidence/CG32_ORIGINAL_PILOT_20261023.json) y [Discover CG32](../evidence/CG32_ORIGINAL_DISCOVER_20261023.json) comparten el manifiesto `a6cc7a29f0b061e114e046865cf7ac4a3969111a904a0281f1919aff35ea0945`. El bundle RF+IF sirve clasificación contemporánea; no acciona máquinas ni acredita ETA/RUL o forecast. CG26 declara el score servido sin calibrar; IF mide rareza, no confirma una avería futura.
- **Modelo en proceso:** `n = 600`, 20 llamadas previas de calentamiento excluidas; `p95 = 11.07344300544355 ms`, presentado como **11,073 ms**. Mide `predict_proba(RF)+score_samples(IF)` sobre una fila, no HTTP ni E2E.
- **Piloto privado existente:** 10 ofrecidos, 10 guardados, 10 documentos ES y offset confirmado 10; cero pérdidas válidas y cero IDs duplicados en la conciliación de ese piloto. HTTP p95 `60.320475000480656 ms`, presentado como **60,320 ms**. E2E p95 `55748.093946000154 ms`, convertido a **55,748 s**. El objetivo de ingeniería propuesto de 1 s **no se cumple**. Diez eventos no prueban SLA, capacidad general o aceptación operativa.
- **Discover:** el JSON registra un documento observado con el mismo `event_id` que el evento seleccionado del piloto. Se cita ese registro; no se afirma haber reabierto ahora el servicio ni disponer de una captura PNG exportada de Discover.
- **CG34:** 5.600 filas de train / 190 positivos en los scores outer de CV. El añadido de costes reutiliza scores existentes; `fixed_specification_refit_performed=false` y `operational_change=false`. Los umbrales del selector se aprenden en inner. El test antiguo permanece excluido; ni la validación reutilizada ni las curvas de ajuste OOF train se presentan como test final independiente. El [protocolo sellado](../evidence/CG34_20261023/manifest.json) y la [revisión CG34](../evidence/CG34_REVIEW_20261023.md) conservan los límites del estudio.

Esta preparación contrasta documentos y JSON existentes. No vuelve a ejecutar tests técnicos, modelos, inferencia, entrenamiento, redes OT/SMB o servicios.

## Lista para el ensayo: pendiente de ejecución

Todas las casillas quedan abiertas para que el grupo registre lo que realmente haga.

- [ ] Acordar los cuatro nombres, bloques y relevos; completar la ficha del guion.
- [ ] Confirmar con el docente formato, fecha, hora, canal final y duración, incluido el turno de preguntas.
- [ ] Resolver la discrepancia concreta sobre `machine_type` sin alterar unilateralmente el bundle.
- [ ] Revisar el euskera con una persona competente y anotar correcciones, sin atribuirle una revisión antes de hacerla.
- [ ] Preparar apoyos con letra grande, contraste legible y solo las frases breves indicadas; mantener las notas fuera de pantalla.
- [ ] Mostrar el gráfico existente a tamaño legible y comprobar que se leen título, ejes, leyenda, €/1.000 eventos y límite OOF train; ampliar el apoyo si al proyectarlo no se lee, sin cambiar datos.
- [ ] Explicar en voz alta las diferencias entre score, rareza y probabilidad calibrada, y entre ms del modelo y s de E2E.
- [ ] Ensayar saludos, pausas, mirada al público y los tres relevos; medir cada bloque con reloj.
- [ ] Ajustar la extensión al tiempo confirmado; si falta tiempo, reducir ejemplos, conservando alcance y límites.
- [ ] Practicar las preguntas sobre test independiente, `machine_type`, ledger, pérdidas, costes y ausencia de ahorro real.
- [ ] Registrar fecha, asistentes, duración real y cambios; no sustituir un ensayo pendiente por una casilla marcada sin evidencia.

## Verificación de esta preparación

Se contrastaron los hashes de los materiales aportados, las cifras citadas con los JSON y los destinos de los enlaces relativos de ambos documentos. La evidencia de verificación y la comparación de preservación se guardan fuera del repositorio, en `D:/github/_local/t2-review-20261023/oral-preparation`.

La propiedad de esta tarea se limita a este documento y al guion enlazado. No se actualizan README sellados, actas, manifiestos CG25 ni modelos; no se realiza commit, push, PR, merge, comentario o cierre. La preparación documental no cierra las limitaciones técnicas o las decisiones docentes indicadas arriba.
