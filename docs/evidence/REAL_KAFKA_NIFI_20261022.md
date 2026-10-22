# CG14/CG15: laboratorio real Kafka/NiFi del 22 de octubre de 2026

Estado: validación local del alcance descrito abajo. Revisión independiente del
padre, CI del SHA publicado, aceptación humana y merge pendientes.

La corrección posterior de almacenamiento y el ensayo **nuevo** de recreación
están en [KAFKA_VOLUME_RECREATE_20261022.md](KAFKA_VOLUME_RECREATE_20261022.md).
Este informe conserva la evidencia histórica de restart del mismo contenedor.

Base remota verificada antes y después del ensayo:
`8caf98962175fabcf13fbc1584dc890cf4f0135f`, árbol
`82a69eba2754045619a2c2d218473605183bb9c3`, PR42
`feat/17-maintenance-planner`. Clon existente `audit-review`, rama propia
`feat/real-kafka-nifi-lab-20261022`. Conservados los untracked previos `.audit/`
y `docs/workflows/pr-issue-audit/`; no se ejecutó Ruff sobre ellos como gate del
producto. FedoraLinux-43 informa Fedora 44; Python 3.11.15/3.12.15.

## Defectos reproducidos y corregidos

1. **REAL-KAFKA37-APIVERSIONS-1, P1, confirmado.** El wheel local `.1` enviaba
   `3.0.11+cncguard.1` como `client_software_version`. Kafka 3.7.2 devuelve
   `INVALID_REQUEST` (42), y el cliente no completa bootstrap. El patrón de
   [Kafka 3.7.2](https://github.com/apache/kafka/blob/3.7.2/clients/src/main/java/org/apache/kafka/common/requests/ApiVersionsRequest.java#L53)
   excluye `+`. El wheel `.2` conserva su identidad PEP 440 y sustituye `+` por
   `-` en los defaults de conexión **y gestor**. El cambio del gestor es
   necesario: prevalece sobre el default de la conexión. Pin, lock, provenance,
   licencia y reproducción actualizados. Los 108 JSON del protocolo siguen
   idénticos, y RECORD se verifica íntegro.
2. **REAL-NIFI212-IMPORT-1, P1, confirmado.** La importación del export staged
   fallaba con STOPPED en puertos y, después, con campos nulos en processors y
   conexiones. Se usa DISABLED, se incluyen `bulletinLevel`,
   `propertyDescriptors`, `labelIndex` y defaults explícitos del formato.
   Además, PRIMARY es inválido para processors con entrada; se usa ALL con una
   tarea por processor. Los primeros imports parciales permanecen detenidos en
   el laboratorio propio. El export final se importó/exportó limpio: 2
   processors, 6 conexiones y 5 puertos, todos DISABLED.

No se relajaron validadores, recibos, precondiciones, offsets ni reglas CI.

## Servicios y aislamiento

Apache Kafka **3.7.2**, Apache NiFi **2.12.0** y Elasticsearch **9.5.4** reales.
ES ya existía; Kafka/NiFi se descargaron desde las imágenes oficiales
`apache/kafka:3.7.2` y `apache/nifi:2.12.0`. Tamaños locales descomprimidos:
624.992.819 y 2.407.879.264 bytes. IDs, RepoDigests y tamaños completos están en
los inventarios. Orígenes: [Kafka Docker](https://kafka.apache.org/37/getting-started/docker/)
y [NiFi Docker](https://hub.docker.com/r/apache/nifi/tags).

Etiqueta exclusiva `t2.real.run=t2-real-20261022-0937`; tres contenedores con
límites de CPU/RAM, volúmenes propios y puertos publicados únicamente en
127.0.0.1: 19372 (Kafka), 19281 (ES) y 19282 (NiFi). La API fixture usa
127.0.0.1:19283 y la interfaz de su bridge propio para NiFi. La primera red
interna no publicaba puertos; se añadió otro bridge propio, sin modificar
redes existentes. No hay acceso a SMB/OT, NiFi compartido ni RESTORE original.

Se reutilizó el Docker de la distro existente: `/var/lib/docker`, datos del
worker en `/home/Fedora/t2-real-lab-20261022`, evidencia en D:. La distribución
está registrada bajo `C:\Users\unaiu\AppData\Local\wsl\{8a489b57-18f3-4603-b97a-9525d61c7794}`;
no se ha trasladado la distro ni se afirma que su VHDX esté en D:.

El inventario posterior a la nueva restricción de temporales detectó que el
`log.dir` efectivo de Kafka era `/tmp/kafka-logs` en su capa escribible: el
volumen montado en `/tmp/kraft-combined-logs` no era ese destino. No se ha
eliminado ni recreado el contenedor. Por tanto, la persistencia observada es
tras **restart del mismo contenedor**, no tras recreación ni prueba de ese
volumen. Los auxiliares de Java/NiFi/ES bajo `/tmp` se inventariaron también.
La instrucción nueva se aplicó al trabajo restante: sin repetir pruebas ni
arrancar servicios, TMPDIR/TEMP/TMP por proceso apuntan a `process-temp` en el
taskroot de D:. No queda necesidad de `/tmp`; no se movieron ni borraron
datos existentes. Paths exactos y atribuciones pendientes se conservan en
`temporary-inventory.json` y `TEMPORARY-SPACE-HANDOFF.md` del directorio local
de evidencia. Los nombres temporales eliminados por unittest no se habían
registrado y no se reconstruyen por conjetura.

La API es `scoring.score_api.create_app` servida por Uvicorn/HTTP real con
ledger SQLite y modelos **sintéticos en memoria**. No se entrenó, cargó un
modelo de entrega ni evaluó testfinal. Los fallos HTTP controlados se declaran
en los scripts fixture. Kafka, NiFi, CG15/Parquet y ES no son mocks.

## Resultados funcionales

| Escenario Kafka | Resultado observado |
|---|---|
| Dos CSV iguales + CSV/UTF-8 inválidos | 2 completos con IDs distintos, 2 rechazos durables; commit 4 |
| ES bloqueado para escritura | Sin commit; CG15 conserva ambos recibos; al recuperar, commit 1 sin nueva inferencia |
| Ruta archive obstruida | Sin commit; obstrucción preservada fuera de la ruta; replay completa con la misma respuesta |
| Respuesta API perdida tras su commit | Timeout y cuarentena durable, sin commit Kafka; replay usa ledger API |
| Falta de cabeceras de provenance | Bloqueo sin commit; sólo respuesta canónica reconocida permite recuperación |
| HTTP 422 explícito de fixture | Raw/cuarentena durables y rechazo, commit 1; no recibo CG15 ficticio |
| Terminación abrupta antes de done | Exit 86, offset sin confirmar; proceso nuevo completa con mismos objetos |
| Terminación abrupta antes de ack | Exit 86, offset sin confirmar; replay verifica destinos y confirma 1 |

En cada recuperación se comprobaron offsets del broker, IDs, estados del
journal, recibos CG15 `stored`/`duplicate`, bytes Parquet y `_source` exacto ES.
Un error del harness que esperaba archivo para un rechazo terminal se corrigió;
no se modificó la semántica del producto. Se acortó a 10 s la sesión del
consumidor **del harness** para que un proceso muerto no mantuviera el grupo
durante los polls acotados de su sucesor. No cambió el timeout del producto.

NiFi ejecutó el puente staged con un CSV válido y otro inválido: originales
retenidos, dos receipts `source_ack=false`, dos recibos CG15 almacenados y
provenance real. Un driver externo de laboratorio conservó los bytes y
coordenadas Kafka y confirmó offset 2 sólo después de verificar esos destinos.
**Ese driver es cableado del laboratorio; no es un ConsumeKafka del producto.**
El puente NiFi sigue sin ser dueño del offset y el export versionado no
configura ES. La ruta Kafka directa anterior sí exige ES antes del commit.

Un segundo ensayo cerró también la ruta **combinada con ES obligatorio**:
Kafka real → driver staged propio → copia NiFi → API canónica → CG15+ES →
commit explícito. Se configuraron los flags ES del CLI sólo en esa copia
propia, con raíz, topic, índice y sinks nuevos. Con ES bloqueado hubo 403,
original fallido retenido, dos recibos CG15 `stored` y offset sin confirmar.
Al recuperar ES, el reintento reutilizó la respuesta guardada (una inferencia
en total). Antes de confirmar 2 se verificaron journal, recibos, documento ES
exacto y los tres eventos provenance, incluyendo coordenadas/status y bytes
input/output. El CSV inválido quedó rechazado de forma durable. Se conservó
el fallo inicial del harness que consultó por error el ledger del primer
ensayo; un verificador separado leyó la raíz correcta y confirmó el offset
sólo después de todos los destinos. No se cambió lógica del producto.

Al detener realmente la API, NiFi retuvo el original y receipt fallidos y el
offset quedó en 2. Tras reiniciar la API con el mismo ledger, el reintento de
la misma ocurrencia obtuvo receipt completo y permitió commit 3. Otro replay
obtuvo `replay=1`, conservando el original fallido y sin nueva inferencia.

El gate de provenance final comprueba los cinco nombres de entrega, component
y group IDs exactos, topic/partition/offset, status de ejecución y **bytes
input/output exactos** recuperados de provenance; no basta contar eventos.
El reinicio de los contenedores propios Kafka/NiFi conservó los offsets de
nueve grupos consultados y los hashes de 318 objetos Parquet. No fue un
reinicio de host ni una pérdida de alimentación.

## Medidas cortas

12 eventos por repetición, tres repeticiones por combinación: 144 eventos.
Tiempo desde envío del productor hasta commit confirmado después de destinos;
no sólo tiempo de inferencia. API/CG15/ES reales, fixture de riesgo constante.

| Máximo por poll | Tasa ofrecida, eventos/s | Mediana de p50, ms | Peor p95 de las 3 tandas, ms | Mediana completados/s |
|---|---:|---:|---:|---:|
| 1 | 5 | 262 | 326 | 5,01 |
| 1 | 20 | 1.048 | 2.074 | 5,07 |
| 4 | 5 | 274 | 370 | 4,86 |
| 4 | 20 | 1.121 | 1.773 | 5,28 |

Lag final 0 en las 12 tandas; máximo muestreado 11. CPU del proceso worker:
1,462–1,589 s por tanda; pico RSS máximo 212.276 KiB. Huella durable por tanda:
288.938–289.466 bytes. Los logs incluyen inblock/oublock y muestras de RSS/lag.
No se midió aquí el coste agregado de CPU de broker/API/ES. No hay intervalo
sostenido suficiente para certificar capacidad, p99, saturación o un SLA; son
una línea base local, sin afirmar mejora respecto de otra versión.

## Gates y evidencia reproducible

- Python 3.11 y 3.12: 54 unittest focales por intérprete, 0 fallos/errores/
  skips/warnings/unraisables. Pytest NiFi/durable: 24 passed y 28 subtests por
  intérprete, con warnings como errores.
- Ruff **0.17.1**, selectores **E,F,I,PLW1510**, sobre todos los Python
  rastreados; formato de los cuatro Python modificados; diff whitespace,
  layout, lock, CG02, CG25 y actionlint: exit 0.
- CG25: 40 criterios, 79 enlaces/anchors, 55 hashes actuales y 18 históricos;
  se actualizaron sólo las huellas de pyproject/lock. Revisión humana pending.
- `uv audit --locked --output-format json`: 57 paquetes, 0 vulnerabilidades y
  0 adverse statuses. Warnings experimentales de la CLI conservados.
- Reproducción del wheel en 3.11/3.12: bytes idénticos; SHA256
  `e1d068023ae9ec42d8675956cc4cb9768fafbc02d5a7101e96cfff7828dff069`.

Evidencia completa y scripts ejecutados:
`D:/github/_local/t2-babysit-20261021/real-kafka-nifi-evidence-20261022/`.
Puntos de entrada: `start_lab.py`, `run_kafka.py`, `worker_child.py`,
`nifi_resume.py`, `nifi_outage.py`, `verify_services.py`, `capacity.py`,
`checks.py`, `final_checks.py` y `stop_inventory.py`. El ensayo combinado usa
`run_nifi_es.py`, `verify_nifi_es.py` y `stop_inventory_phase2.py`. No ejecutar otra vez un
creador de recursos: el laboratorio y sus datos se conservan para revisión.
Los scripts del harness reflejan su estado final; los logs conservan los
reintentos y los cambios de instrumentación. La lógica central del worker,
archivo y API no cambia en esta PR.

La verificación final del sellado detectó un log de diagnóstico aún abierto.
Se comprobó el cmdline del probe propio, se detuvo con SIGTERM y se fijó su
huella final. Los demás artefactos y hashes de fuentes coincidían. Ese probe
no confirmaba offsets ni forma parte de los escenarios funcionales pasados.

El resumen JSON y manifiesto adjuntos fijan los resultados y hashes de los
artefactos locales. Se mantienen también los fallos iniciales de import,
handshake, comandos de gate y las correcciones del harness. Los tres
contenedores propios se detienen al terminar; no se borran datos ni recursos
ajenos.

## Límites que siguen abiertos

Rebalance durante escritura, recuperación del host/alimentación, pérdida de
disco/retención, múltiples nodos, carga sostenida, SMB/Filebeat/Kibana y modelo
de entrega no se aceptan con este ensayo. No establece exactly-once distribuido.
No se ha repetido la suite Windows global: los 4 fails/84 errors son el estado
heredado comunicado al encargar este trabajo, no una validación actual aquí.
La revisión del padre, CI del SHA final, aprobación main y aceptación humana
siguen siendo gates separados. Ninguna issue se cierra por esta evidencia.
