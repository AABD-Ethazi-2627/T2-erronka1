# ANEXO4 CNC Guard

Adaptación Markdown del formulario docente. Borrador pendiente de acuerdo del equipo; no acredita firma ni entrega. Fuente y hash en [manifiesto](manifest.json). Se contrastaron los tres rótulos del DOCX; ANEXO4.md del corpus solo contiene la celda de propuesta.

## Erronkaren izena

CNC Guard — Mantentze Prediktiboa, según [enunciado](../../ENUNTZIATUA.md).

## BEHIN BETIKO PROPOSAMENA

**Propuesta para revisión; aprobación final pendiente.**

| Taldeak aurrera eramatea erabaki duen proposamena | |
|---|---|
| Proposamena berrikusteko | Laborategiko telemetria Filebeat, Kafka eta NiFi bidez bildu, Elasticsearch-en gorde eta Kibana-n bistaratu. Emandako 8000 errenkadako AI4I CSV murriztua erabili: 5600 fit, 1200 garapen-balidazio eta aurrez ikuskatutako testeko 1200 baztertu. FastAPI bidez RF-rekin uneko egoera sailkatu eta IF-rekin arrarotasuna bereizi, sarrerako etiketak kenduta. Pertsonak alertak berrikusi eta erabakia hartuko du. |
| Mugak | Ez dago data, ETA, RUL edo 24 orduko iragarpen industrial frogaturik. Ez da CNC fisikorik kontrolatzen. Laborategiak ez du industria-eraginkortasuna edo lege-betetzea ziurtatzen. |
| Ebidentziak | [Memoria eta 40 irizpide](README.md#matriz-de-los-40-descriptores), [emaitzak eta mugak](README.md#resultados-incorporados), [irismen aktiboa](../evidence/CG17_CURRENT_STATE_SCOPE.md). |
| Taldearen erabakia, data eta berrikuslea | Pendiente. Este borrador no demuestra un acuerdo tomado. |

ANEXO1eko konpromisoen berrespena, benetako akordioak, sinadurak eta entrega pendiente daude.

## Estado documental al 21/10/2026

Base integrada PR42 `e5faf015cc16e2044d25ab59c1ec30c32222d889`; propuesta pendiente de acuerdo. Los resultados de CG15 durable/adaptador Kafka, CG21, microbenchmark CG23, scoring replay y SMB offline se reúnen en la memoria con sus límites. TP32/FN9/FP9/TN1150 corresponde a validación reutilizada, sin evaluación final independiente nueva.

Pendientes: Apache Kafka y SMB/Filebeat reales, Kibana actual, NiFi E2E v4, migraciones y revisión humana. La base PR42 `53f342d` ya incorpora PR62 y PR64; esta última corrige los 218 avisos Kafka de Python 3.11. PR65 añade el worker opt-in y [su corrección de recibos/HTTP](../evidence/DURABLE_PIPELINE_FIX_R2_20261021.md), pendiente de revisión padre. Los límites Windows/WMIC permanecen. No se acredita aceptación humana, firma, Moodle ni entrega final; no se cierran issues.
