# Memoria CNC Guard y trazabilidad CG25

Borrador para revisión del equipo y docente, 21/10/2026. Cobertura documental de 40 descriptores; no acredita nota, aceptación humana ni entrega.

## Fuentes y atribución por sección

- [Enunciado](../../ENUNTZIATUA.md), «1. Fasea», «2. Fasea», «3. Fasea»: requisitos de pipeline, entrenamiento e inferencia; «Entregablea Orokorra» y «Demo Aurkezpena»: artefactos y demostración de 10 minutos. Los pesos por fase no se suman con los pesos por módulo de rúbrica.
- [Fuente docente exacta](../rubrica/fuente.json), Zereginak, columna G: 40 descriptores avanzados, celdas y hash del Excel local; [interpretación](../rubrica/OBJETIVOS_Y_ETAPAS.md). No se ha verificado la versión online ni se autootorga 10.
- ANEXO4.docx docente local, «Erronkaren izena», «BEHIN BETIKO PROPOSAMENA», «Taldeak aurrera eramatea erabaki duen proposamena»: estructura de [ANEXO4 adaptado](ANEXO4_CNC_Guard.md). Ruta del corpus y hash en [manifiesto](manifest.json). No se redistribuye el original ni sus metadatos privados.
- [CG30](../evidence/CG30.md), «Fuentes docentes examinadas»: atribución previa a Random Forest, metodología de validación y métricas del corpus local. Se remite a ese registro versionado; esta tarea no revalida los PDF.
- La autoría técnica previa corresponde al historial Git y los informes enlazados. Una asignación no prueba actividad individual. Esta aportación de agente organiza documentación; el equipo debe revisar y reconocer sus contribuciones reales.

## Alcance y decisiones técnicas

Base: PR42, commit `28a77543bfd67a36b96ddc2f4acc103b13f62c2e`, rama feat/17-maintenance-planner. Comparación inicial con origin/main: 0 commits exclusivos de main y 45 de esta base. PR38 es índice parcial de evidencia, no memoria aceptada. La investigación temporal de PR40/41 queda histórica y retirada del alcance activo por PR42.

Solo el CSV reducido AI4I suministrado entrena RF/IF. RF clasifica estado contemporáneo; IF expresa rareza separada. Cinco sensores y machine_type entran al estimador. Timestamp/ID son trazabilidad. NiFi elimina etiquetas y CSV crudo antes de /predict. No se predicen fechas, ETA, RUL ni fallo industrial a 24 horas.

Filebeat → Kafka → NiFi → FastAPI → NiFi → Elasticsearch → Kibana es el recorrido de laboratorio documentado. Parquet se conserva por herramienta explícita, sin archivado continuo garantizado. Una persona decide cualquier mantenimiento; no se controla CNC física. Enunciado NFS frente a evidencia SMB requiere aclaración docente; esta tarea no accede a servicios compartidos.

## Resultados y límites

[Corrección v4](../evidence/CG17_CURRENT_STATE_SCOPE.md) y [registro](../evidence/CG17_CURRENT_STATE_SCOPE.json): pruebas locales registradas de procedencia, contrato sin etiquetas y score actual. Los 104 tests son resultado previo de esa versión; CG25 no los reejecuta. No se repitió streaming E2E tras la corrección; colas antiguas requieren migración explícita.

[Índice de 19/10](../evidence/INDEX_2026-10-19.md): ensayos locales anteriores, métricas y límites. Validación reutilizada no equivale a test final independiente. Totales históricos del panel no prueban operación actual v4. CG24 es análisis previo para revisión, sin certificación legal. CG15/durabilidad tiene trabajo independiente pendiente; no se declara resuelto aquí.

**Implementado**: artefacto presente en base. **Probado local**: registro fechado de ejecución, acotado a esa versión. **CI**: checks remotos del SHA concreto. **Integrado**: merge comprobado a destino. **Aceptación humana**: revisor, fecha y conclusión reales. CG25 verifica solo documentación local; CI, integración en main y aceptación de esta aportación pendientes. No acredita despliegue, firmas, defensa ni entrega Moodle.

## Matriz de los 40 descriptores

Texto exacto por celda en fuente.json. Artefactos fijados al commit base anterior; cada informe contiene su procedimiento y resultado técnico fechado. El comando siguiente inspecciona ese registro sin ejecutar servicios. El resultado de CG25 es enlace/hash comprobado; no repite pruebas técnicas. Aplicar el alcance activo anterior a todas las filas, especialmente a experimentos temporales históricos.

