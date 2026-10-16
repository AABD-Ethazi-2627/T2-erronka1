# CG01 — Objetivos y etapas para aspirar al nivel avanzado (10)

Propuesta revisada el 16/10/2026. No acredita cumplimiento ni garantiza nota. Fuente primaria: `Erronka1_ikaslearen_errubrika.xlsx`, hoja `Zereginak`, columna G, cabecera `G3 = AURRERATUA (10)`. Se ha leído el Excel original local, no solo la presentación o la matriz técnica anterior. [Extracción trazable y SHA-256](CG01_rubrica_fuente.json): 40 descriptores avanzados no vacíos, con criterio, celda y peso tal como está almacenado. No se redistribuye la lista personal del enunciado.

La copia está en Downloads; el enlace oficial figura en `01_Erronka1_CNC_Guard/materialak/MOODLE_URLs.md`. No se ha podido verificar la versión online: confirmar con el tutor que esta copia es la vigente antes de cerrar el acuerdo.

## Qué significa aspirar al 10

El nivel 10 describe profundidad de justificación, implementación y pruebas en cada criterio; no fija F1=1. Exige interpretar errores, demostrar el flujo completo y relacionar los resultados con decisiones de mantenimiento. Los criterios IAS no tienen pesos visibles, pero sí descriptores: se incluyen en el plan. No se suman porcentajes de asignaturas distintas para inventar una nota global.

Objetivo general propuesto: construir y justificar un laboratorio CNC Guard con aprendizaje offline e inferencia online, integración automática, conservación propia, panel operativo y pruebas de calidad, recuperación y rendimiento; demostrar qué decisiones permite tomar y qué afirmaciones no respaldan los datos. La decisión final de mantenimiento será humana y trazable. Se explicará el bucle de observación → inferencia → aviso → revisión → acción/seguimiento y sus niveles de autonomía, sin accionar equipos físicos.

## Matriz completa: exigencia avanzada → objetivo → evidencia → etapa

Las referencias son celdas de `Zereginak`; las filas agrupadas conservan sus referencias individuales. Las evidencias son objetivos propuestos, todavía no resultados.

