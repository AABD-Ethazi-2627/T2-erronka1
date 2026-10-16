# CG01 — Propuesta de alcance y acuerdo de equipo

**Borrador para debatir, 16 de octubre de 2026. No es un acuerdo aprobado.**
Issue: [CG01](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/1).

## Propuesta para presentar al equipo

Proponemos desarrollar CNC Guard como un laboratorio reproducible de detección de fallos y anomalías. Utilizaremos el training AI4I disponible para entrenar y evaluar, y los batches diarios del SMB como registros operativos de máquinas simuladas. Construiremos nuestra propia conservación de los datos, su procesamiento y un panel de consulta. El resultado inicial identificará el estado de fallo del registro actual. La predicción de una avería a 24 horas seguirá como hipótesis de ampliación, pendiente de datos longitudinales y eventos de avería adecuados.

El objetivo es mejorar la detección equilibrando falsos negativos y falsas alarmas. F1 y F2, junto con precisión, recall y matriz de confusión, permitirán justificar la elección. Acercarse a 1 es una aspiración, no una garantía ni un criterio que permita alterar etiquetas o reutilizar el test para ajustar el modelo.

## 1. Alcance propuesto

- Entrenar únicamente con `data/ai4i2020_train.csv`; separar entrenamiento, validación y test antes de ajustar modelos. Ajustar preparación, parámetros y umbrales dentro del proceso de entrenamiento/validación, conservando el test para la evaluación final.
- Recoger los CSV del SMB cuando el servidor esté disponible. Son registros operativos del laboratorio de origen simulado AI4I; no constituyen evidencia de funcionamiento en una fábrica.
- Inventariar y validar esquema, unidades, fechas, etiquetas y duplicados; conservar los originales y documentar registros rechazados y sus motivos.
- Mantener un histórico propio, con Bronze (original), Silver (validado) y Gold (resultados/agregaciones). NiFi ejecutará el flujo que implementemos: instalarlo no crea por sí solo estas capas ni una política de retención.
- Utilizar Random Forest para clasificación supervisada e integrar Isolation Forest como señal complementaria de anomalía. Una anomalía no equivale automáticamente a una avería; su señal no descartará por sí sola una alerta supervisada.
- Consultar histórico con Parquet/DuckDB y visualizar resultados operativos con Elasticsearch/Kibana.
- Entregar código, configuraciones, flujo de datos, informe de evaluación, instrucciones de reproducción y evidencias de una demostración completa.

No se conectará el prototipo a CNC físicos ni se automatizarán órdenes de parada. La demostración no acreditará anticipación de 24 horas ni eficacia industrial. Los tiempos reales de llegada del SMB se medirán; «tiempo real» no implica una latencia garantizada.

## 2. Tecnologías del curso y trazabilidad

Rutas relativas a la raíz del repositorio docente `bigdata`, situado fuera de este worktree. Páginas físicas del PDF, contadas desde 1. Esta tabla propone una selección; el curso no obliga a usar todas las tecnologías mencionadas en sus materiales.

| Función propuesta | Tecnología | Material docente comprobado |
|---|---|---|
| Ingesta y validación | Apache NiFi | `06_NiFi/materialak/01_01_ApacheNifi.pdf`, pp. 1–8 y casos de procesamiento de registros |
| Transporte de eventos | Apache Kafka y consumidores Python | `07_Kafka/materialak/01_03_ApacheKafka.pdf`, pp. 1–6 y apartados de productores/consumidores |
| Preparación y modelos | Python, pandas, scikit-learn; Random Forest | `05_BigData_Ingeniaritza/materialak/01_02_datuen_ingeniaritza.pdf`, p. 29; `03_ML_5072/materialak/5072_00_Sarrera.pdf`, apartado de herramientas; `03_ML_5072/materialak/5072_2_06_Random_Forest.pdf`, pp. 1–6 |
| Anomalías | Isolation Forest | `03_ML_5072/materialak/5072_00_Sarrera.pdf`, p. 15, tabla de algoritmos (numeración impresa 16/22) |
| Histórico y consulta | Parquet y DuckDB | `05_BigData_Ingeniaritza/materialak/01_02_datuen_ingeniaritza.pdf`, pp. 29–31 y 33–35 |
| Organización por capas | Bronze / Silver / Gold | `06_NiFi/materialak/Apache NiFi kasu praktikoak (5-6-7).pdf`, caso 7, p. 25 y siguientes |
| Consulta operativa y panel | Elasticsearch y Kibana | `05_BigData_Ingeniaritza/materialak/02_elastic_stack.pdf`, pp. 5–10 y apartados de consultas y visualización |
| Ejecución local de servicios | Docker Compose | `05_BigData_Ingeniaritza/materialak/02_elastic_stack.pdf`, práctica de p. 10 |

