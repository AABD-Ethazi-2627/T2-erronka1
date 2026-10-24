# CG20 API → ES → Kibana, 22/10/2026

Proyecto educativo. Main remoto verificado `3b79c927c909bb0c87fe3f344c2b4bd152f31c61`, árbol `2e7f81c7a09839378e44cccca215b84d516ded8d`.
Worktree manual desde audit-review: `D:/github/_worktrees/t2-cg20-api-kibana-20261022`, rama `test/cg20-api-kibana-20261022`.

Resultado requerido: misma identidad, origen, model_version, scores, alerta, timestamp y destino en respuesta HTTP canónica/ledger, _source ES y consulta/vista real Kibana. JSON, capturas reales, comandos, export vigente, versiones y límites.

Evaluación previa: RUN-FINAL PM y comentario 6342104563 identifican exactamente el hueco; PR76 termina en ES y PR69 representa otros 100 documentos sin scoring. No existe prueba suficiente del mismo evento hasta Kibana. No se suman ambos labs.

Autorizado: lab nuevo acotado, imágenes locales, Filebeat/Kafka/NiFi + worker producto/API con stubs sintéticos/ES9.5.4/Kibana9.5.4. Binds y archivos propios D:, puertos aleatorios loopback, inventarios antes/después y comprobación de recursos preexistentes. PR draft contra main para evidencia nueva. No cerrar issue antes de revisión del padre; sin comentarios, menciones, requests review, CI manual, watch o polling CI.

Preservar: nueve contenedores automatic-graph detenidos, todos sus datos/sellos, broker histórico y su capa única, cuatro volúmenes históricos Kibana, SMB/OT/infra compartida. Ningún start/exec/write sobre ellos. Inventario inicial: 111 contenedores, 78 volúmenes, 11 redes, 60 imágenes; solo cuatro contenedores ajenos activos.

Modelo: RiskDouble/AnomalyDouble del test existente, sin bundle/modelos reales/inferencia real/train/testfinal. Uvicorn y ledger de producto. NiFi ExecuteStreamCommand programa scripts.run_automatic_graph; no driver externo de ACK.

JVM: se reutiliza la solución demostrada en el lab previo para ES9.5.4 con rootfs solo lectura: filesystem POSIX nuevo respaldado por imagen ext4 propia D:, montado en carpeta propia D: y bind a /lab/runtime y /tmp internos del contenedor. ES y su agente JVM crean temporales internos que requieren semántica POSIX, y sus subprocesos usan /tmp aun fijando java.io.tmpdir. Excepción expresamente autorizada por el usuario; ningún /tmp del host ni datos históricos. Se conserva imagen y montaje al entregar.

Ejecución: `agent-ps <taskroot>/launch.ps1 <nombre-unico-log> TASKROOT/<script.py> <fase>`. launch fija todos los temp/cache a D: y usa Python3.12 existente de Fedora, sin escrituras de bytecode. Comandos exactos y exit codes en commands.jsonl y docker-commands.jsonl. Fallos se conservan y se diagnostican antes de repetir.

No se atribuyen SLA/HA/exactly-once global, carga sostenida, aceptación docente o producción. La captura nueva no transforma pruebas previas en ejecución propia.
