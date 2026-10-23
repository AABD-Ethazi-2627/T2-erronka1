# Memoria CNC Guard y trazabilidad CG25/CG27/CG30

Borrador reconciliado el 22/10/2026 para revisión del equipo y docente. Cubre documentalmente 40 descriptores; no acredita nota, aceptación humana, firmas ni entrega final.

## Fuentes y atribución por sección

- [Conciliación CG10 del 22/10](../evidence/CG10_PRECISION_20261022.md): corrige
  la precisión de lectura CSV de los umbrales y costes; reemplaza el JSON anterior
  para los resultados activos. Las revisiones Git fijadas en la matriz conservan
  su valor histórico; no acreditan la revisión ni el merge de este arreglo.
- [Enunciado](../../ENUNTZIATUA.md): fases de pipeline, entrenamiento e inferencia; «Entregablea Orokorra» y «Demo Aurkezpena» describen artefactos y defensa de 10 minutos. Los pesos de fase y de módulo son ejes distintos.
- [Fuente docente exacta](../rubrica/fuente.json), Zereginak, columna G: 40 descriptores, celdas y hash del Excel local; [interpretación](../rubrica/OBJETIVOS_Y_ETAPAS.md). No se ha cotejado la versión online ni se asigna una nota.
- ANEXO4.docx docente local: «Erronkaren izena», «BEHIN BETIKO PROPOSAMENA» y «Taldeak aurrera eramatea erabaki duen proposamena» dan la estructura del [borrador adaptado](ANEXO4_CNC_Guard.md). Ruta y hash del original en el [manifiesto](manifest.json); el original no se redistribuye ni se vuelve a inspeccionar aquí.
- [CG30](../evidence/CG30.md#versiones-y-decisiones-incorporadas): argumentación y versiones basadas en artefactos existentes. Se mantiene su atribución docente previa; no se ha hecho investigación nueva ni se han revalidado los PDF.
- Resultados, comandos y límites se atribuyen a sus informes versionados. Esta aportación reconcilia documentación y ejecuta el verificador documental; no repite sus pruebas técnicas. La autoría técnica consta en Git. El equipo debe revisar y reconocer sus contribuciones reales: una asignación no prueba actividad individual.

## Alcance y decisiones técnicas

Base auditada: PR42 `f770932d61ff55158bb18c9d89120617e8c5db65`, árbol `7f47d0763d7fb04ca25a999635a53b49b2a3e4d7`. Incluye PR62/64/65/66/67/69 por integración previa. PR68 permanece abierta y fuera de esta base al corte del 22/10/2026: evidencia del autor y revisión P2 no equivalen a merge. La base anterior `e5faf01` y el snapshot original `28a7754` se conservan como históricos en el manifiesto. Integración en PR42 no equivale a merge en main ni aceptación humana.

Solo el CSV reducido AI4I suministrado, de **8000 filas**, alimenta el alcance activo. El [split por índices](../evidence/CG04_split_membership.json) es **5600 fit / 1200 validación de desarrollo / 1200 excluidas**, disjuntas y con cobertura completa; esas últimas filas pertenecen al test previamente inspeccionado y no son un test final independiente nuevo. El ejercicio PR43 6400/1600 es histórico: no sustituye el split activo ni autoriza promoción. [CG04](../CG04_ENVIRONMENT.md) documenta la separación y la compatibilidad del entorno.

RF clasifica **estado contemporáneo**, IF expresa rareza separada. Cinco sensores y `machine_type` entran al estimador; timestamp/ID son trazabilidad. NiFi debe retirar etiquetas y CSV crudo antes de `/predict`. No se predicen fechas, ETA, RUL ni averías industriales a 24 horas. PR40/41 y la simulación estacional permanecen etiquetadas como investigación histórica fuera de entrega.

Filebeat → Kafka → NiFi → FastAPI → NiFi → Elasticsearch → Kibana describe el recorrido de laboratorio. El archivo CG15 y su adaptador Kafka ya están implementados e integrados; no acredita archivado continuo de ese recorrido ni su E2E v4. Una persona decide el mantenimiento; no se controla una CNC física. La discrepancia NFS del enunciado frente a SMB requiere aclaración docente.

## Resultados incorporados

Actualización específica CG24, 22/10/2026, sobre main `3b79c92`:
[tabla normativa, fuentes verificadas y responsabilidades](../evidence/CG24.md#aplicabilidad-normativa--corte-del-22102026).
Completa el análisis que faltaba para G16/G17; el criterio 2 de #24 queda pendiente
de revisión PM e integración. Los criterios 1/3/4/5 ya tienen aceptación PM en
el comentario 6342074330 de #24, enlazado en el informe. Las 40 filas de la matriz
mantienen su corte histórico y la revisión/explicación educativa pendiente; no
se confunde aceptación documental del issue con nota, defensa o certificación.

Los resultados siguientes están registrados en las fuentes indicadas. «Integrado» describe un merge de código; no expresa aceptación humana o de todos los criterios asociados.

| Frente | Evidencia y resultado registrado | Límite vigente |
|---|---|---|
| Clasificación y split | [Alcance v4](../evidence/CG17_CURRENT_STATE_SCOPE.md), [membresía](../evidence/CG04_split_membership.json) y [CG10](../evidence/CG10.md): TP=32, FN=9, FP=9, TN=1150, total 1200; recall/precision 32/41=78,05%. | **Validación reutilizada** para desarrollo/selección de umbral. No es test final independiente ni garantiza generalización industrial; no se recalculan métricas aquí. |
| CG15 durable, PR46 | [Archivo](../evidence/CG15_ARCHIVE.md): Bronze de bytes originales, Parquet, ledger, fsync→commit→ACK, detección de corrupción y replay; compatibilidad Parquet 18.1.0↔23.0.1 conservando bytes. Revisión independiente favorable al delta y merge verificados. | Disco local y fallos controlados. No prueba pérdida eléctrica, durabilidad de hardware ni transporte distribuido. |
| Adaptador Kafka, PR58/60 | [CG15 Kafka](../evidence/CG15_KAFKA_20261021.md): 17 tests focales; loopback con librdkafka mock 2.16.0, 3 envíos=1 guardado+1 duplicado+1 rechazado, commit/replay 3, hashes conservados y SIGTERM exit 0. PR60 añade manejo de JSON profundo. | Mock de protocolo, **no Apache Kafka 3.7 real**. TLS/SASL, operación del clúster, namespaces/retención y aceptación de transporte pendientes. |
| CG21, PR45 | [Harness durable](../evidence/CG21.md) y [JSON](../evidence/CG21_durable_20261021.json): 5=3 accepted+2 rejected+0 pending; 2 únicas, 1 duplicada. Cortes `os._exit(73)` en after_write/before_commit/after_commit y replay conservan Parquet. | Fuente SQLite local y procesos controlados; no offsets Kafka reales, HA o caída distribuida. El [fixture anterior](../evidence/CG21_fixture.json) se conserva como histórico. |
| CG23, PR47 | [Protocolo](../evidence/CG23.md), [18 mediciones](../evidence/CG23_repeated_20261021.json): 3 repeticiones × 25/100/250 eventos/s × 1/4 consumidores, 2250 entregas ofrecidas sin replay, espera sintética 10 ms. Revisión favorable acotada al microbenchmark. | In-memory/JSONL buffered sin fsync; no inferencia, Kafka/NiFi/ES ni capacidad sostenible del pipeline. Percentiles por corrida, CPU incluye replay y RSS es máximo del intérprete. Los escenarios de coste/retención son hipotéticos. |
| Scoring replay, PR61 | [Contrato](../SCORING_REPLAY_CONTRACT.md): respuesta canónica SQLite persistida antes del 200, replay estable de `scored_at`, 409 ante identidad con otro contenido y fallo cerrado. [Evidencia PR61](../evidence/PR61_ES_FIXTURE_IDENTITY.md): 237 tests y 3 skips por intérprete, 11 de replay y 2 ES focales OK en 3.11/3.12. | Dobles deterministas, SQLite/archivo reales; no modelos de entrega ni NiFi E2E. Ledger local compartido por workers, no SQLite sobre SMB/NFS ni garantía entre réplicas independientes. Migración/importación de respuestas previas no implementada. |
| SMB offline, PR63 (antecedente; PR69 amplía debajo) | [Resultados](../evidence/CG05_CG29_OFFLINE_20261021.md), [protocolo](../SMB_FILEBEAT_LAB.md): 19 tests por pasada, dos pasadas por 3.11/3.12; detección de descargas cortas/cambiantes y formato de líneas, publicación y claves de replay. Revisión independiente favorable al delta offline. | Dobles de subprocess y oráculo, **sin SMB/Filebeat/registry/Kafka reales**. Mutación de igual tamaño/prefijo estable exige protocolo del productor. El nombre publicado no tiene garantía demostrada frente a corte eléctrico. |
| Panel, contrato ES y demo, PR49–56 (antecedente) | [CG24](../evidence/CG24_2026-10-21.md), [render](../evidence/CG19_render_2026-10-21.md), [contrato/migración ES](../evidence/ES_V4_CONTRACT_MIGRATION.md), [ensayo CG26](../evidence/CG26_REHEARSAL.md). | Evidencia offline/local o ES desechable según informe; no demuestra Kibana real actual, migración del servicio compartido, seguridad industrial ni defensa humana. |
| Corrección SVG de PR69, 22/10 | [ARIA y captura de página20](../evidence/CG19_SVG_ARIA_20261022.md). | Regresión incremental y filtros de Kibana propio con fixtures sintéticas; zoom nativo, NVDA audible, carga y aceptación humana pendientes. |

| DuckDB 2.0, PR66 | [Migración](../DUCKDB_2_MIGRATION.md): contrato UTC/ns/NULL y compatibilidad Parquet verificados por sus autores. | Sin reserializar bytes antiguos para ocultar corrupción; historial 18/23 preservado. |
| Windows, PR67 | [Informe del autor](../evidence/WINDOWS_PORTABILITY_20261022.md): 303 tests estrictos x2 y pytest 558 passed/250 subtests/3 skips por cada combinación Windows/Fedora y Python3.11/3.12. | Capas solapadas; no sumar como independientes. Tres skips ES, recuperación de proceso Windows sin garantía powercut. Estas suites no se repiten en esta actualización documental. |
| Kibana/ES/SMB reales, PR69 | [Laboratorio del autor](../evidence/ISOLATED_RUNTIME_20261022.md): filtros 0/1/31/100, migración ES/rollback, cuatro mensajes SMB/Filebeat/registry→Kafka exactos antes/después de cortes. | Fixtures sintéticas; no carga/SLA, migración compartida ni automatización NiFi completa. [Corrección DOM/ARIA](../evidence/CG19_SVG_ARIA_20261022.md), zoom nativo/NVDA audible pendientes. |

El [índice de 19/10](../evidence/INDEX_2026-10-19.md) conserva ensayos pre-v4 como históricos. PR62 ya está incorporada en la base PR42 `53f342d`; PR65 añade el worker durable opt-in y [corrige recibos y validación HTTP](../evidence/DURABLE_PIPELINE_FIX_R2_20261021.md). Esta implementación y sus pruebas locales no acreditan cableado del grafo NiFi activo ni streaming Apache Kafka/NiFi E2E. PR65 ya está integrada; la aceptación del recorrido completo y main siguen pendientes.

## Límites y pendientes

- **Kafka Python 3.11:** el registro histórico SMB tenía 218 avisos del primer import. PR64 los corrige con el wheel fijado `3.0.11+cncguard.1`, ya incorporado en `53f342d`; véase [evidencia](../evidence/KAFKA311_WARNING_FIX_20261021.md). Los logs históricos no cambian y sus fallos no se presentan como passes nuevos.
- **Windows:** la [matriz histórica](../evidence/STARLETTE_TESTCLIENT_20261021.md) conserva su resultado previo de 12 errores POSIX y aviso WMIC. La corrección posterior define el [contrato actual](../PLATFORM_SUPPORT.md), separando recuperación de proceso Windows de fsync POSIX. El informe histórico no se reescribe ni acredita por sí solo las pruebas del cambio actual.
- **Runtime y migración:** PR69 aporta Kibana/ES y SMB/Filebeat/registry→Kafka reales propios, con fixtures y cuatro mensajes. PR68 aporta ensayos Apache Kafka/NiFi del autor fuera de esta base; el P2 de orden de `docker diff` está pendiente de revisión al corte. Siguen pendientes carga/SLA, E2E automático integrado, reconciliación de identidades entre fuentes y migración/importación de respuestas canónicas antiguas. No se aplican cambios a servicios compartidos.
- **Personas y entrega:** pendientes revisión del padre, contraste de otro miembro, explicación individual CG30, demo/defensa, acuerdos ANEXO1/ANEXO4, firmas y canal Moodle. La información del usuario sobre tutor no sustituye un acta o aceptación textual archivada. No se cierran issues.

**Implementado**: código presente. **Probado local**: ejecución fechada de un SHA/entorno con límites. **CI**: checks del SHA concreto. **Integrado**: merge comprobado al destino indicado. **Aceptación humana**: persona, fecha y conclusión reales. Esta actualización aporta reconciliación documental y comprobaciones focales propias; CI del nuevo SHA y revisión del padre son fases separadas. No hay despliegue ni entrega final.

## Matriz de los 40 descriptores

Texto exacto por celda en fuente.json. Artefactos fijados a la base integrada `f770932d61ff55158bb18c9d89120617e8c5db65`; CG30 se amplía documentalmente en esta PR y el comando muestra su antecedente en base. Cada informe contiene su procedimiento y resultado técnico fechado. El comando siguiente inspecciona ese registro sin ejecutar servicios. El resultado de CG25 es enlace/hash comprobado; no repite pruebas técnicas. Aplicar el alcance activo anterior a todas las filas, especialmente a experimentos temporales históricos.

| Criterio | Artefacto en base | Comando de inspección | Resultado registrado y límite | Revisor y fecha |
|---|---|---|---|---|
| Zereginak!G5 | [Informe](../evidence/CG30.md) | `git show f770932:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G10 | [Informe](../evidence/CG30.md) | `git show f770932:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G14 | [Informe](../evidence/CG23.md) | `git show f770932:docs/evidence/CG23.md` | 18 corridas de microbenchmark local; no latencia E2E ni capacidad Kafka/NiFi/ES. Aceptación humana pendiente. | Pendiente |
| Zereginak!G16 | [Informe](../evidence/CG24_2026-10-21.md) | `git show f770932:docs/evidence/CG24_2026-10-21.md` | Análisis previo por machine_type, sin certificación CE ni dictamen jurídico. Aceptación humana pendiente. | Pendiente |
| Zereginak!G17 | [Informe](../evidence/CG24_2026-10-21.md) | `git show f770932:docs/evidence/CG24_2026-10-21.md` | Sin datos de operadores; revisión legal humana pendiente. Aceptación humana pendiente. | Pendiente |
| Zereginak!G19 | [Informe](../evidence/CG24_2026-10-21.md) | `git show f770932:docs/evidence/CG24_2026-10-21.md` | Laboratorio acotado; no acreditación de exposición compartida segura. Aceptación humana pendiente. | Pendiente |
| Zereginak!G20 | [Informe](../evidence/CG24_2026-10-21.md) | `git show f770932:docs/evidence/CG24_2026-10-21.md` | Análisis por subgrupo; sin validación de despliegue compartido. Aceptación humana pendiente. | Pendiente |
| Zereginak!G23 | [Informe](../evidence/CG30.md) | `git show f770932:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G24 | [Informe](../evidence/CG30.md) | `git show f770932:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G31 | [Informe](../evidence/CG30.md) | `git show f770932:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G32 | [Informe](../evidence/CG30.md) | `git show f770932:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G36 | [Informe](../evidence/CG04_split_membership.json) | `git show f770932:docs/evidence/CG04_split_membership.json` | Dataset activo de 8000 filas; split 5600/1200/1200 documentado en CG04, sin test final nuevo. Aceptación humana pendiente. | Pendiente |
| Zereginak!G38 | [Informe](../evidence/CG08.md) | `git show f770932:docs/evidence/CG08.md` | Evidencia versionada. Ablación/SMOTENC probados; interpretación física no causal. Aceptación humana pendiente. | Pendiente |
| Zereginak!G39 | [Informe](../evidence/CG10.md) | `git show f770932:docs/evidence/CG10.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G41 | [Informe](../CG14_DURABLE_PIPELINE.md) | `git show f770932:docs/CG14_DURABLE_PIPELINE.md` | API/carga única/validación/replay implementados; worker durable opt-in. Cableado automático del grafo NiFi activo y E2E completo no acreditados en esta base. Aceptación humana pendiente. | Pendiente |
| Zereginak!G45 | [Informe](../evidence/CG10.md) | `git show f770932:docs/evidence/CG10.md` | TP32/FN9/FP9/TN1150 en validación reutilizada; no test final independiente. Aceptación humana pendiente. | Pendiente |
| Zereginak!G46 | [Informe](../evidence/WINDOWS_PORTABILITY_20261022.md) | `git show f770932:docs/evidence/WINDOWS_PORTABILITY_20261022.md` | Autor PR67: 303 tests estrictos x2 y pytest 558+250 subtests por cada uno de cuatro entornos. Recuperación de proceso; latencia E2E, apagado y fiabilidad distribuida pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G49 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | Autor PR69: SMB Windows + Filebeat/registry real + Kafka propio, cuatro mensajes exactos antes/después de cortes. Sin carga sostenida ni recorrido completo NiFi→modelo→ES; equivalencia SMB/NFS pendiente. Aceptación humana pendiente. | Pendiente |
| Zereginak!G52 | [Informe](../evidence/CG30.md) | `git show f770932:docs/evidence/CG30.md` | Evidencia versionada. Comparación tecnológica y defensa por revisar. Aceptación humana pendiente. | Pendiente |
| Zereginak!G55 | [Informe](../evidence/CG28.md) | `git show f770932:docs/evidence/CG28.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G60 | [Informe](../evidence/CG08.md) | `git show f770932:docs/evidence/CG08.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G61 | [Informe](../evidence/CG28.md) | `git show f770932:docs/evidence/CG28.md` | Evidencia versionada. Paradoja de parada programada requiere acuerdo; no reetiquetada. Aceptación humana pendiente. | Pendiente |
| Zereginak!G62 | [Informe](../evidence/CG08.md) | `git show f770932:docs/evidence/CG08.md` | Evidencia versionada. groupby en observaciones simuladas y laboratorio temporal separado; no historial físico. Aceptación humana pendiente. | Pendiente |
| Zereginak!G65 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | Kibana real con 100 IDs sintéticos y filtros 0/1/31/100. Relación telemetría/inferencia documentada; utilidad operativa y entrada continua completa pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G66 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | ES real: strict mapping, reindex/alias/rollback e in-place v4 con documentos sintéticos. No migración del servicio compartido ni de respuestas canónicas previas. Aceptación humana pendiente. | Pendiente |
| Zereginak!G68 | [Fuente histórica](../evidence/CG18.md) · [Ingest ES actual](../evidence/G68_ES_INGEST_20261022.md) | `git show f770932:docs/evidence/CG18.md` conserva el corte previo; export y evidencia actual enlazados | Guard final versionado sin alterar respuesta canónica; simulación, mapping estricto y replay en laboratorio propio. Migración compartida y aceptación humana pendientes. | Pendiente |
| Zereginak!G71 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | Kibana/Discover reales: filtros/ventana, total 100 frente a muestra 50, 20 páginas/100 IDs. No serie física observada; selección visual y explicación humana pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G72 | [Informe](../evidence/CG19_2026-10-21.md) | `git show f770932:docs/evidence/CG19_2026-10-21.md` | Casos FP/FN y propuesta de inspección; matriz TP32/FN9/FP9/TN1150 reutilizada. No mantenimiento real ni decisión aceptada por operador. Aceptación humana pendiente. | Pendiente |
| Zereginak!G77 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | Archivo durable implementado; autor PR69 concilia cuatro mensajes SMB/Filebeat/Kafka con registry persistente. Retención continua, recuperación de host y trazabilidad integral pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G80 | [Informe](../evidence/CG23.md) | `git show f770932:docs/evidence/CG23.md` | Concurrencia 1/4 con espera sintética y buffer; no carga sostenida del pipeline ni inferencia medida. Aceptación humana pendiente. | Pendiente |
| Zereginak!G85 | [Informe](../evidence/CG12.md) | `git show f770932:docs/evidence/CG12.md` | Evidencia versionada. Mononodo, sin ensayo de clúster. Aceptación humana pendiente. | Pendiente |
| Zereginak!G87 | [Informe](../evidence/CG19_SVG_ARIA_20261022.md) | `git show f770932:docs/evidence/CG19_SVG_ARIA_20261022.md` | Kibana real y regresión DOM incremental 35 estados; guías ARIA reactivas y captura nueva página20. Zoom nativo y NVDA audible pendientes; no conformidad global ni aceptación humana. Aceptación humana pendiente. | Pendiente |
| Zereginak!G90 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | Autor PR69: cuatro pares clave/mensaje exactos antes/después de SMB y Filebeat. PR68 tiene evidencia Apache Kafka/NiFi del autor fuera de esta base; fix P2 docker diff aún en revisión al corte. Aceptación humana pendiente. | Pendiente |
| Zereginak!G92 | [Informe](../CG14_DURABLE_PIPELINE.md) | `git show f770932:docs/CG14_DURABLE_PIPELINE.md` | Conversión/validación y worker opt-in presentes; recibos verificables antes de ACK. No grafo ConsumeKafka/InvokeHTTP/ES automático integrado demostrado; ensayo de driver externo PR68 no lo sustituye. Aceptación humana pendiente. | Pendiente |
| Zereginak!G95 | [Informe](../evidence/CG21.md) | `git show f770932:docs/evidence/CG21.md` | Controles de faltantes/formato/duplicados y rechazo durable, HTTP 409/422/503; pruebas con dobles y SQLite reales. Impacto integral NiFi/ES y aceptación humana pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G96 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | Replay/cortes de proceso y registry comprobados según autores; cuatro mensajes SMB sin ausentes/duplicados. No pérdida cero distribuida, carga sostenida, HA ni corte eléctrico. Aceptación humana pendiente. | Pendiente |
| Zereginak!G100 | [Informe](../evidence/ES_V4_CONTRACT_MIGRATION.md) | `git show f770932:docs/evidence/ES_V4_CONTRACT_MIGRATION.md` | Preflight y procedimiento de migración; servicio compartido sin migrar ni aceptar. Aceptación humana pendiente. | Pendiente |
| Zereginak!G101 | [Informe](../evidence/CG16.md) | `git show f770932:docs/evidence/CG16.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G104 | [Informe](../evidence/CG23.md) | `git show f770932:docs/evidence/CG23.md` | Escenarios hipotéticos FP/FN, volumen y retención; no ahorro observado ni dimensionamiento aceptado. Aceptación humana pendiente. | Pendiente |
| Zereginak!G105 | [Informe](../evidence/ISOLATED_RUNTIME_20261022.md) | `git show f770932:docs/evidence/ISOLATED_RUNTIME_20261022.md` | Dashboard vivo propio con fixtures sintéticas, KPI/rango/filtros y offline fijo separado. No panel de producción, SLA ni validación de utilidad por operador. Aceptación humana pendiente. | Pendiente |

## Pendientes para completar la entrega

1. Coordinar los [pendientes técnicos](#límites-y-pendientes), sin convertir los resultados incorporados en aceptación del pipeline.
2. Otro miembro debe contrastar los 40 descriptores, ejecutar el procedimiento pertinente y registrar su conclusión y fecha. No se inventan reuniones, defensa ni aprendizaje individual.
3. Confirmar NFS/SMB, ponderaciones y alcance con el docente. ANEXO1 registra 11 semanas frente a ~3 semanas/~45 horas del enunciado; las fechas oficiales requieren confirmación.
4. Revisar [ANEXO4](ANEXO4_CNC_Guard.md) y [ANEXO1](../requisitos/ANEXO1_CNC_Guard.md). Compromisos, acuerdos, firmas y aprobación final siguen pendientes; esta PR no modifica el reparto.
5. Preparar demo/defensa y recoger después evidencia real y aceptación docente. No se afirma entrega en Moodle.

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

`python3 scripts/check_cg25_memory.py` comprueba 40 celdas exactas, estructura/pin de cada fila, enlaces locales/anchors y hashes actuales e históricos. El manifiesto fija los bytes documentales actuales; `historical_snapshot` verifica los bytes de la base original mediante `git show`, sin confundirlos con los actuales. No incluye su propio hash.

`git diff --check BASE HEAD`, inspección del rango completo y Ruff 0.17.1 sobre el verificador afectado completan el control documental. Los checks documentales no repiten las suites de los autores ni prueban servicios/ML. La auditoría actual añade pruebas focales sintéticas de API/replay, registradas aparte; no sustituyen CI o aceptación humana. El registro anterior permanece en `docs-final-reconcile/`; la auditoría actual y sus checks propios están en `rubric-final-audit-20261022/` del taskroot local.

## Auditoría de aceptación del 22/10/2026

La [matriz CG01–CG30 y bloqueos](../rubrica/ESTADO_20261022.md) separa implementación, ejecución del autor, comprobación propia y pendientes humanos. El [guion actual](../demo/README.md) usa la API/replay vigente. No convierte evidencia parcial en criterio aprobado. Las fuentes fijadas al SHA y el corte de issues se conservan en el informe durable local.
