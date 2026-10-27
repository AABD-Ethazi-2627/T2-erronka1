# Rúbrica de CNC Guard

Este directorio mantiene el foco técnico del proyecto: qué exige el docente para el nivel avanzado, en qué etapa se aborda y qué evidencia falta. Su contenido se revisa desde las issues y PRs. ANEXO1 no contiene ni sustituye esta rúbrica.

| Documento | Para qué usarlo |
|---|---|
| [Estado actual del 23/10: 40 criterios](ESTADO_20261023.md) | Consultar objetivos, evidencias por SHA, aceptaciones vigentes y pendientes concretos de CG31/#80 |
| [Registro de aclaraciones docentes](ACLARACIONES_20261023.md) | Preparar CG33/#82 y registrar respuestas reales, sin atribuir aprobaciones pendientes |
| [Objetivos y etapas](OBJETIVOS_Y_ETAPAS.md) | Diseñar el trabajo y consultar la interpretación de cada descriptor de 10 |
| [Seguimiento histórico](SEGUIMIENTO.md) | Consultar el corte del 22/10 y sus añadidos fechados; sus estados remotos han sido superados por el corte actual |
| [Fuente original extraída](fuente.json) | Consultar el texto docente exacto, coordenadas de celdas y SHA-256 |

Las [30 guías de issues](../issues/README.md) concretan estos criterios en pasos y pruebas para estudiantes. CG28 (#35), CG29 (#36) y CG30 (#37) separan API, Filebeat y justificación conceptual.

El corte actual parte de `main` `5005ccde81f16cd2deac6ee3b30085d773e0fc88`.
#10, #11, #20, #24 y #25 están cerradas; #26, #27 y #37 siguen abiertas.
La ampliación CG31–CG40 está recogida en el estado actual y en la
[revisión de las 11 issues abiertas](../evidence/PENDING_REQUIREMENTS_20261023.md).
`SEGUIMIENTO.md`, `ESTADO_20261022.md`, `OBJETIVOS_Y_ETAPAS.md` y `fuente.json`
se conservan con sus hashes CG25. Sus reservas de aceptación genérica, test nuevo
y procesadores NiFi nativos se leen con la fecha original y las decisiones PM
posteriores. El nuevo corte no acredita defensa, entrega o aprobación docente.

## Cómo usarla durante el trabajo

1. Al concretar una issue, identificar sus celdas de rúbrica y la evidencia que debe producir. Una issue puede cubrir varios criterios y un criterio puede necesitar varias issues.
2. En el PR, indicar criterio, artefacto, comando o procedimiento de reproducción, resultado obtenido y limitaciones. Enlazar una versión concreta de código/evidencia cuando esté disponible.
3. En cada control de etapa, revisar la tabla de seguimiento y registrar qué falta. El responsable propuesto organiza la evidencia con sus colaboradores; no sustituye la evaluación del profesor ni el aprendizaje de todo el equipo.
4. Cambiar a «Revisado por el equipo» solo después de revisar la evidencia. No convertir un PR abierto, un test verde o una descripción de diseño en un criterio acreditado automáticamente.
5. Mantener las dudas para el tutor en [objetivos y etapas](OBJETIVOS_Y_ETAPAS.md), especialmente SMB/NFS, histórico temporal, umbrales y pesos. Si llega otra rúbrica, registrar su hash y revisar los cambios antes de sustituir los requisitos.

Estados del seguimiento: **Pendiente de evidencia**, **Evidencia aportada**, **Revisado por el equipo** y **Pendiente de aclaración docente**. No son notas. CI se reserva para preparar el merge, según la instrucción del usuario; las verificaciones locales se documentan cuando se ejecutan.

## Límites de la fuente

Copia local `Erronka1_ikaslearen_errubrika.xlsx`, hoja `Zereginak`, columna G: 40 descriptores avanzados no vacíos. La extracción conserva el texto y peso tal como aparecen; no reemplaza el Excel completo ni sus demás niveles. No se ha podido verificar la versión online. El enlace docente registrado es [la hoja oficial](https://docs.google.com/spreadsheets/d/1cSTAGeRHBalejlizDdn1UGMZZfkBeenMut27FWV8W80/edit?usp=sharing).

No se combinan pesos de asignaturas distintas ni se afirma que F1=1 sea un requisito. Las competencias transversales, los controles, la presentación y la prueba individual se revisan además conforme al enunciado y a lo que confirme el profesorado.
