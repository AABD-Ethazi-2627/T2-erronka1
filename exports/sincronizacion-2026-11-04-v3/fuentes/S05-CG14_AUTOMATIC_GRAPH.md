# Grafo automático CG13/14/15 con propietario único del offset

Este modo conecta el productor Filebeat existente con Kafka y un ciclo del
worker durable programado por NiFi 2.12. No usa staging ni un driver externo
que confirme offsets. Tampoco contiene un processor `ConsumeKafka`: NiFi
ejecuta el adaptador Kafka del producto mediante `ExecuteStreamCommand`.
Es una alternativa explícita al paso ConsumeKafka de la issue14; su revisión
humana queda pendiente. El export staged de PR68 sigue siendo un artefacto
distinto y no se convierte en un grafo autónomo por esta documentación.

Artefactos nuevos:

- [Export NiFi](../nifi-flows/cg14_automatic_graph_nifi_2.12.0.json), inicialmente
  DISABLED, generado por [el builder](../scripts/build_automatic_graph_flow.py).
- [Configuración de ejemplo](../deploy/cg14/automatic-graph.example.json), que
  requiere archivo y ES; [launcher](../scripts/run_automatic_graph.py).
- [Worker existente](../scripts/run_durable_pipeline.py) y
  [protocolo durable](CG14_DURABLE_PIPELINE.md), reutilizados sin cambiar la API,
  el ledger canónico, los IDs de ocurrencia ni los recibos CG15.

## Decisión y orden de confirmación

Filebeat publica el CSV original con `required_acks: -1`; conserva su registry.
Ese ACK del productor solo acredita la recepción Kafka según su configuración.
No significa que exista todavía una predicción o un recibo CG15.

NiFi genera un trigger vacío, ejecuta un ciclo acotado y guarda su salida y sus
atributos de diagnóstico. El trigger nunca contiene un mensaje Kafka. El
adaptador del worker es el único consumidor del grupo raw: auto-commit está
deshabilitado, entrega un prefijo ordenado de cada partición y confirma offsets
explícitos solo tras terminar todo el poll. No se confirma la posición
prefetched. Se mantiene `kafka-owner.lock` desde antes de construir el cliente
hasta después de su cierre; una segunda CLI/NiFi con la misma raíz falla antes
de unirse al grupo. `automatic-owner.lock` protege además configuración/reportes
durante todo el ciclo. Los locks son del SO y no se borran al recuperar.

Antes del commit se exigen, en este orden: raw/origen y journal durable;
proyección con identidad original; respuesta canónica guardada por API y
worker; ambos recibos CG15 `stored`/`duplicate` con hash exacto; `_create` ES
aceptado, o 409 seguido de GET con `_source` idéntico; job completado; asignación
Kafka vigente. Un rechazo CG15 persistido bloquea también durante replay;
su contador de replay no se interpreta como aceptación. El worker existente
verifica de nuevo los destinos al recibir un job ya completado.

La configuración automática queda fijada en `automatic-config.json` antes de
conectar, incluidos grupo, topic, namespace, rutas y destinos. El journal del
worker fija además manifiesto y contratos. Cambiar bytes requiere reconciliación;
no hay comando de reset o purga. Las opciones de CLI se pasan como lista, sin
shell. El export usa delimitador `;`: los parámetros de rutas no pueden contenerlo.
Antes de abrir el consumidor, el launcher exige un índice concreto existente,
su pipeline final de PR74, el export instalado idéntico y mapping estricto.
No instala ni modifica ES. Esa comprobación no es una transacción con la escritura:
los cambios concurrentes siguen sujetos al error de destino antes de commit.

La exclusión es local a una raíz en un único nodo. El operador debe reservar un
grupo exclusivo y una única raíz para ese origen; no ejecutar el modo directo,
el staged, un ConsumeKafka ni otra instancia con otra raíz sobre ese grupo.
Un grupo compartido reparte particiones y no replica un archivo completo.
La configuración no impide que un operador externo cree otro consumidor.
No habilitar este export en un clúster NiFi multinodo ni compartir SQLite por SMB/NFS.

## Activación en un laboratorio propio

1. Inventariar recursos/IDs y verificar que el broker, topics y destinos son
   propios. Reservar namespace de clúster/generación y grupo; crear el topic
   explícitamente. Reutilizar el topic raw y la configuración Filebeat existente:
   [filebeat.yml](../filebeat/filebeat.yml). Configurar hosts/topic en una copia.
2. Preparar el entorno soportado Python3.11/3.12 con el lock y extra Kafka.
   NiFi debe poder ejecutar ese intérprete y leer el checkout. Proporcionar un
   manifiesto canónico ya validado; el worker no entrena ni carga modelos.
3. Instalar **primero** `cnc-prediction-v1`, verificar su contenido/versionado y
   después instalar el template de PR74; crear un índice concreto propio que
   coincida con `cnc-alerts-*` o `cnc-telemetry-*`. Verificar en sus settings
   `index.final_pipeline=cnc-prediction-v1` y mapping. El valor real es un
   pipeline **final**, no un default que se pueda omitir mediante `_none`.
   Seguir [el procedimiento ES](../elasticsearch/README.md); no duplicarlo.
4. Crear una copia de la configuración con rutas absolutas locales y ES
   obligatorio. `offset_reset=none` falla cerrado si no hay offset: para el
   primer arranque de un grupo propio se debe elegir `earliest` explícitamente.
   Mantener después los mismos bytes; no cambiar automáticamente a `none`.
