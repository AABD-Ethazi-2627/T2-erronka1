# Resolución de deudas y revisión — 26/10/2026

## Composición y autoridad

Continuación del encargo de trabajar las deudas del informe con agentes.
La composición inicial y su validación están en [integración](20261026-integration.md).
El padre recibió `b7b9c05fc820516f3e1035194503a77b15460aa8`, árbol
`eebae797d2a1d44807eafbf96a2ce5bd77d72ff1`, limpio, en
`kali/integrate-branch-readiness`, y trabaja en ese worktree aislado.
No cambia las ramas autoras ni el checkout original.

Los agentes Codex/GPT-6.1-Sol se repartieron integración, análisis raw de
rendimiento y aceptación/revisión estática. Sus resultados se contrastaron con
fuentes, pruebas e informes reales; no se asumió que un resultado del agente
equivale a aceptación ni a CI. No se han fusionado PR ni desplegado servicios.

## Correcciones posteriores

- Se aplicó el patch de observabilidad, hash
  `174513c6ca2473614fec8b246f01f24fb23b54a93b9f392e4063d5f86bb4f927`,
  y se validó sobre este checkout real. Registra spans monotónicos de ES/worker
  y periodos del export por procesador. No cambia scheduling, batch o ACK.
- Se corrigió el segundo hallazgo independiente: token NiFi ausente ya no causa
  concatenación con `None`; cleanup intenta las paradas independientes, conserva
  el error primario y escribe recibo de fallo. Se detectan también comandos de
  stop no exitosos y errores al persistir el recibo sin reemplazar la excepción
  primaria. Diagnósticos almacenan fases y tipos, no mensajes con secretos.
- Se completó el gate de imágenes: además de identidad/targets exige paquetes
  analizables, clases esperadas y runtime Python/Rust donde corresponde. Verifica
  `ArtifactName` contra el artefacto de build/inventario esperado, y exige ImageID.
  Un llamador de validación de evidencia local puede proporcionar el nombre
  independiente usado en su comando de escaneo mediante `expected_artifact`.
  Los JSON limpios pueden omitir `Vulnerabilities`; UV no necesita Metadata.OS.
- Se concilió el estado CG32 y se añadió banner histórico al informe del 23/10,
  conservando sus cifras y los JSON originales. [Inventario vigente](../../../evidence/DEBT_STATUS_20261026.md).
- Se verificaron de nuevo los 24 hallazgos históricos de secretos mediante
  recálculo de hashes, sin supresiones. [Disposición](../../../evidence/SECRET_TRIAGE_20261026.md).

## Validaciones observadas hasta este hito

- Targeted real: 36 pruebas y 36 subtests pasan con `-W error`.
- El primer intento targeted detectó una fixture que devolvía Mock donde el
  runtime devuelve returncode entero; la comprobación se limitó a códigos
  enteros, conservando el rechazo de nonzero y la prueba correspondiente.
- Ruff detectó cuatro diagnósticos. Se corrigieron imports, estructura de with,
  binding explícito de variable de loop y captura de errores previstos en cleanup.
  Ruff check final de los seis archivos Python afectados: todos pasan; sin noqa
  ni cambios de configuración.
- Gate reforzado probado contra UV/HAProxy/Go del escaneo actual del integrador
  y contra cuatro JSON Trivy reales de CI `40145579428`: API, UV, Wolfi, Filebeat.
  Siete validaciones sin errores. Los cuatro de CI acreditan compatibilidad del
  formato, no un nuevo escaneo del runtime ni revisión vigente de sus avisos.
  Recibo local: `D:/cnc-guard-integration-20261026/parent-report-gate-validation.json`.
- La suite completa pytest posterior a estos cambios terminó exit 0; las suites
  y checks restantes están en curso y se registran con exit individual en
  `D:/cnc-guard-integration-20261026/checks.jsonl`. No interpretar el exit global
  del runner como aprobación: se inspeccionan sus filas y logs por comando.

Suite completa terminada: **677 passed, 3 skipped, 328 subtests passed**;
unittest **385 pruebas, 3 skips**. Ambas con `-W error`, exit individual 0.
Los once checks restantes tienen exit individual 0. Los logs son
`pytest.4.log`, `unittest.4.log` y los once `*.3.log` del recibo privado.
Las fuentes de aplicación de este hito están en
`01a5f2b77ed890fac0d47e525ebced62733a1122`, árbol
`8ba28e6c6727419589e9498f57b6b7d44bb0b03d`. Las pruebas se ejecutaron sobre
esas fuentes antes de confirmar el commit; no se cambiaron después durante
la ejecución. Este añadido posterior solo precisa el recibo documental.
Los tres casos ES no son PASS por estar skipped.

Se detectó una caché Ruff nueva en el worktree C:. Se trasladó de forma
reversible al directorio propio D:, verificando igualdad de seis archivos;
recibo `ruff-cache-relocation.json`. Los próximos comandos Ruff usan
`--no-cache` o `RUFF_CACHE_DIR` en D:. No se alteró configuración global.

Revisión independiente final lanzada sobre `01a5f2b`:
`clientRequestId=btaldea-final-code-review-20261026-v1`, functions.exec cell43,
Codex/GPT-6.1-Sol, solo lectura. Pendiente de devolver resultado; no se presume
aprobación. No hay publicación ni watchers.

## Operación dinámica separada

Se lanzó otro agente T3, Codex/GPT-6.1-Sol, para las nueve builds/escaneos,
pruebas de parches/alcanzabilidad y los tres casos ES. Fuente runtime fijada en
`b7b9c05`; los cambios posteriores del padre no alteran Dockerfiles, parches,
requirements ni fuentes de la API incluidas en esas imágenes.

`clientRequestId=btaldea-runtime-validation-20261026-v1`, functions.exec cell26.
La llamada está pendiente; no se relanza ni se consulta task_status.
Evidencia prevista en `D:/cnc-guard-runtime-20261026`. No hay autorización para
escribir imágenes/cachés en el motor con data-root C:, modificarlo o tocar
contenedores ajenos. No se presume que el runtime ya esté operativo.

## Deudas externas

Projects sigue fallando de forma explícita sin credencial dedicada; no se ha
copiado OAuth, cambiado el gate a skip/pass ni aplicado el Project. Las decisiones
docentes, revisión del euskera, explicación 4/4, ensayo, entrega y recibo siguen
pendientes. El objetivo E2E propuesto y la campaña CG32 tampoco se cierran por
instrumentarlos. PR96 queda fuera, con su trabajo concurrente preservado.
