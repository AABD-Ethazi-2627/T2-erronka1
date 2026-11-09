# Recuperación WIP para continuar en otro PC — 2026-11-08

Goal: preservar y publicar el trabajo autorizado del mismo B-taldea, rama
`integration/complete-project-20261103`, PR119. Este commit es recuperación WIP;
no es aceptación, merge ni despliegue. No se crearon agentes ni checkouts.

## Estado y exclusión

HEAD previo `fe4dd914ad5c88cdb064d78cafbecc960133d8d3`; remoto previo
`6d67bc2ec72d931486174b906654bcc089250cba`, 0 detrás/53 delante.
El handoff bloqueado anterior está preservado fuera del repo en
`/home/tears/.cache/cnc-recovery/20261108T095847Z/HANDOFF_BLOCKED.md`.

El escritor `/root/cnc_runtime_closure`, sesión nativa
`01a1b096-7a74-71f0-a3d5-6453e43d9f97`, terminó normalmente a
2026-11-08T10:00:27.846Z (`task_complete`). La API nativa interrupt respondió
`live agent path /root/cnc_runtime_closure not found`. Sus cinco hashes finales
coinciden con disco. Inventarios repetidos de los 49 archivos no muestran deriva.
No se envió ninguna señal. El dueño de sus descriptores es PID1291571,
`codex app-server`, compartido con otras sesiones: **no se mató**. Descriptor y
lock abiertos por un servidor compartido no prueban una ejecución activa.
Se capturó inventario de procesos con cwd del worktree; el proceso Claude
PID1370150 tiene sesión d0911adb-c045-484f-949f-3e4374314e61, último end_turn
2026-11-06T13:23:27.392Z, y tampoco se tocó.
El T3 original permanece ordinal64 interrupted, ordinal65 cancelled,
activeRunId null y pendingRequestCount0; no se reanudó.

## Preservación y cambios

Nueva copia externa: `/home/tears/.cache/cnc-recovery/20261108T100059Z`:
49 archivos /353729 bytes; TAR SHA256
`97adfe4183d080af5aa9a74ef112497d3092d98b27519635d737ca9d56ebcfa4`.
Contiene archivos, inventario hash/mtime, patches tracked/index y copia del
índice original. Se mantienen ambas copias anteriores 095559Z y095847Z,
los dos stashes originales de main y todos los originales.

Los 49 archivos recuperados (10 tracked modificados,39 nuevos) se enumeran en
[RECOVERY_CAPTURE_20261108.json](RECOVERY_CAPTURE_20261108.json): preparación
ES OTel, probes Java,27 POM oficiales, perfil Jackson y guards de perfil CNC,
Dockerfile opt-in y pruebas. El máximo es51874 bytes; no incluye JARs/binarios,
modelos ni secretos. Stage mediante lista explícita; sin add -A ni reset.

## Verificado en esta recuperación

- `.venv/bin/python -m pytest -q tests/test_es_otel_qualification.py tests/test_nifi_runtime_profile.py`: **75 passed**, última ejecución1.49s.
- `ruff check scripts/nifi_runtime_profile.py tests/test_nifi_runtime_profile.py tests/test_es_otel_qualification.py deploy/images/elasticsearch-patches/otel-qualification`: pasa. El intento inicial `.venv/bin/ruff` falló por ausencia del ejecutable; se usó `/usr/bin/ruff` sin instalar nada.
- `git diff --check`: pasa; JSON/XML parsean y los27 POM coinciden con sus pins/declaraciones.
- `seal_inventory.seal()` reproduce exactamente `inventory-result.json` desde el archivo local sellado `inventory-01-verified`; TAR compacto coincide con SHA9187e9927179c9c5ec7c5e8530a7f0c1bf3b086aad6e087f460c39fdef6320f1. Es reproducción local de evidencia histórica, no nueva ejecución en Benten.
- Gitleaks de los53 commits devuelve27 alertas; scan de los49 archivos recuperados devuelve42. Todas revisadas en sus versiones y contexto: SHA256 de artefactos/event_key, sin credenciales. Clasificación por archivo/línea en JSON adjunto. Exit1 se conserva como detección bruta; no se añadieron allowlists ni supresiones. Un scan preliminar del directorio de backups no sustituye el posterior scan de archivos extraídos.
- Políticas global/integración, MKDL, verification-loop, handoff-report y procedimientos image-remediation/pending-review consultados. Skill `workflow-records` no localizado en catálogo ni índices/árboles locales consultados; se deja registro durable en el workflow existente sin atribuirle una skill no leída.

## Pendiente y límites

Los15 findings NiFi referidos por el handoff anterior no se reescanearon ni
repararon. Jackson95 sigue con calificación limitada; Jetty10 y su control
negativo pendientes. H1/H2/M1/M2 tienen guards/pruebas locales; falta baseline
independiente cold OCI, evidencia real de conservación y M3 antes de restaurar
estado persistido. El Dockerfile CNC sigue opt-in y bloqueado por baseline null;
no se debe presentar como construible ni aprobado.

ES inventario sellado no prueba loader/APM/entitlements. Probes Java aún no
compilados/ejecutados aquí; los27 POM son declaraciones, falta oracle Maven
mediado real. No hay nueva suite completa, Docker, build/scan, CG32, integración,
CI ni aceptación humana. `replacement:null`, `runtime_approved:false` y gate
**cero findings** se mantienen. La revisión Muse anterior no se repitió.

Fuera de publicación quedan exclusivamente copias externas, índice original,
stashes, logs/reportes crudos, sesiones y archivo compacto de prueba local
`/home/tears/.cache/cnc-benten-vm-20261105/es-otel-qualification-20261106/inventory-01-verified/`.
No queda fuente legítima recuperada excluida intencionadamente.

## Continuación exacta

1. Verificar `git ls-remote origin refs/heads/integration/complete-project-20261103` contra `git rev-parse HEAD` del commit publicado; recibo y PR/checks actuales se guardan fuera del repo tras push en la copia100059Z. Los checks antiguos no validan este WIP.
2. En el PC potente usar una carpeta independiente y nueva, nunca `review/pending-20261023`:

```powershell
git clone --single-branch --branch integration/complete-project-20261103 https://github.com/AABD-Ethazi-2627/T2-erronka1.git CNC-Guard-integration
cd CNC-Guard-integration
git rev-parse HEAD
```

Comparar SHA con el recibo remoto antes de trabajar. La prueba compacta local
externa debe transferirse por separado si se necesita reproducirla allí;
verificar su SHA antes de usarla. Conservar el árbol ejecutado89f58fc.
3. Continuar desde `deploy/images/elasticsearch-patches/otel-qualification/NEXT_PHASE.md` bajo reserva y gates existentes; congelar nueva fuente por separado. CNC: capturar baseline cold independiente antes de probar preparación. NiFi: resolver findings y repetir controles negativos y calificación real.
4. CI/reviews se consultan separadamente; no merge/deploy ni aceptación mientras falte evidencia. No reducir6GiB/20GiB ni seguridad, no campañas pesadas en Lenovo ni cambios a servicios Benten.