| Celdas G | Objetivo derivado del nivel 10 | Evidencia revisable | Etapa |
|---|---|---|---|
| 5 | Distinguir aprendizaje offline, inferencia online, bucle de control y autonomía | Diagrama y decisiones humanas/automáticas explicadas, con límites del laboratorio | E1/E8 |
| 10 | Comparar familias supervisadas y de anomalías: RF/Gradient Boosting e IF/Autoencoder | Comparación argumentada de ventajas y uso en CNC; no implica desplegar los cuatro modelos | E3 |
| 14 | Cuantificar costes de fallo/mantenimiento, ajustar umbrales por riesgo y probar scoring online | Escenarios de coste, elección de umbral y medición de latencia/carga | E3/E6 |
| 16 | Analizar clasificación AI Act, CE, responsabilidades y vigilancia laboral | Informe de aplicabilidad con fuentes oficiales vigentes y finalidad declarada; no presumir certificación | E1/E8 |
| 17,19,20 | Integrar privacidad y seguridad en todo el diseño | Matriz por componente: datos, acceso, secretos, exposición, conservación y prueba de controles; impedir cruces con rendimiento personal | E1–E8 |
| 23,24 | Explicar IA específica frente a general y reglas frente a ML | Sección conceptual aplicada a decisiones reales de CNC Guard, límites y ventajas | E1/E8 |
| 31,32 | Justificar tipos de aprendizaje y ecosistema completo de herramientas | Relación datos/etiquetas/técnicas, preparación, desbalance, serialización y servicio | E2/E3 |
| 36 | EDA profunda y preparación de variables | Distribuciones, faltantes, unidades, clases, anomalías y decisiones reproducibles | E2 |
| 38 | Feature engineering físico e interpretación, evitando fugas | `temp_diff`, `power_est` con unidades/fórmula; importancia de variables; SMOTE exclusivamente dentro del entrenamiento de cada partición si se usa | E3 |
| 39 | Interpretar recall, precisión y matriz de confusión | Recuentos TP/FP/FN/TN y discusión de casos; F1/F2 complementan lo exigido | E3 |
| 41 | API robusta, carga única al arrancar, validación y errores, alertas e integración NiFi | Arranque real, entradas válidas/inválidas, fallos y recorrido NiFi→API | E4/E5 |
| 45 | Justificar recall prioritario (descriptor cita 76%+), costes FP/FN y adecuación | Recall medido sobre test reservado con soporte de positivos; comparar coste de parada 1.200 €/h con inspección innecesaria | E3/E7 |
| 46 | Validar desacoplamiento, transferencia, latencia y fiabilidad integral | Recuentos reconciliados y latencias desde entrada hasta alerta; fallos inducidos y recuperación | E6 |
| 49 | Automatizar archivos→Filebeat→Kafka→NiFi→modelo→Elasticsearch | Ejecución sin intervención por registro, documentos/KPI verificables; confirmar adaptación SMB al NFS del descriptor | E5/E6 |
| 52,55 | Justificar Python y estructurar código modular, Pydantic, excepciones y separación train/API | Arquitectura de módulos, contratos tipados, revisión y pruebas de errores | E3/E4 |
| 60 | Definir modelo frente al desbalance, SMOTE/pesos y ajuste de umbral; justificar métricas | Experimentos comparables sin fuga, comparación con referencia, recall/ROC-AUC y trampa de accuracy | E3 |
| 61 | FastAPI `/health`, `/predict`, serialización, umbrales y rendimiento | Casos frontera: <0,15 OK; ≥0,15 AVISO; ≥0,7 CRITICA; pruebas reales y explicación de la «paradoja de parada programada» | E4/E6 |
| 62 | Mejorar con variables, histórico por máquina, CV, fine tuning y evaluación interpretada | Comparación antes/después y validación cruzada adecuada; histórico solo si la identidad/orden son fiables, sin futuro ni etiquetas como predictor | E3 |
| 65,66 | Combinar telemetría e inferencia en información operativa coherente | Esquema versionado y documentos con sensores, máquina, fecha, probabilidad, alerta y versión de modelo | E2/E5 |
| 68 | Crear índices e ingest pipelines correctos | Export de mappings/pipelines y consultas que comprueban tipos y documentos reales | E5 |
| 71,72 | Elegir y justificar visualizaciones y su relación con mantenimiento | Series, comparación de máquinas, KPI/alertas; comprobar intervalos, agregaciones y filtros | E7 |
| 77 | Extracción/almacenamiento robustos con integridad y disponibilidad | Original recuperable, trazabilidad hasta alerta y consultas por máquina/tiempo | E5/E6 |
| 80 | Probar carga y justificar seguridad y recursos | Volumen/tasa, CPU/RAM/colas, latencia, errores; mejoras y controles de accesos/puertos/credenciales | E6 |
| 85 | Explicar mononodo frente a clúster redundante y sus límites | Shards/réplicas y efectos de pérdida de nodo; no presentar Compose mononodo como alta disponibilidad | E6/E8 |
| 87 | Entregar dashboard completo, claro y de calidad | Export Kibana, capturas y guion de consultas reproducible | E7 |
| 90 | Probar Kafka y consumidores independientes, offsets y continuidad | Pausa/reinicio de consumidor, offsets antes/después y reconciliación de eventos | E5/E6 |
| 92 | Automatizar conversión/validación, InvokeHTTP, rutas por riesgo y almacenamiento | Flujo NiFi exportado, contadores, ramas de rechazo/error y telemetría/alertas verificadas en ES | E5/E6 |
| 95 | Probar calidad y explicar su impacto en inferencia | Faltantes, formatos y duplicados inyectados; rechazo trazable y efecto analizado | E2/E6 |
| 96 | Probar interrupción/carga y aplicar medidas contra pérdidas/duplicados | Ledger de eventos enviados, aceptados, rechazados y únicos almacenados; replay, backpressure y recuperación | E6 |
| 100,101 | Justificar señales/metadatos/resultados y mantener coherencia en limpieza/API/archivo | Diccionario, selección de variables, contrato compartido y pruebas de transformación | E2/E5 |
| 104,105 | Interpretar críticamente alertas/costes y demostrar decisiones mediante BI | Casos de mantenimiento argumentados en panel, FP/FN y límites; ahorro estimado separado de ahorro observado | E7/E8 |

## Etapas y puertas de salida

