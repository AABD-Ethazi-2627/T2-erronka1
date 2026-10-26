# Deudas de la composición CNC Guard — 26/10/2026

Este inventario distingue corrección de código, ejecución real y aceptación.
No declara aprobado el proyecto ni convierte documentación en actos humanos.
La referencia anterior es el [informe de ramas](../workflows/pending-review/runs/20261026-branch-readiness.md).

| Deuda | Trabajo efectuado | Cierre pendiente |
| --- | --- | --- |
| Composiciones locales anteriores a seguridad remota | Main `b219398` y CG32 `d892486` incorporados conservando bundle sellado, fixture ML, arreglo Windows y deltas documentales. | Publicación y CI/revisión del head remoto; no equivale a aceptar el proyecto. |
| Gate acepta ausencia de escaneo | Gate más estricto de upstream conservado, regresión final y nueve JSON de builds pasan con identidad/cobertura contrastadas. Conserva JSON limpios válidos sin `Vulnerabilities`, y UV sin OS. | Revisar diagnósticos nuevos en builds futuras; sin nuevas excepciones. |
| Cleanup CG32 oculta fallo primario | Corregido, con regresiones e inspección independiente: paradas independientes, error primario y recibo conservados; cleanup fallido tampoco produce éxito. | Ensayo real de pausa/kill de CG32 separado, no se ha inducido una caída NiFi aquí. |
| Falta observabilidad del ciclo | Spans monotónicos de comprobación ES y worker; el recibo conserva periodos exportados por procesador. No cambia scheduling, batch, ownership ni ACK. | Nuevo piloto para medir esas fases. El export no acredita por sí mismo la configuración observada del servidor. |
| E2E y campaña CG32 | Recalculado el piloto archivado: p95 E2E 55748,094 ms y HTTP 60,320 ms sobre diez eventos. | A/B y campaña reproducible según presupuesto; el objetivo propuesto de 1 s y la carga condicionada de 50/s no se han demostrado. |
| Coincidencias históricas de secretos | [25/25 verificadas como digests de contenido](SECRET_TRIAGE_FINAL_20261026.json) en el escaneo posterior; 24/24 iniciales conservadas, sin supresiones. | Esto no certifica todos los tipos de secreto ni commits futuros. |
| Dependencias Python | Auditoría actual de 90 filas sin errores ni avisos activos en la integración; entorno research separado y estudio sellado intacto. | Conservar regresiones de la rueda local; PyPI no audita sus modificaciones propias. |
| Imágenes y tres casos ES | Nueve builds/escaneos, pruebas de backports/alcanzabilidad y tres verificadores ES pasan; se conservan cuatro avisos raw con disposición. | Sin garantía universal de vulnerabilidades o aceptación industrial; conservar pruebas de los backports. |
| Portabilidad de verificadores ES | Corregida y probada directamente: imagen por ID, socket local/WSL, binds ext4 explícitos, UUID y cleanup por pertenencia. | No requiere ya el adaptador externo histórico. |
| Incidente de almacenamiento | Primer daemon tocó metadatos compartidos en C:; aislamiento corregido y motor original operativo con recuentos previos. | Sin snapshot previo, no se puede probar ni restaurar el delta exacto. No se declara cumplimiento íntegro de D:; incidente conservado. |
| Integridad CG25 | Check final pasa: 193 hashes actuales, 18 históricos intactos y unión del inventario local/upstream. | Revisión humana continúa pendiente; no es una aceptación técnica o académica global. |
| Estado documental contradictorio | El estado CG32 separa piloto original medido de los bloqueos históricos por host. Los recuentos antiguos de imágenes conservan fecha y revisión. | Mantener referencias al informe de ejecución vigente. |
| Projects | Fallo administrativo confirmado del [run programado 40270755905](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/40270755905): tests pasan y falta `PROJECTS_SYNC_TOKEN`. No es CI de PR. | Administrador provisiona credencial dedicada con acceso a ambos Projects; después dry-run y apply autorizado/verificado. No copiar OAuth personal ni convertir el fallo en skip/pass. |
| Rúbrica y equivalencias | Copias y aclaraciones disponibles; clasificación contemporánea y ETA/RUL siguen separadas. | Confirmación docente de versión/pesos, G49/G92/G62, cinco sensores frente a `machine_type` y condiciones definitivas de entrega/defensa. |
| Personas y entrega | Guion y checklist preparados. | Revisión humana del euskera, explicación real de los cuatro integrantes, ensayo, entrega efectiva y justificante. |

## Evidencia de rendimiento

[Descomposición raw y hashes](CG32_TIMING_ANALYSIS_20261026.json): el tramo
descriptivo entre timestamp Kafka y `scored_at` tiene p95 54326,249 ms. Usa wall
clock y no se identifica con una medida de entrada al broker: el raw no conserva
`timestamp_type`. Los percentiles por fase no se suman. No se atribuyen esos
54 s a una sola causa sin spans de proceso, asignación y poll.

El trigger estaba exportado a 2 s y el propietario Kafka a 5 s, con
`max_records=1`/`max_polls=3`. Eso motiva instrumentación y un A/B; no demuestra
que aumentar batch alcance 1 s. Los nuevos spans excluyen arranque/imports de
Python y persistencia/contabilidad final; ese límite queda en su contrato.

## Trabajo concurrente y límites

La [PR96](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/96), inspeccionada
inicialmente en `716c940`, y su continuación PR97 ya están integradas en main
`b219398` y se incorporaron por ese ancestro. No se reemplaza su trabajo ni se
copia su manifiesto sobre el local: se conservan la unión y 193 hashes actuales.
La ausencia
de bundle en su host no desmiente la recuperación local del bundle original:
identidad y disponibilidad se comprueban por host y tres hashes, sin reentrenar.

Las propuestas numéricas E2E/50/s son objetivos de ingeniería, no cifras
docentes ni un SLA industrial confirmado. Se conserva el piloto incumplido y
los avisos experimentales históricos sin repetir fits ni promover candidatos.

No se han aplicado cambios a Projects, fusionado PR, desplegado servicios
compartidos, enviado mensajes a terceros o cerrado issues de aceptación.
