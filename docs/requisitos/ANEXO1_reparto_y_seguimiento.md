# ANEXO1 CNC Guard — reparto y seguimiento

Borrador del 16/10/2026 preparado a petición del equipo a partir de las asignaciones actuales de los issues abiertos. [ANEXO1 en Markdown en euskera](ANEXO1_CNC_Guard.md). No acredita firma, consenso ni entrega al profesorado.

## Reparto técnico observado

| Rol indicado por el usuario | Cuenta responsable según los issues | Issues individuales abiertos |
|---|---|---|
| Infra | petiteiker | #4 entorno Python, #5 entradas del laboratorio, #12 Compose/almacenamiento, #13 Kafka, #21 fallos/recuperación, #23 capacidad/retención/coste |
| Diseño | Angiecrizu | #19 Kibana, #25 memoria/criterios/ANEXO4, #26 demostración y defensa |
| Dev | Niistal | #14 NiFi, #15 archivo Parquet, #16 inferencia/calidad, #17 agrupación de avisos, #18 Elasticsearch |
| Generalista ML / Project lead | tears-mysthrala | #2 inventario, #3 contratos, #6 histórico/EDA, #7 variables/etiquetas/splits, #8 RF, #9 IF, #10 métricas/umbrales |

#24 (seguridad y efecto humano) está compartido por tears-mysthrala y Angiecrizu. #1, #11, #20, #22 y #27 están asignados a los cuatro: acuerdo de alcance, hitos, prueba integral y defensa son responsabilidad compartida. Esta foto no cambia asignaciones ni demuestra que las tareas estén hechas. [Snapshot verificable de 27 issues abiertos](CG01_reparto_issues.json), con enlaces y cuentas.

## Correspondencia propuesta con la plantilla docente

El usuario ha confirmado expresamente el 16/10/2026 las cuatro cuentas y su correspondencia con los roles técnicos de la tabla. Su correspondencia con los cargos de tutoría siguientes es una propuesta derivada del trabajo, pendiente de confirmación colectiva:

| Cargo ANEXO1 | Propuesta | Motivo |
|---|---|---|
| Coordinación | tears-mysthrala | Generalista ML/Project lead; coordinación de objetivos, contratos y evaluación |
| Portavocía | Angiecrizu | Preparación de demo y defensa (#26) |
| Secretaría | Angiecrizu | Memoria y documentación (#25) |
| Apoyo 1 | Niistal | Desarrollo e integración; apoyo a la comunicación técnica y revisión cruzada |
| Apoyo 2 | petiteiker | Infraestructura y pruebas; apoyo al seguimiento de tiempos y disponibilidad |

La plantilla tiene cinco cargos y el equipo cuatro personas; se propone que diseño/documentación asuma portavocía y secretaría. Las funciones de apoyo de la plantilla (tono de comunicación y tiempo) se mantienen, además de las responsabilidades técnicas. Ser responsable de diseño no prueba por sí solo que una persona haya aceptado portavocía.

Se mantienen las cuentas de GitHub confirmadas por el usuario como identificación en este borrador, sin inferir nombres civiles. Tutor/a y denominación oficial de grupo pendientes de confirmación. El equipo se identifica provisionalmente como CNC Guard; `T2` se marca para confirmar. El curso 2026–27 procede de la plantilla; las 11 semanas del enunciado no implican reiniciar el plazo a partir de hoy.

## Objetivos colectivos propuestos

1. Aprender a trabajar en equipo y ayudarnos a comprender el sistema completo, como establece ANEXO1.
2. Entregar el laboratorio CNC Guard con datos trazables, evaluación reproducible, integración y panel, ajustado a los [40 descriptores avanzados](../rubrica/OBJETIVOS_Y_ETAPAS.md).
3. Revisar los resultados de cada etapa, registrar las limitaciones y preparar una defensa en la que cada integrante pueda explicar su contribución y el recorrido completo.

## Compromisos de trabajo propuestos

Las cuatro filas de compromisos del ANEXO1 en Markdown resumen responsabilidades ya asignadas en los issues. Son propuestas para ratificar, no declaraciones personales firmadas. Ninguna firma se rellena automáticamente. Se conserva la posibilidad de ampliar los compromisos en Markdown.

| Responsable | Compromiso propuesto | Evidencia de seguimiento |
|---|---|---|
| Infra | Mantener instrucciones de arranque y recuperación, registrar disponibilidad/bloqueos y ejecutar pruebas de capacidad y fallos | Configuraciones versionadas, comandos/resultados y pruebas #21/#23 |
| Diseño | Mantener panel y memoria vinculados a criterios, recoger acuerdos y preparar el guion de demostración | Export/capturas de Kibana, memoria, actas y guion #19/#25/#26 |
| Dev | Implementar contratos y flujo modular, tratar rechazos/errores y probar la trazabilidad de cada evento | Código, flujo NiFi exportado, fixtures y resultados #14–#18 |
| ML / Project lead | Mantener trazabilidad de datos/modelos, justificar evaluación y umbrales y coordinar dependencias/revisiones | Inventario, experimentos, métricas, PRs y revisiones #2/#3/#6–#10 |

Propuesta de seguimiento: revisión semanal breve con responsable, estado real, evidencia, bloqueo y siguiente paso por issue. En cada puerta E1–E8, revisar conjuntamente las evidencias antes de aceptar la etapa. Registrar ausencias o cambios que afecten a otros y transferir conocimientos. No dar por finalizada una tarea solo por hacer push o abrir PR. CI se ejecutará cuando se prepare el merge, según la indicación del usuario.

## Pendientes para aprobar

- Confirmar tutor/a, grupo y periodo oficial; las fechas se alinearán con la entrega del profesorado.
- Ratificar la correspondencia de cargos de tutoría y las cuatro propuestas de compromiso.
- Revisar objetivos y calendario del borrador CG01, resolver las dudas de rúbrica con el tutor y recoger el acuerdo.
- Firmar personalmente cuando corresponda y conservar evidencia de la entrega. El documento original se conserva intacto.
