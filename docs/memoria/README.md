# Memoria CNC Guard y trazabilidad CG25/CG27/CG30

Borrador reconciliado el 21/10/2026 para revisión del equipo y docente. Cubre documentalmente 40 descriptores; no acredita nota, aceptación humana, firmas ni entrega final.

## Fuentes y atribución por sección

- [Enunciado](../../ENUNTZIATUA.md): fases de pipeline, entrenamiento e inferencia; «Entregablea Orokorra» y «Demo Aurkezpena» describen artefactos y defensa de 10 minutos. Los pesos de fase y de módulo son ejes distintos.
- [Fuente docente exacta](../rubrica/fuente.json), Zereginak, columna G: 40 descriptores, celdas y hash del Excel local; [interpretación](../rubrica/OBJETIVOS_Y_ETAPAS.md). No se ha cotejado la versión online ni se asigna una nota.
- ANEXO4.docx docente local: «Erronkaren izena», «BEHIN BETIKO PROPOSAMENA» y «Taldeak aurrera eramatea erabaki duen proposamena» dan la estructura del [borrador adaptado](ANEXO4_CNC_Guard.md). Ruta y hash del original en el [manifiesto](manifest.json); el original no se redistribuye ni se vuelve a inspeccionar aquí.
- [CG30](../evidence/CG30.md#versiones-y-decisiones-incorporadas): argumentación y versiones basadas en artefactos existentes. Se mantiene su atribución docente previa; no se ha hecho investigación nueva ni se han revalidado los PDF.
- Resultados, comandos y límites se atribuyen a sus informes versionados. Esta aportación reconcilia documentación y ejecuta el verificador documental; no repite sus pruebas técnicas. La autoría técnica consta en Git. El equipo debe revisar y reconocer sus contribuciones reales: una asignación no prueba actividad individual.

## Alcance y decisiones técnicas

Snapshot documental original: PR42 `e5faf015cc16e2044d25ab59c1ec30c32222d889`, árbol `040546fdb917fd65641812d80f643ef4b2ca1fe0`, incorporado por merge normal a PR48. Sus hashes se conservan en el manifiesto. La composición PR65 usa ahora PR42 `53f342df39ff7e8d744186c22d61b456bb8f6d7a`, árbol `5383a7edf91c89200ed98d32601cedaf75720308`, con PR62 y PR64 incorporadas. PR42 permanece abierta hacia main; integración en esa rama no equivale a merge en main ni aceptación humana.

Solo el CSV reducido AI4I suministrado, de **8000 filas**, alimenta el alcance activo. El [split por índices](../evidence/CG04_split_membership.json) es **5600 fit / 1200 validación de desarrollo / 1200 excluidas**, disjuntas y con cobertura completa; esas últimas filas pertenecen al test previamente inspeccionado y no son un test final independiente nuevo. El ejercicio PR43 6400/1600 es histórico: no sustituye el split activo ni autoriza promoción. [CG04](../CG04_ENVIRONMENT.md) documenta la separación y la compatibilidad del entorno.

RF clasifica **estado contemporáneo**, IF expresa rareza separada. Cinco sensores y `machine_type` entran al estimador; timestamp/ID son trazabilidad. NiFi debe retirar etiquetas y CSV crudo antes de `/predict`. No se predicen fechas, ETA, RUL ni averías industriales a 24 horas. PR40/41 y la simulación estacional permanecen etiquetadas como investigación histórica fuera de entrega.

Filebeat → Kafka → NiFi → FastAPI → NiFi → Elasticsearch → Kibana describe el recorrido de laboratorio. El archivo CG15 y su adaptador Kafka ya están implementados e integrados; no acredita archivado continuo de ese recorrido ni su E2E v4. Una persona decide el mantenimiento; no se controla una CNC física. La discrepancia NFS del enunciado frente a SMB requiere aclaración docente.

## Resultados incorporados

Los resultados siguientes están registrados en las fuentes indicadas. «Integrado» describe un merge de código; no expresa aceptación humana o de todos los criterios asociados.

| Frente | Evidencia y resultado registrado | Límite vigente |
|---|---|---|
| Clasificación y split | [Alcance v4](../evidence/CG17_CURRENT_STATE_SCOPE.md), [membresía](../evidence/CG04_split_membership.json) y [CG10](../evidence/CG10.md): TP=32, FN=9, FP=9, TN=1150, total 1200; recall/precision 32/41=78,05%. | **Validación reutilizada** para desarrollo/selección de umbral. No es test final independiente ni garantiza generalización industrial; no se recalculan métricas aquí. |
| CG15 durable, PR46 | [Archivo](../evidence/CG15_ARCHIVE.md): Bronze de bytes originales, Parquet, ledger, fsync→commit→ACK, detección de corrupción y replay; compatibilidad Parquet 18.1.0↔23.0.1 conservando bytes. Revisión independiente favorable al delta y merge verificados. | Disco local y fallos controlados. No prueba pérdida eléctrica, durabilidad de hardware ni transporte distribuido. |
| Adaptador Kafka, PR58/60 | [CG15 Kafka](../evidence/CG15_KAFKA_20261021.md): 17 tests focales; loopback con librdkafka mock 2.16.0, 3 envíos=1 guardado+1 duplicado+1 rechazado, commit/replay 3, hashes conservados y SIGTERM exit0. PR60 añade manejo de JSON profundo. | Mock de protocolo, **no Apache Kafka 3.7 real**. TLS/SASL, operación del clúster, namespaces/retención y aceptación de transporte pendientes. |
| CG21, PR45 | [Harness durable](../evidence/CG21.md) y [JSON](../evidence/CG21_durable_20261021.json): 5=3 accepted+2 rejected+0 pending; 2 únicas, 1 duplicada. Cortes `os._exit(73)` en after_write/before_commit/after_commit y replay conservan Parquet. | Fuente SQLite local y procesos controlados; no offsets Kafka reales, HA o caída distribuida. El [fixture anterior](../evidence/CG21_fixture.json) se conserva como histórico. |
| CG23, PR47 | [Protocolo](../evidence/CG23.md), [18 mediciones](../evidence/CG23_repeated_20261021.json): 3 repeticiones × 25/100/250 eventos/s × 1/4 consumidores, 2250 entregas ofrecidas sin replay, espera sintética 10 ms. Revisión favorable acotada al microbenchmark. | In-memory/JSONL buffered sin fsync; no inferencia, Kafka/NiFi/ES ni capacidad sostenible del pipeline. Percentiles por corrida, CPU incluye replay y RSS es máximo del intérprete. Los escenarios de coste/retención son hipotéticos. |
| Scoring replay, PR61 | [Contrato](../SCORING_REPLAY_CONTRACT.md): respuesta canónica SQLite persistida antes del 200, replay estable de `scored_at`, 409 ante identidad con otro contenido y fallo cerrado. [Evidencia PR61](../evidence/PR61_ES_FIXTURE_IDENTITY.md): 237 tests y 3 skips por intérprete, 11 de replay y 2 ES focales OK en 3.11/3.12. | Dobles deterministas, SQLite/archivo reales; no modelos de entrega ni NiFi E2E. Ledger local compartido por workers, no SQLite sobre SMB/NFS ni garantía entre réplicas independientes. Migración/importación de respuestas previas no implementada. |
| SMB offline, PR63 | [Resultados](../evidence/CG05_CG29_OFFLINE_20261021.md), [protocolo](../SMB_FILEBEAT_LAB.md): 19 tests por pasada, dos pasadas por 3.11/3.12; detección de descargas cortas/cambiantes y formato de líneas, publicación y claves de replay. Revisión independiente favorable al delta offline. | Dobles de subprocess y oráculo, **sin SMB/Filebeat/registry/Kafka reales**. Mutación de igual tamaño/prefijo estable exige protocolo del productor. El nombre publicado no tiene garantía demostrada frente a corte eléctrico. |
| Panel, contrato ES y demo, PR49–56 | [CG24](../evidence/CG24_2026-10-21.md), [render](../evidence/CG19_render_2026-10-21.md), [contrato/migración ES](../evidence/ES_V4_CONTRACT_MIGRATION.md), [ensayo CG26](../evidence/CG26_REHEARSAL.md). | Evidencia offline/local o ES desechable según informe; no demuestra Kibana real actual, migración del servicio compartido, seguridad industrial ni defensa humana. |

El [índice de 19/10](../evidence/INDEX_2026-10-19.md) conserva ensayos pre-v4 como históricos. PR62 ya está incorporada en la base PR42 `53f342d`; PR65 añade el worker durable opt-in y [corrige recibos y validación HTTP](../evidence/DURABLE_PIPELINE_FIX_R2_20261021.md). Esta implementación y sus pruebas locales no acreditan cableado del grafo NiFi activo ni streaming Apache Kafka/NiFi E2E. La revisión padre de PR65 sigue pendiente.

## Límites y pendientes

- **Kafka Python 3.11:** el registro histórico SMB tenía 218 avisos del primer import. PR64 los corrige con el wheel fijado `3.0.11+cncguard.1`, ya incorporado en `53f342d`; véase [evidencia](../evidence/KAFKA311_WARNING_FIX_20261021.md). Los logs históricos no cambian y sus fallos no se presentan como passes nuevos.
- **Windows:** la [matriz de compatibilidad](../evidence/STARLETTE_TESTCLIENT_20261021.md) conserva 12 errores POSIX y UserWarning de joblib/loky por WMIC ausente. No se han resuelto ni revalidado mediante esta aportación documental.
- **Runtime y migración:** faltan Apache Kafka real, Filebeat/registry/SMB propios, confirmación del productor, Kibana actual, E2E NiFi v4 y conciliación de colas/índices/identidades/respuestas previas. No se ha aplicado la migración ES, el pin RESTORE ni el ledger a servicios compartidos.
- **Personas y entrega:** pendientes revisión del padre, contraste de otro miembro, explicación individual CG30, demo/defensa, acuerdos ANEXO1/ANEXO4, firmas y canal Moodle. La información del usuario sobre tutor no sustituye un acta o aceptación textual archivada. No se cierran issues.

**Implementado**: código presente. **Probado local**: ejecución fechada de un SHA/entorno con límites. **CI**: checks del SHA concreto. **Integrado**: merge comprobado al destino indicado. **Aceptación humana**: persona, fecha y conclusión reales. PR48 solo aporta reconciliación y validación documental; su CI automático y revisión del padre quedan pendientes. No hay despliegue ni entrega final.

## Matriz de los 40 descriptores

Texto exacto por celda en fuente.json. Artefactos fijados a la base integrada `e5faf015cc16e2044d25ab59c1ec30c32222d889`; CG30 se amplía documentalmente en esta PR y el comando muestra su antecedente en base. Cada informe contiene su procedimiento y resultado técnico fechado. El comando siguiente inspecciona ese registro sin ejecutar servicios. El resultado de CG25 es enlace/hash comprobado; no repite pruebas técnicas. Aplicar el alcance activo anterior a todas las filas, especialmente a experimentos temporales históricos.

| Criterio | Artefacto en base | Comando de inspección | Resultado registrado y límite | Revisor y fecha |
|---|---|---|---|---|
| Zereginak!G5 | [Informe](../evidence/CG30.md) | `git show e5faf01:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G10 | [Informe](../evidence/CG30.md) | `git show e5faf01:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G14 | [Informe](../evidence/CG23.md) | `git show e5faf01:docs/evidence/CG23.md` | 18 corridas de microbenchmark local; no latencia E2E ni capacidad Kafka/NiFi/ES. Aceptación humana pendiente. | Pendiente |
| Zereginak!G16 | [Informe](../evidence/CG24_2026-10-21.md) | `git show e5faf01:docs/evidence/CG24_2026-10-21.md` | Análisis previo por machine_type, sin certificación CE ni dictamen jurídico. Aceptación humana pendiente. | Pendiente |
| Zereginak!G17 | [Informe](../evidence/CG24_2026-10-21.md) | `git show e5faf01:docs/evidence/CG24_2026-10-21.md` | Sin datos de operadores; revisión legal humana pendiente. Aceptación humana pendiente. | Pendiente |
| Zereginak!G19 | [Informe](../evidence/CG24_2026-10-21.md) | `git show e5faf01:docs/evidence/CG24_2026-10-21.md` | Laboratorio acotado; no acreditación de exposición compartida segura. Aceptación humana pendiente. | Pendiente |
| Zereginak!G20 | [Informe](../evidence/CG24_2026-10-21.md) | `git show e5faf01:docs/evidence/CG24_2026-10-21.md` | Análisis por subgrupo; sin validación de despliegue compartido. Aceptación humana pendiente. | Pendiente |
| Zereginak!G23 | [Informe](../evidence/CG30.md) | `git show e5faf01:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G24 | [Informe](../evidence/CG30.md) | `git show e5faf01:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G31 | [Informe](../evidence/CG30.md) | `git show e5faf01:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G32 | [Informe](../evidence/CG30.md) | `git show e5faf01:docs/evidence/CG30.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G36 | [Informe](../evidence/CG04_split_membership.json) | `git show e5faf01:docs/evidence/CG04_split_membership.json` | Dataset activo de 8000 filas; split 5600/1200/1200 documentado en CG04, sin test final nuevo. Aceptación humana pendiente. | Pendiente |
| Zereginak!G38 | [Informe](../evidence/CG08.md) | `git show e5faf01:docs/evidence/CG08.md` | Evidencia versionada. Ablación/SMOTENC probados; interpretación física no causal. Aceptación humana pendiente. | Pendiente |
| Zereginak!G39 | [Informe](../evidence/CG10.md) | `git show e5faf01:docs/evidence/CG10.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G41 | [Informe](../evidence/CG28.md) | `git show e5faf01:docs/evidence/CG28.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G45 | [Informe](../evidence/CG10.md) | `git show e5faf01:docs/evidence/CG10.md` | TP32/FN9/FP9/TN1150 en validación reutilizada; no test final independiente. Aceptación humana pendiente. | Pendiente |
| Zereginak!G46 | [Informe](../evidence/CG21.md) | `git show e5faf01:docs/evidence/CG21.md` | Cortes de procesos y replay sobre CG15 durable, fuente SQLite; no HA ni recuperación distribuida. Aceptación humana pendiente. | Pendiente |
| Zereginak!G49 | [Informe](../evidence/CG05_CG29_OFFLINE_20261021.md) | `git show e5faf01:docs/evidence/CG05_CG29_OFFLINE_20261021.md` | 19 tests offline por pasada/versión; SMB, registry y Filebeat reales pendientes; NFS sin confirmar. Aceptación humana pendiente. | Pendiente |
| Zereginak!G52 | [Informe](../evidence/CG30.md) | `git show e5faf01:docs/evidence/CG30.md` | Evidencia versionada. Comparación tecnológica y defensa por revisar. Aceptación humana pendiente. | Pendiente |
| Zereginak!G55 | [Informe](../evidence/CG28.md) | `git show e5faf01:docs/evidence/CG28.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G60 | [Informe](../evidence/CG08.md) | `git show e5faf01:docs/evidence/CG08.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G61 | [Informe](../evidence/CG28.md) | `git show e5faf01:docs/evidence/CG28.md` | Evidencia versionada. Paradoja de parada programada requiere acuerdo; no reetiquetada. Aceptación humana pendiente. | Pendiente |
| Zereginak!G62 | [Informe](../evidence/CG08.md) | `git show e5faf01:docs/evidence/CG08.md` | Evidencia versionada. groupby en observaciones simuladas y laboratorio temporal separado; no historial físico. Aceptación humana pendiente. | Pendiente |
| Zereginak!G65 | [Informe](../evidence/CG19_2026-10-21.md) | `git show e5faf01:docs/evidence/CG19_2026-10-21.md` | Panel offline, render y contraste versionados; no Kibana/ES real actual ni utilidad aceptada por operador. Aceptación humana pendiente. | Pendiente |
| Zereginak!G66 | [Informe](../evidence/CG18.md) | `git show e5faf01:docs/evidence/CG18.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G68 | [Informe](../evidence/ES_V4_CONTRACT_MIGRATION.md) | `git show e5faf01:docs/evidence/ES_V4_CONTRACT_MIGRATION.md` | Contrato/mapping v4 corregido y ensayado en ES desechable; migración del servicio compartido pendiente. Aceptación humana pendiente. | Pendiente |
| Zereginak!G71 | [Informe](../evidence/CG19_render_2026-10-21.md) | `git show e5faf01:docs/evidence/CG19_render_2026-10-21.md` | Render offline y contratos de consulta; no aceptación del dashboard Kibana real actual. Aceptación humana pendiente. | Pendiente |
| Zereginak!G72 | [Informe](../evidence/CG19.md) | `git show e5faf01:docs/evidence/CG19.md` | Propuestas de decisión; ninguna orden física ni mantenimiento real ejecutado. Aceptación humana pendiente. | Pendiente |
| Zereginak!G77 | [Informe](../evidence/CG15_ARCHIVE.md) | `git show e5faf01:docs/evidence/CG15_ARCHIVE.md` | Bronze/Parquet/ledger, fsync→commit→ACK y replay; Kafka adapter en CG15_KAFKA, broker real pendiente. Aceptación humana pendiente. | Pendiente |
| Zereginak!G80 | [Informe](../evidence/CG23.md) | `git show e5faf01:docs/evidence/CG23.md` | Concurrencia 1/4 con espera sintética y buffer; no carga sostenida del pipeline ni inferencia medida. Aceptación humana pendiente. | Pendiente |
| Zereginak!G85 | [Informe](../evidence/CG12.md) | `git show e5faf01:docs/evidence/CG12.md` | Evidencia versionada. Mononodo, sin ensayo de clúster. Aceptación humana pendiente. | Pendiente |
| Zereginak!G87 | [Informe](../evidence/CG19_render_2026-10-21.md) | `git show e5faf01:docs/evidence/CG19_render_2026-10-21.md` | Capturas/render offline y contraste; contadores de Kibana del 19/10 son históricos pre-v4. Aceptación humana pendiente. | Pendiente |
| Zereginak!G90 | [Informe](../evidence/CG21.md) | `git show e5faf01:docs/evidence/CG21.md` | Tres cortes locales de proceso y replay conciliado; sin reinicio distribuido ni corte eléctrico. Aceptación humana pendiente. | Pendiente |
| Zereginak!G92 | [Informe](../evidence/CG16.md) | `git show e5faf01:docs/evidence/CG16.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G95 | [Informe](../evidence/CG21.md) | `git show e5faf01:docs/evidence/CG21.md` | Harness durable incorporado; scoring replay en PR61. NiFi PR62 sigue separado y pendiente de integración/E2E. Aceptación humana pendiente. | Pendiente |
| Zereginak!G96 | [Informe](../evidence/CG21.md) | `git show e5faf01:docs/evidence/CG21.md` | 5=3 aceptadas+2 rechazadas+0 pendientes, 2 únicas/1 duplicada; fuente SQLite, no offsets Kafka reales. Aceptación humana pendiente. | Pendiente |
| Zereginak!G100 | [Informe](../evidence/ES_V4_CONTRACT_MIGRATION.md) | `git show e5faf01:docs/evidence/ES_V4_CONTRACT_MIGRATION.md` | Preflight y procedimiento de migración; servicio compartido sin migrar ni aceptar. Aceptación humana pendiente. | Pendiente |
| Zereginak!G101 | [Informe](../evidence/CG16.md) | `git show e5faf01:docs/evidence/CG16.md` | Evidencia versionada. Explicación y aceptación del equipo pendientes. Aceptación humana pendiente. | Pendiente |
| Zereginak!G104 | [Informe](../evidence/CG23.md) | `git show e5faf01:docs/evidence/CG23.md` | Escenarios hipotéticos FP/FN, volumen y retención; no ahorro observado ni dimensionamiento aceptado. Aceptación humana pendiente. | Pendiente |
| Zereginak!G105 | [Informe](../evidence/CG19_2026-10-21.md) | `git show e5faf01:docs/evidence/CG19_2026-10-21.md` | Evidencia offline y consultas; utilidad/aceptación por operador pendientes. Aceptación humana pendiente. | Pendiente |

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

`git diff --check BASE HEAD`, inspección del rango completo y Ruff 0.17.1 sobre el verificador afectado completan el control documental. Estos checks no repiten las pruebas técnicas de las fuentes, no prueban servicios/ML ni sustituyen CI o aceptación humana. El informe de ejecución de esta reconciliación queda en `docs-final-reconcile/` del taskroot local.