| Criterio | Artefacto en base | Comando de inspección | Resultado registrado y límite | Revisor y fecha |
|---|---|---|---|---|
| Zereginak!G5 | [Informe](../evidence/CG30.md) | `git show 28a7754:docs/evidence/CG30.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G10 | [Informe](../evidence/CG30.md) | `git show 28a7754:docs/evidence/CG30.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G14 | [Informe](../evidence/CG10.md) | `git show 28a7754:docs/evidence/CG10.md` | Registro local previo. Carga concurrente y latencia E2E pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G16 | [Informe](../evidence/CG24.md) | `git show 28a7754:docs/evidence/CG24.md` | Registro local previo. No es certificación CE ni dictamen jurídico.  No equivale a aceptación. | Pendiente |
| Zereginak!G17 | [Informe](../evidence/CG24.md) | `git show 28a7754:docs/evidence/CG24.md` | Registro local previo. Sin datos de operadores; revisión legal humana pendiente.  No equivale a aceptación. | Pendiente |
| Zereginak!G19 | [Informe](../evidence/CG24.md) | `git show 28a7754:docs/evidence/CG24.md` | Registro local previo. Solo laboratorio loopback.  No equivale a aceptación. | Pendiente |
| Zereginak!G20 | [Informe](../evidence/CG24.md) | `git show 28a7754:docs/evidence/CG24.md` | Registro local previo. No validación de despliegue compartido.  No equivale a aceptación. | Pendiente |
| Zereginak!G23 | [Informe](../evidence/CG30.md) | `git show 28a7754:docs/evidence/CG30.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G24 | [Informe](../evidence/CG30.md) | `git show 28a7754:docs/evidence/CG30.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G31 | [Informe](../evidence/CG30.md) | `git show 28a7754:docs/evidence/CG30.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G32 | [Informe](../evidence/CG30.md) | `git show 28a7754:docs/evidence/CG30.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G36 | [Informe](../evidence/CG11.md) | `git show 28a7754:docs/evidence/CG11.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G38 | [Informe](../evidence/CG08.md) | `git show 28a7754:docs/evidence/CG08.md` | Registro local previo. Ablación/SMOTENC probados; interpretación física no causal.  No equivale a aceptación. | Pendiente |
| Zereginak!G39 | [Informe](../evidence/CG10.md) | `git show 28a7754:docs/evidence/CG10.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G41 | [Informe](../evidence/CG28.md) | `git show 28a7754:docs/evidence/CG28.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G45 | [Informe](../evidence/CG10.md) | `git show 28a7754:docs/evidence/CG10.md` | Registro local previo. 78,05% recall en validación reutilizada; sin test independiente ni garantía industrial.  No equivale a aceptación. | Pendiente |
| Zereginak!G46 | [Informe](../evidence/CG22.md) | `git show 28a7754:docs/evidence/CG22.md` | Registro local previo. Ensayo acotado; no caída completa ni HA.  No equivale a aceptación. | Pendiente |
| Zereginak!G49 | [Informe](../evidence/CG05.md) | `git show 28a7754:docs/evidence/CG05.md` | Registro local previo. SMB, no NFS; sin gran volumen sostenido ni timer SMB.  No equivale a aceptación. | Pendiente |
| Zereginak!G52 | [Informe](../evidence/CG30.md) | `git show 28a7754:docs/evidence/CG30.md` | Registro local previo. Comparación tecnológica y defensa por revisar.  No equivale a aceptación. | Pendiente |
| Zereginak!G55 | [Informe](../evidence/CG28.md) | `git show 28a7754:docs/evidence/CG28.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G60 | [Informe](../evidence/CG08.md) | `git show 28a7754:docs/evidence/CG08.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G61 | [Informe](../evidence/CG28.md) | `git show 28a7754:docs/evidence/CG28.md` | Registro local previo. Paradoja de parada programada requiere acuerdo; no reetiquetada.  No equivale a aceptación. | Pendiente |
| Zereginak!G62 | [Informe](../evidence/CG08.md) | `git show 28a7754:docs/evidence/CG08.md` | Registro local previo. groupby en observaciones simuladas y laboratorio temporal separado; no historial físico.  No equivale a aceptación. | Pendiente |
| Zereginak!G65 | [Informe](../evidence/CG19.md) | `git show 28a7754:docs/evidence/CG19.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G66 | [Informe](../evidence/CG18.md) | `git show 28a7754:docs/evidence/CG18.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G68 | [Informe](../evidence/CG18.md) | `git show 28a7754:docs/evidence/CG18.md` | Registro local previo. Mapping/index template probado; transformación en NiFi, sin pipeline ingest ES separado.  No equivale a aceptación. | Pendiente |
| Zereginak!G71 | [Informe](../evidence/CG19.md) | `git show 28a7754:docs/evidence/CG19.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G72 | [Informe](../evidence/CG19.md) | `git show 28a7754:docs/evidence/CG19.md` | Registro local previo. Propuestas de decisión, no mantenimiento real ejecutado.  No equivale a aceptación. | Pendiente |
| Zereginak!G77 | [Informe](../evidence/CG05.md) | `git show 28a7754:docs/evidence/CG05.md` | Registro local previo. Captura explícita y conservación separada; sin retención continua garantizada.  No equivale a aceptación. | Pendiente |
| Zereginak!G80 | [Informe](../evidence/CG22.md) | `git show 28a7754:docs/evidence/CG22.md` | Registro local previo. HTTP secuencial; carga sostenida/concurrente pendiente.  No equivale a aceptación. | Pendiente |
| Zereginak!G85 | [Informe](../evidence/CG12.md) | `git show 28a7754:docs/evidence/CG12.md` | Registro local previo. Mononodo, sin ensayo de clúster.  No equivale a aceptación. | Pendiente |
| Zereginak!G87 | [Informe](../evidence/CG19.md) | `git show 28a7754:docs/evidence/CG19.md` | Registro local previo. Canvas reales verificados; captura de página completa no disponible.  No equivale a aceptación. | Pendiente |
| Zereginak!G90 | [Informe](../evidence/CG22.md) | `git show 28a7754:docs/evidence/CG22.md` | Registro local previo. Pausa consumidor/reinicio Filebeat; reinicio total pendiente.  No equivale a aceptación. | Pendiente |
| Zereginak!G92 | [Informe](../evidence/CG16.md) | `git show 28a7754:docs/evidence/CG16.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G95 | [Informe](../evidence/CG14.md) | `git show 28a7754:docs/evidence/CG14.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G96 | [Informe](../evidence/CG22.md) | `git show 28a7754:docs/evidence/CG22.md` | Registro local previo. Contabilidad cerrada en ensayo acotado, no garantía de pérdida cero.  No equivale a aceptación. | Pendiente |
| Zereginak!G100 | [Informe](../evidence/CG18.md) | `git show 28a7754:docs/evidence/CG18.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G101 | [Informe](../evidence/CG16.md) | `git show 28a7754:docs/evidence/CG16.md` | Registro local previo. Explicación y aceptación del equipo pendientes.  No equivale a aceptación. | Pendiente |
| Zereginak!G104 | [Informe](../evidence/CG10.md) | `git show 28a7754:docs/evidence/CG10.md` | Registro local previo. Costes por escenarios; no ahorro observado.  No equivale a aceptación. | Pendiente |
| Zereginak!G105 | [Informe](../evidence/CG19.md) | `git show 28a7754:docs/evidence/CG19.md` | Registro local previo. Panel con datos de aceptación, sin validación de utilidad por operador.  No equivale a aceptación. | Pendiente |

## Pendientes para completar la entrega

1. Revisar dependencias CG23 (capacidad/reinicio completo), CG24 (seguridad y privacidad) y CG30 (explicación propia de entradas, salidas, decisiones y errores). Tener informe no cierra una dependencia.
2. Otro miembro debe contrastar cada descriptor con su evidencia y registrar conclusión y fecha en el seguimiento. No se inventan reuniones, defensa ni aprendizaje individual.
3. Confirmar NFS/SMB, ponderaciones y alcance con el docente. ANEXO1 registra 11 semanas frente a ~3 semanas/~45 horas del enunciado; fechas oficiales pendientes. Esta memoria identifica la contradicción sin resolverla por inferencia.
4. Revisar la propuesta ANEXO4 y los acuerdos reales de [ANEXO1](../requisitos/ANEXO1_CNC_Guard.md); compromisos, firmas y aprobación final siguen pendientes. No se modifica el reparto ni se atribuyen acuerdos nuevos.
5. Preparar demo/defensa del enunciado y recoger después evidencia real, aceptación docente y entrega por el canal requerido.

Registro humano a completar:

```text
Criterio e issue:
PR y commit:
Artefacto y comando/procedimiento:
Resultado real y fecha:
Límite:
Revisor, conclusión y fecha: pendiente
```

## Verificación documental

`python3 scripts/check_cg25_memory.py`: cobertura exacta de 40 celdas, enlaces locales y hashes de fuentes/evidencias versionadas. `git diff --check`: whitespace. No prueban servicios, ML, CI ni aceptación. Git fija esta memoria y el manifiesto; no se incluye hash autorreferencial.