| Etapa | Objetivo y entrega para revisión | Condición para avanzar |
|---|---|---|
| E1 — acuerdo | CG01, ANEXO1, objetivos, responsables, calendario, arquitectura, análisis inicial de riesgos | Equipo registra acuerdo; tutor confirma dudas de rúbrica y adaptación de fuentes |
| E2 — datos | CG02, contratos, EDA, calidad y diseño de evaluación | Procedencia y límites aceptados; fixtures positivos/negativos diferenciados de datos operativos; sin inventar continuidad |
| E3 — modelos | Referencia, variables físicas, CV, ajuste RF/IF, desbalance, costes y métricas | Resultados reproducibles con hash/semilla/versiones; test reservado; errores interpretados y mejoras comparadas |
| E4 — servicio | FastAPI/Pydantic, modelo serializado, `/health`, `/predict`, niveles de alerta | Arranque, validación, errores y límites 0,15/0,7 comprobados; modelo cargado una vez |
| E5 — integración | Archivos→Filebeat→Kafka→NiFi→API→ES; histórico por capas/Parquet/DuckDB | Evento trazable de origen a almacenamiento/panel, rechazos identificados, contratos coherentes y flujo exportado |
| E6 — robustez | Interrupciones, replay, duplicados, carga, recursos y seguridad | Contabilidad de eventos cierra; recuperación demostrada; latencias y mejoras documentadas; límites mononodo explícitos |
| E7 — decisión | Panel Kibana y casos de mantenimiento/coste | Otro compañero reproduce filtros/consultas y explica una decisión y sus riesgos |
| E8 — entrega | Matriz final criterio→artefacto→comando→resultado→límite, memoria y defensa | Equipo revisa todos los criterios, actualiza ANEXO1, registra pendientes; nadie se autoatribuye el 10 |

Seguridad, privacidad, seguimiento y documentación son transversales. Cada control de etapa debe dejar acta breve: responsable, fecha, commit, evidencia, resultado real, pendientes y siguiente paso. Cada integrante prepara una explicación del sistema completo, además de su parte.

## Decisiones y dudas que debe resolver el equipo con el tutor

1. **SMB frente a NFS:** el servidor disponible es SMB; G49 menciona NFS→Filebeat→Kafka. Acordar montaje/lectura y equivalencia evaluable; no sustituir silenciosamente Filebeat ni invertir Kafka→NiFi.
2. **Histórico y predicción:** G62 exige histórico por máquina con `groupby`, pero el training no tiene tiempo y los snapshots muestran estados conflictivos por máquina/instante. Agrupar no crea una secuencia física válida. Implementar análisis histórico cuando sea justificable, demostrar sus límites y consultar cómo acreditar este criterio; no fabricar fechas ni confirmar horizonte de 24h.
3. **Umbrales:** G61 pide 0,15/0,7 y también threshold tuning. Conservar esos niveles como contrato docente de demostración y evaluar umbrales alternativos offline; cualquier cambio del contrato se acuerda con el tutor. Aclarar la interpretación de la «paradoja de parada programada» antes de modificar etiquetas.
4. **Objetivos cuantitativos:** G45 cita recall 76%+. Tomarlo como referencia explícita a contrastar con el tutor, junto con precisión mínima/F1/F2 y costes. El Excel no exige F1=1 ni demuestra por sí mismo adecuación industrial.
5. **Pesos y versión:** H5 contiene `15%%`; IAS tiene descriptores sin pesos visibles y fila 62 solo descriptores 7/10. Confirmar interpretación y vigencia de la copia. No rellenar huecos de la rúbrica con supuestos.
6. **Costes:** 1.200 €/h es el supuesto del enunciado, no una pérdida medida. Coste de inspección, duración de parada y efecto de mantenimiento requieren escenarios declarados o información del tutor; no inventar ahorro real.
7. **Evaluación global:** el enunciado, p. 11, combina trabajo técnico grupal, prueba individual y competencias transversales; contempla otra distribución si no hay prueba individual. Confirmar modalidad. La rúbrica técnica no sustituye controles, propuesta, presentación, autoevaluación o coevaluación. La p. 8 también evalúa organización, comunicación, implicación y autonomía.

El informe legal final deberá consultar fuentes oficiales vigentes; esta matriz registra lo que pide el docente, no emite una conclusión jurídica sobre AI Act o CE.