Recorrido propuesto para debatir: SMB → ingesta NiFi → Kafka → procesamiento Python → histórico Parquet/consulta DuckDB y resultados Elasticsearch → Kibana. El acceso concreto al SMB, la distribución de responsabilidades de archivo y las confirmaciones de consumo se concretarán en sus issues; este esquema no presupone un conector ya probado.

El patrón medallion se adapta del caso docente AEMET; no obliga a incorporar AEMET o MongoDB a CNC Guard. La retención de Kafka tampoco sustituye al histórico propio. No se añaden servicios o frameworks sin respaldo docente. FastAPI y Streamlit no forman parte de esta propuesta.

**Inconsistencia documental a resolver:** el README de planificación docente menciona una evolución con FastAPI, mientras que la tabla de selección de `soluzioak/Presentacion_Tecnologias/TRAZABILIDAD.md` lo excluye. Se ha utilizado el material docente original para esta propuesta; el equipo debe acordar el recorrido y actualizar la presentación/planificación después, sin tratar ninguno de esos snapshots como acuerdo humano vigente.

## 3. Criterios de aceptación propuestos

| Entrega | Evidencia para aceptarla |
|---|---|
| Fuentes y calidad | Inventario reproducible, procedencia, hashes, unidades, análisis de etiquetas/tiempo y límites de uso; revisión de CG02 |
| Ingesta | Un batch válido recorre el flujo; otro inválido queda identificado y conservado para revisión; relectura sin duplicar resultados según la clave acordada |
| Histórico | Original recuperable, dato validado y resultado trazables entre capas; consulta DuckDB sobre Parquet y prueba de relectura |
| Modelo supervisado | Separación de datos documentada, referencia de comparación, precisión/recall/F1/F2 y matriz de confusión; ningún identificador ni indicador derivado del fallo se usa como predictor sin justificar su disponibilidad y ausencia de fuga |
| Anomalías | Resultado de Isolation Forest distinguido del fallo supervisado y evaluación de su aportación y falsas alarmas |
| Panel | Resultados, calidad y frescura del dato visibles; interrupción del SMB distinguida de ausencia de fallos |
| Reproducción | Otro compañero ejecuta las instrucciones en el laboratorio y registra versión, comandos, resultado y limitaciones |

Antes de ajustar umbrales, el equipo debe acordar si F1 será el criterio principal y F2 el complementario o si prioriza F2 con una precisión mínima. El valor mínimo aceptable de precisión/recall y la política de falsas alarmas quedan **pendientes de acuerdo**, sin inventar costes industriales. Se publicarán también los recuentos de positivos y negativos. Los 40 registros de los snapshots de CG02 son negativos: por sí solos no permiten estimar recall ni F1/F2 para fallos.

Retención propuesta para discutir: 90 días de histórico y 30 días de índice operativo, sujeta a espacio disponible y mediciones de volumen. Son decisiones de diseño pendientes, no requisitos del curso ni servicios actualmente activos.

## 4. Objetivos y organización — ANEXO1

Fuente: `01_Erronka1_CNC_Guard/materialak/ANEXO1-Eus.md` (plantilla original también en DOCX).