5. Importar el export nuevo en NiFi; configurar `WORKER_CHECKOUT`,
   `WORKER_PYTHON`, `GRAPH_CONFIG`, `PROCESS_TEMP`, `CYCLE_REPORTS` mediante un
   contexto de parámetros. Las cinco rutas deben existir y ser accesibles.
   En el lab de esta entrega todo writable/temp/cache se ubica en binds D:.
   Persistir conf/state/FlowFile/content/provenance/work/logs de NiFi y datos y
   metadata KRaft; un bind a otra ruta no acredita `log.dirs`.
   NiFi2.12 también requiere assets/connector_assets/nar_repository/status:
   el lab los configura dentro del bind de trabajo. Filebeat debe ejecutar
   con un UID que pueda persistir y ajustar permisos de su registry.
6. Revisar VALID de los cinco processors. Habilitar primero PutFile,
   AttributesToJSON y ExecuteStreamCommand; activar GenerateFlowFile al final.
   Una tarea concurrente por processor, nodo único. El trigger periódico
   reintenta por sí solo tras fallos. No hay publicación/commit por el harness.
7. Observar offsets del grupo por administración, journal, recibos y ES.
   Mantener controles de acceso a los diagnósticos, que contienen rutas y errores.
   Detener primero el trigger y esperar la salida del ciclo para una parada
   limpia; luego detener el resto. No borrar colas, registry o journals.

Las relaciones `output stream`, `nonzero status` y `original` se conservan.
AttributesToJSON registra `execution.status/error`; PutFile guarda salidas y
diagnósticos por UUID y reencola `failure` sin caducidad. La contrapresión limita
triggers/diagnósticos pendientes. Estos ficheros son observabilidad: su presencia
o su ausencia nunca autoriza un ACK Kafka. Los recibos efectivos están en CG15.
Si el disco de diagnóstico se llena después de un commit, no invalida los
destinos ya durables; detiene por contrapresión la planificación de ciclos.

## Fallos y recuperación

- CSV/UTF-8 inválidos y HTTP422: rechazo terminal con raw/cuarentena durable
  antes de commit; no generan Prediction ni archivo de una Prediction ficticia.
- HTTP409 (identidad/manifiesto incompatible), HTTP413 (cuerpo demasiado grande),
  otros 4xx y redirecciones: bloqueo y ningún commit. 413 no se reclasifica 422.
- HTTP503/otros5xx/timeout: intentos finitos dentro del ciclo y salida no cero;
  NiFi volverá a programarlo con los mismos bytes. Un timeout después del commit
  de API se recupera por su respuesta canónica, sin inferencia nueva.
- CG15 rejected o recibo/hash ausente: bloqueo persistente. No editar el recibo
  para continuar; restaurar/reconciliar desde evidencia original. Un retry
  exitoso de transporte no resuelve ese conflicto por sí mismo.
- ES403, guard de pipeline, mapping, pipeline ausente o documento409 distinto:
  bloqueo, aunque archivo/API ya estén guardados. Corregir solo la causa
  autorizada y reanudar; el mismo response/outbox se reutiliza.
- Crash antes/después de `done` o commit incierto: Kafka puede repetir el prefijo.
  Reiniciar con misma raíz/API ledger/config/namespace/grupo. No republicar
  mensajes ni generar nuevos IDs para ocultar el replay. Un rebalance hace
  fallar el ciclo y cierra sin auto-commit; NiFi reintenta desde el broker.

Cada ciclo conserva un reporte inmutable en `automatic-cycles/`. Su contabilidad
es **observed = saved + rejected + pending**, basada en jobs únicos observados.
`saved` significa job completado con los destinos requeridos en su ejecución;
no certifica una comprobación remota continua ni sustituye offsets del broker.
El total enviado lo debe aportar Filebeat/productor, incluyendo lo todavía no
leído de Kafka. No sumar `replay` como nuevo mensaje ni asumir que `completed`
del ciclo significa que no hay lag: puede haber consumido solo su presupuesto.

## Verificación y límites

[Regresiones](../tests/test_automatic_graph.py) y suites durables existentes
comprueban exclusión, configuración inmutable, configuración ES obligatoria,
errores, recibos rechazados y replay. [Evidencia de esta entrega](evidence/AUTOMATIC_GRAPH_20261022.md)
distingue fuente/export estático, integración real y límites pendientes.
El contrato de tipos/NAR/relaciones de los processors se capturó del catálogo
real de NiFi2.12 y se conserva en la fixture versionada de regresión.

Hay transacciones independientes en Filebeat, Kafka, API, worker, CG15, ES y
NiFi. No se afirma exactly-once distribuido, pérdida cero, HA, capacidad
sostenida ni resistencia ante corte de alimentación/host. La recuperación
depende de retención, namespace correcto, disco fiable y conservación de todos
los estados. Windows proporciona recuperación de proceso según
[el contrato de plataforma](PLATFORM_SUPPORT.md). Falta revisión del padre.

Referencias de processors verificadas para NiFi2.12:
[GenerateFlowFile](https://nifi.apache.org/components/org.apache.nifi.processors.standard.GenerateFlowFile/),
[ExecuteStreamCommand](https://nifi.apache.org/components/org.apache.nifi.processors.standard.ExecuteStreamCommand/).
ExecuteStreamCommand requiere entrada; por eso el export incluye un trigger
autónomo y no trata ese processor aislado como una fuente.
