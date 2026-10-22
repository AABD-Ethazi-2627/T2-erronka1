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

## Estado documental al 22/10/2026

Base auditada PR42 `f770932d61ff55158bb18c9d89120617e8c5db65`. La [matriz actual](../rubrica/ESTADO_20261022.md) incorpora PR66 DuckDB2, PR67 Windows y PR69 Kibana/ES/SMB reales. PR68 sigue abierta, fuera de esta base y con revisión del fix P2 pendiente al corte. Los cuatro mensajes SMB no prueban carga sostenida ni SLA; la regresión DOM/ARIA no acredita zoom nativo ni NVDA audible.

TP32/FN9/FP9/TN1150 es validación reutilizada. Split activo 5600/1200/1200, sin test final independiente nuevo. No se ejecutan entrenamientos ni se cambian modelos de entrega en esta actualización.

Acuerdo, reproducción por compañero, explicación individual, firmas, Moodle y entrega final: pendientes. No se cierran issues ni se asigna calificación.