Objetivos colectivos propuestos: aprender a trabajar en equipo, ayudarnos a comprender cada parte y entregar un laboratorio reproducible dentro del plazo. Revisar el trabajo de otro compañero antes de dar una tarea por aceptada y registrar acuerdos y desacuerdos.

| Rol de ANEXO1 | Responsabilidad de la plantilla | Persona |
|---|---|---|
| Coordinación | Moderar, seguir los pasos y fomentar la participación | Pendiente |
| Portavocía | Comunicar acuerdos y hablar con el profesorado | Pendiente |
| Secretaría | Redactar, conservar y organizar documentos y entregas; revisar el lenguaje | Pendiente |
| Apoyo 1 | Cuidar el tono de comunicación | Pendiente |
| Apoyo 2 | Controlar el tiempo | Pendiente |

Asignar o adaptar los roles al número real de integrantes con el equipo/tutor. Estos roles organizativos no sustituyen a los responsables técnicos por issue. No se asignan nombres ni se presuponen compromisos personales.

Cada persona rellenará su compromiso en ANEXO1: **nombre / compromiso concreto / forma de seguimiento / firma cuando corresponda**. Registrar periodo, nombre del equipo, grupo y tutor en la plantilla oficial. La secretaría conservará el acta y preparará la entrega cuando corresponda; este borrador no acredita subida a Classroom ni firma.

## 5. Calendario relativo de 11 semanas

Propuesta revisable al confirmar fecha de inicio y entrega con el profesorado; las fechas antiguas de las issues no prueban trabajo realizado.

| Semana | Resultado propuesto |
|---|---|
| 1 | Acordar CG01, roles y ANEXO1; revisar inventario CG02 |
| 2 | Contratos de datos, calidad y comportamiento ante indisponibilidad del SMB |
| 3 | Preparación reproducible y separación de datos para evaluación |
| 4 | Referencia supervisada y primera evaluación de Random Forest |
| 5 | Ajuste con validación, F1/F2 y análisis de errores; integración experimental de Isolation Forest |
| 6 | Histórico propio por capas, Parquet y consultas DuckDB |
| 7 | Integración NiFi/Kafka y pruebas de relectura e interrupciones |
| 8 | Integración de inferencia y publicación de resultados operativos |
| 9 | Panel Kibana, calidad y frescura de datos |
| 10 | Prueba de extremo a extremo y reproducción por otro compañero |
| 11 | Correcciones, memoria, demostración y retrospectiva/ANEXO1 |

Al aprobarlo, contrastar dependencias, disponibilidad y esfuerzo con las issues existentes; actualizar sus fechas y responsables en conjunto. El calendario no cierra ni reordena automáticamente el Project.

## 6. Acta mínima para convertir el borrador en acuerdo

- Fecha de reunión y participantes: **pendientes**.
- Objetivo y límites aceptados, cambios solicitados: **pendientes**.
- Arquitectura y tecnologías elegidas, con justificación: **pendientes**.
- Métrica principal y mínimos de aceptación: **pendientes**.
- Roles de ANEXO1, responsables técnicos y compromisos personales: **pendientes**.
- Inicio, entrega y revisión del calendario: **pendientes**.
- Política de retención y revisión de capacidad: **pendientes**.
- Persona que redacta el acta, revisión del equipo y enlace al ANEXO1: **pendientes**.

CG01 podrá marcarse resuelta cuando estos acuerdos estén registrados y revisados, el alcance quede limitado al laboratorio y el calendario de 11 semanas esté confirmado. Preparar un documento o abrir un PR no equivale a que el equipo lo haya aprobado.

## Referencias de estado

- [PR #33 / CG02](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/33): inventario y límites de la etiqueta, todavía sujeto a revisión. No es necesario mezclar su implementación con este borrador.
- Material docente: rutas de la tabla anterior, verificadas localmente el 16 de octubre de 2026. La presentación previa es contexto de planificación, no prueba de consenso del equipo.
