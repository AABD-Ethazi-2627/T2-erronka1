# CNC Guard: explicaciones para estudiar y exponer

Preparación del 28/10/2026 para #37 y #83 de `AABD-Ethazi-2627/T2-erronka1`. Base documental comprobada: [`main` b2186e519e5444dcdb127d9409da105a8fe6d674](https://github.com/AABD-Ethazi-2627/T2-erronka1/tree/b2186e519e5444dcdb127d9409da105a8fe6d674), tras integrar PR91. Todas las rutas citadas se refieren a esa versión; las fechas de sus evidencias se conservan. Es material redactado para preparar la explicación, con un reparto propuesto en cuatro bloques; no registra intervenciones, ensayo o aceptación de personas. Los ejemplos didácticos se distinguen de las mediciones archivadas.

Cada bloque puede estudiarse por separado. El texto oral desarrolla la explicación; la ficha posterior ayuda a responder sin memorizarla palabra por palabra. Para la exposición breve en euskera puede usarse el [guion de defensa actualizado](DEFENTSA_GIDOIA_20261023.md).

## Bloque 1 propuesto: qué hace la IA y qué recibe

### Texto oral desarrollado

«CNC Guard ayuda a revisar el estado actual de una máquina a partir de una lectura de sus sensores. La palabra “actual” define el problema: una fila es una fotografía tabular. El sistema no ha demostrado cuándo se romperá una máquina, cuánta vida útil le queda ni qué ocurrirá dentro de veinticuatro horas. Aunque una variable se llame `tool_wear_min`, sus minutos representan el desgaste de la herramienta en esa lectura; no crean una secuencia de observaciones de la misma máquina.

Estamos ante IA estrecha: un sistema especializado en una tarea delimitada. AGI designa la idea de una inteligencia general capaz de abordar muchos tipos de tareas; no es una propiedad que hayamos demostrado aquí. Tampoco toda decisión de nuestro sistema procede del aprendizaje automático. Una regla escrita por una persona puede decir: si el score llega a 0,15, mostrar AVISO. Esa comparación está programada. Lo aprendido es la función que transforma las variables de entrada en un score.

En aprendizaje supervisado se usan ejemplos con una etiqueta objetivo. Nuestro Random Forest, o RF, aprende a relacionar lecturas con `machine_failure`, la etiqueta contemporánea de fallo. Un bosque combina muchos árboles: cada árbol separa casos mediante condiciones sobre variables y el conjunto agrega sus resultados. Gradient Boosting, o GB, también combina árboles, pero los construye sucesivamente para mejorar el resultado conjunto corrigiendo errores del ajuste anterior. No hay una familia que gane por definición: hay que comparar configuraciones con el mismo protocolo y considerar qué errores comete cada una.

El aprendizaje no supervisado busca estructura en las entradas sin aprender directamente a predecir una etiqueta objetivo. Nuestro canal de rareza plantea otra pregunta: cuánto se aparta una lectura de las consideradas normales. Isolation Forest, o IF, usa particiones aleatorias; observaciones que se aíslan con facilidad pueden resultar más extrañas. Un autoencoder, o AE, comprime y reconstruye las entradas; un error de reconstrucción alto puede servir como señal de rareza. Esto no equivale a una etiqueta de avería. En este proyecto se usan etiquetas de train para filtrar normales, por lo que tampoco sería correcto describir todo el procedimiento como completamente ajeno a etiquetas. No existe una verdad independiente de anomalías con la que certificar que toda rareza sea un fallo.

La API RF+IF recibe seis entradas de modelo: `air_temp_K`, `process_temp_K`, `rpm`, `torque_Nm`, `tool_wear_min` y `machine_type`. Son cinco medidas físicas más una categoría H, M o L. Las temperaturas están en kelvin, la velocidad en revoluciones por minuto, el torque en newton metro y el desgaste en minutos. Que el ejemplo docente enumere cinco sensores no elimina el tipo que usa el bundle: la valoración académica de esa diferencia sigue abierta.

El evento incluye además `event_id`, `machine_id`, `timestamp`, `schema_version`, `quality_flag` y `source`. Esos campos permiten seguir el origen y detectar reintentos; no son predictores que la API añada a X. Dentro de `source` se conserva el tipo de origen, la URI y la referencia del registro. Las etiquetas de fallo tampoco entran como sensores. Si se introdujera la respuesta que queremos predecir dentro de X, el modelo podría parecer excelente por una fuga de información.

La salida separa `failure_score`, nivel de alerta y rareza. La API usa el negativo de `IF.score_samples`: en ese canal, un valor mayor significa más extraño. El score RF no está acreditado como probabilidad calibrada de una futura avería. Un IF sin alerta no cancela una alerta RF, y una alerta IF no confirma por sí sola una avería. El resultado se conserva con la versión y el hash del artefacto para saber qué produjo la respuesta. La decisión de inspeccionar o actuar corresponde a una persona; la API no detiene ni pone en marcha la CNC».

Las entradas y el alcance proceden del [recibo histórico CG26](../evidence/CG26_REHEARSAL_2026-10-21.json), [CG07](../evidence/CG07.md), [`scoring/scope.py`](../../scoring/scope.py) y de las clases `Telemetry`/`Source` e `infer` en [`scoring/score_api.py`](../../scoring/score_api.py). La comparación RF/GB/IF/AE y el filtro de normales están documentados en [CG34, secciones de representación y rareza](../evidence/CG34_EXPLORACION_20261023.md); sus detectores research no son el IF servido. Las definiciones de familias son explicaciones conceptuales, no nuevas pruebas de rendimiento.

### Entrada, salida, error y límite

**Si preguntan por FastAPI y Pydantic:** FastAPI expone el contrato HTTP;
Pydantic valida los modelos de entrada antes de inferir. Esto permite separar
un dato inválido de una indisponibilidad del modelo y mantener una respuesta
con estructura conocida. Validar el formato no demuestra que el sensor mida
bien: la revisión del dato y la interpretación física siguen siendo necesarias.

**Si preguntan por el lazo de control:** aquí la salida llega a una persona
que puede revisar y decidir mantenimiento. Un lazo cerrado automático requeriría
que una acción sobre la máquina produjera nuevas medidas y que el sistema
comprobara su efecto. No hemos implementado ni validado ese actuador o ese lazo;
la autonomía del scheduler se limita a transportar y procesar eventos.

La **entrada** es una lectura con esas seis variables y sus metadatos. La **salida** es una predicción trazable con score RF, `alert_level`, señal IF, umbrales e identidad del modelo. Un **error** de contrato, como `rpm` negativo o un tipo fuera de H/M/L, se rechaza con 422; no debe transformarse en una predicción aparentemente normal. El **límite** es la clasificación contemporánea sobre datos sintéticos tabulares: ni causalidad, ni pronóstico temporal, ni orden automática sobre la máquina.

### Ejemplo recorrido

El caso `normal_fit_example` de CG26 contiene 301,5 K de aire, 310,4 K de proceso, 1.350 rpm, 54,9 Nm, 153 minutos y tipo M. Su score RF archivado es `0.004264675232657996`, con nivel OK. Es una demostración histórica sobre una fila de fit, no una muestra independiente ni una predicción del candidato reconstruido del 28/10. La diferencia de temperaturas es `310,4 − 301,5 = 8,9 K`: muestra cómo interpretar una variable derivada sin añadir etiquetas o fechas al modelo. En el ejemplo físico de [CG07](../evidence/CG07.md), 60 rpm y 10 Nm dan `P = 10 × 60 × 2π/60 = 20π W`. El producto rpm·torque solo no está expresado en vatios; `wear_torque` es un proxy, no desgaste físico demostrado.

### Relevo propuesto

«Ya hemos definido qué entra y qué significa la salida. El siguiente bloque explica cómo separar los datos y comparar modelos sin que la evaluación vea sus propias respuestas».

### Preguntas fuera de especialidad

- **¿Por qué guardar un timestamp si no se predice el futuro?** Para trazabilidad del evento. Guardarlo no obliga a usarlo como variable del estimador ni demuestra que las filas formen una serie temporal.
- **¿Qué pasa si se repite una petición?** Con la misma identidad, entrada y configuración, el ledger devuelve la respuesta canónica; no necesita ejecutar otra inferencia. El bloque 3 explica cómo continúa la entrega.
- **¿Una alerta correcta es gratis?** No en la matriz del ejercicio: el TP tiene coste de 300 €. El bloque 4 desarrolla el cálculo completo.

## Bloque 2 propuesto: datos, selección y calibración sin fuga

### Texto oral desarrollado

«La fuente activa tiene 8.000 filas del CSV AI4I reducido suministrado. La pertenencia conservada es 5.600 de entrenamiento, 1.200 de validación de desarrollo y 1.200 del test antiguo, ya inspeccionado y excluido. Las tres partes son disjuntas y cubren la fuente. Excluir ese test significa que no se vuelve a usar para ajustar ni para presentar un nuevo resultado independiente. Cambiar la semilla y repartir otra vez las mismas filas no recuperaría la independencia perdida. La validación también se ha reutilizado: sus resultados sirven para desarrollo, con ese límite.

En CG34 se compararon 50 configuraciones, no cincuenta modelos ya desplegados. Cuarenta son supervisadas y diez son detectores de rareza. El screening tiene 150 unidades: cincuenta configuraciones por tres folds. La fase nested tiene 600 unidades: por configuración, nueve ajustes inner y tres refits outer. A ello se suman ocho unidades de piloto, setenta y dos de calibración y un refit final: 831 unidades de entrenamiento. Este estudio utiliza las 5.600 filas de train, con 190 positivos; no puntúa la validación reutilizada ni el test excluido.

¿Para qué sirve anidar la validación? Si probamos muchas opciones y elegimos la que mejor sale en los mismos datos que usamos para anunciar el resultado, seleccionamos también parte de su suerte. En cada partición externa, dejamos el outer-held fuera. Dentro del outer-train, los folds inner producen scores fuera del ajuste de cada fila, llamados OOF. Con esos scores internos se seleccionan configuración y umbral. Después se reajusta sobre el outer-train y se evalúa una vez en el outer-held. La imputación, escala, codificación y pesos también pertenecen al ajuste interno: calcularlos con todo el conjunto antes de separar daría información del held al modelo.

El umbral no se elige mirando el resultado outer. Tampoco se puede escoger después el escenario de costes que haga ganar al candidato favorito. La regla inicial, preregistrada, conserva sus costes históricos; la matriz docente recibida después se analiza por separado reutilizando scores ya guardados. Eso permite explicar la cronología sin reescribir el criterio inicial. La selección sobre todo train sirve para preparar una especificación fija, pero ese paquete final no hereda automáticamente una evaluación independiente del procedimiento nested.

La calibración intenta que el significado numérico de un score corresponda mejor a frecuencias observadas. No debe aprenderse sobre los mismos casos con los que se comprueba. En cada fit secundario de CG34, el estimador usa el 75 % y el calibrador el 25 % reservado del entrenamiento correspondiente. `raw75` permite compararlo con un estimador que recibió ese mismo 75 %. Ningún held ajusta el estimador o calibrador, y los finalistas se eligen dentro de cada outer-train. Se estudiaron variantes raw y sigmoid/isotonic, pero el resultado no demuestra que el score del bundle servido esté calibrado ni autoriza sustituir sus umbrales.

El desbalance importa porque los fallos son pocos. De los 5.600 casos de train, 190 son positivos. Un clasificador que dijera siempre “sin fallo” acertaría aproximadamente el 96,61 % y detectaría cero fallos. Por eso la exactitud global sola no basta. Recall pregunta qué parte de los fallos detectamos; precision, qué parte de nuestras alertas son verdaderos positivos. F2 da más peso al recall que F1, pero tampoco contiene por sí solo la matriz económica. Los pesos de clase son una opción de ajuste; no se ha aplicado SMOTE sobre todo el conjunto antes de los folds.

Python permite preparar variables, entrenar los pipelines y guardar artefactos para servirlos después con FastAPI. El entrenamiento es offline; la API carga esos artefactos y hace inferencia, sin aprender de cada petición. Serializar no vuelve intercambiables todos los archivos con la misma etiqueta de versión: hay que verificar manifiesto, hashes, dependencias y recarga. La API verifica los hashes de ambos pickles antes de deserializarlos con joblib, exige compatibilidad declarada de sklearn y hace una prueba de carga. Ese control presupone un directorio confiable; un hash aportado junto a un pickle desconocido no convierte ese pickle en seguro. Si el bundle no está preparado, responde 503 en lugar de fabricar un score.

La conclusión del estudio es conservar RF y los niveles 0,15/0,70. Bajo la regla inicial, los selectores eligen RF en los tres outer. Con la matriz docente posterior, el selector del pool completo elige AdaBoost/RF/RF, mientras la selección de la especificación fija sobre train vuelve a elegir RF. No debemos atribuir el resultado de un selector cambiante a un único modelo. El paquete RF research, el RF+IF histórico y el candidato reconstruido de CG32 son artefactos distintos».

Fuentes: [membresía CG04](../evidence/CG04_split_membership.json), [CG07 y preprocesamiento](../evidence/CG07.md), [informe CG34 completo](../evidence/CG34_EXPLORACION_20261023.md), [manifiesto research](../evidence/CG34_20261023/manifest.json), [auditoría CG40 de unidades y paquete](../evidence/CG40_CLOSEOUT_20261028.json) y [carga de la API](../../scoring/score_api.py). CG34 conserva 27 avisos de sus candidatos, incluido un AE sin convergencia al llegar al límite; no se presenta como si todas las optimizaciones hubieran convergido. Sus conclusiones siguen siendo desarrollo sobre una fuente sintética previamente explorada.

### Entrada, salida, error y límite

La **entrada** del estudio son las filas y pertenencias de train, configuraciones y reglas de selección fijadas. La **salida** son scores OOF, métricas, selección y un paquete research identificado. Un **error** sería aprender el umbral con outer-held, escalar con todo el conjunto o escoger finalistas por el ranking global externo. El **límite** es que nested reduce la fuga dentro del procedimiento descrito; no borra la exploración previa del proyecto ni convierte AI4I en validación industrial.

### Ejemplo calculado

El negativo constante acierta `(5.600 − 190) / 5.600 = 96,6071 %`, pero su recall es `0 / 190 = 0 %`. Como ejemplo de métricas reales de desarrollo, el punto AVISO de [CG10 conciliado](../evidence/CG10_PRECISION_20261022.md) tiene TP32, FN9, FP12 y TN1147 en 1.200 filas: recall `32 / (32 + 9) = 78,0488 %` y precision `32 / (32 + 12) = 72,7273 %`. El punto F2 original tiene los mismos TP/FN y FP9/TN1150; son umbrales distintos sobre predicciones de validación reutilizada. Ninguno es el resultado outer de CG34 ni una medición de la campaña nominal CG32.

### Relevo propuesto

«La evaluación nos ayuda a elegir y a reconocer los límites del modelo. Ahora seguiremos una lectura real del sistema para entender cuándo está recibida, calculada y guardada, y qué ocurre si se interrumpe el recorrido».

### Preguntas fuera de especialidad

- **¿Seis entradas significan seis sensores físicos?** No: cinco medidas y una categoría de tipo de máquina. Los metadatos siguen viajando para trazabilidad.
- **¿Si el modelo tarda pocos milisegundos, todo llega en un segundo?** No. La cola, planificación, persistencia y visibilidad en ES añaden tiempo. El p95 del modelo y el p95 E2E miden recorridos distintos.
- **¿Por qué no poner el umbral económico teórico directamente?** Requiere una probabilidad calibrada y costes/acciones que describan el caso real. El score servido no tiene esa acreditación y el análisis económico no cambió la política operativa.

## Bloque 3 propuesto: recorrido durable y campaña actual

### Texto oral desarrollado

«El recorrido previsto empieza en SMB: se captura una copia local validada y se publica como CSV inmutable. Filebeat lee esa copia; no recibe las credenciales SMB ni necesita leer directamente un montaje remoto. El protocolo del productor debe cerrar el lote antes de anunciar el nombre final. Comparar tamaños antes y después ayuda a detectar ciertas descargas incompletas, pero no demuestra que un productor haya terminado un archivo si cambia bytes manteniendo su tamaño. La campaña CG32 del 28/10 empieza en CSV local: no mide ese tramo SMB ni acredita su funcionamiento en red.

Desde la copia local, Filebeat envía a Kafka. Kafka conserva los registros y su posición. NiFi organiza el trabajo con un trigger de GenerateFlowFile y ExecuteStreamCommand, que ejecuta el worker Python por ciclos acotados. No hay un processor ConsumeKafka escondido: el adaptador del worker es el único propietario del offset del grupo. NiFi actúa como scheduler y el worker realiza la lectura y el recorrido durable. Esta autonomía de planificación no es autonomía para intervenir sobre las máquinas.

El worker conserva origen y journal, proyecta la lectura al contrato y llama a FastAPI. La API calcula con RF+IF y confirma su respuesta en un ledger SQLite local antes de devolver 200. Si se pierde la conexión después de ese commit, repetir la petición idéntica recupera la misma respuesta completa, incluido `scored_at`. La clave incluye `event_id`, hash RF y policy, y la configuración completa queda vinculada. No se vuelve a calcular solo porque haya otro intento HTTP.

Después quedan destinos por confirmar. El worker exige los recibos durables del archivo CG15 y la escritura ES. Si ES devuelve conflicto de creación, comprueba que el documento existente sea idéntico; un documento distinto bloquea. Solo después de los destinos requeridos, del job completado y de comprobar la asignación vigente se confirma el offset Kafka. El ACK del productor Filebeat significa recepción en Kafka bajo su configuración; el 200 de la API significa respuesta confirmada en su ledger. Ninguno sustituye por sí solo ese commit final de consumo.

Por eso se puede repetir transporte y conservar un único resultado lógico. Eso es idempotencia con identidad estable; no es una transacción distribuida exactly-once. Conservar registry, journal, ledgers, namespace y retención forma parte de la recuperación. No se arregla un conflicto cambiando el identificador ni borrando estado.

Los códigos ayudan a decidir. Un 200 entrega una respuesta canónica. Un 409 de la API indica una identidad o configuración incompatible y requiere reconciliación, sin commit del worker. Un 422 es un rechazo terminal de entrada: se conserva raw y cuarentena antes de confirmar su tratamiento, sin fabricar una Prediction. Un 503 indica modelo no preparado; junto con otros 5xx o timeouts permite intentos finitos dentro del ciclo y una nueva planificación conservando los mismos bytes. Estos códigos son el contrato del producto; la campaña de lecturas nominales no es una prueba nueva de todos esos errores.

La campaña integrada actual es la del 28 de octubre. En siete corridas se ofrecieron y guardaron 1.860 eventos nominales; cada corrida terminó con cero pérdidas válidas, cero duplicados finales por ID, cero pendientes y lag final cero. Las pruebas de pausa y SIGKILL recuperaron veinte de veinte eventos cada una. Eso describe las interrupciones observadas; no demuestra que el kill ocurriera justo en la ventana entre respuesta HTTP y commit Kafka.

La limitación de capacidad es visible. Las tres corridas base ofrecieron seiscientos eventos cada una a diez por segundo durante sesenta segundos. El lag máximo llegó a 340 y luego se drenó. El throughput observado contando el drenaje quedó entre 4,1087 y 4,2702 eventos por segundo. Haber ofrecido diez por segundo no significa sostener esa tasa sin backlog. Los p95 HTTP servidor estuvieron por debajo de cien milisegundos, pero los E2E de las corridas base estuvieron entre 78,135 y 83,859 segundos. No se cumple la meta propuesta de un segundo E2E.

La latencia RF+IF en proceso tiene otra medida: p95 de 5,929676 ms, con seiscientas observaciones warm y veinte llamadas previas excluidas. No se suma ese percentil al HTTP o al E2E. El E2E empieza después del fsync de la línea CSV y termina en el primer poll de ES que ve el documento; incluye refresh y polling. Discover aporta una captura de un mismo evento con ID y hash RF coincidentes, no la prueba visual individual de los 1.860. La lectura correcta es que el laboratorio permite demostrar ráfagas acotadas, trazabilidad y drenaje posterior; no capacidad industrial ni SLA».

Fuentes del mecanismo: [SMB y copia local](../SMB_FILEBEAT_LAB.md), [grafo automático](../CG14_AUTOMATIC_GRAPH.md), [pipeline durable](../CG14_DURABLE_PIPELINE.md) y [contrato del ledger](../SCORING_REPLAY_CONTRACT.md). Resultados: [informe CG32 del 28/10](../evidence/CG32_CAMPAIGN_20261028.md), [protocolo de medidas](../CG32_LOAD_PROTOCOL.md), [latencia del modelo](../evidence/CG32_CAMPAIGN_20261028/model-latency.json), [dispersión entre las tres bases](../evidence/CG32_CAMPAIGN_20261028/summary-10.json) y [recibo de Discover](../evidence/CG32_CAMPAIGN_20261028/discover-receipt.json).

### Cifras por corrida para consultar al explicar

Valores del informe contrastados con cada `run.json` dentro de [`raw-runs.zip`](../evidence/CG32_CAMPAIGN_20261028/raw-runs.zip); el [índice de hashes](../evidence/CG32_CAMPAIGN_20261028/raw-index.json) permite comprobar sus bytes. HTTP en ms; E2E y drenaje en s. Se muestran tres decimales, sin agrupar percentiles de distintas corridas.

| Corrida / directorio raw bajo `runs/` | Ofrecidos / guardados | p95 HTTP ms | p95 E2E s | Lag máximo / final | Drenaje s |
|---|---:|---:|---:|---:|---:|
| `batch32-base-1-r10-eacaea` | 600 / 600 | 14,958 | 82,747 | 340 / 0 | 87,888 |
| `batch32-base-2-r10-80ec85` | 600 / 600 | 15,116 | 83,859 | 340 / 0 | 88,596 |
| `batch32-base-3-r10-4d8d8b` | 600 / 600 | 14,365 | 78,135 | 340 / 0 | 83,132 |
| `batch32-kill-r1-1850f3` | 20 / 20 | 15,905 | 39,762 | 20 / 0 | 27,714 |
| `batch32-pause-r1-3ebd72` | 20 / 20 | 13,414 | 25,728 | 18 / 0 | 8,144 |
| `batch32-pilot-r1-3c9256` | 10 / 10 | 13,577 | 12,162 | 9 / 0 | 15,022 |
| `rebuilt-pilot-r1-cab63c` | 10 / 10 | 19,906 | 25,928 | 9 / 0 | 29,045 |

La suma `600 + 600 + 600 + 20 + 20 + 10 + 10 = 1.860` cuenta eventos de transporte de fixtures nominales, con IDs nuevos por ocurrencia. No son 1.860 muestras independientes para medir recall o precisión del modelo. Las corridas posteriores al piloto usan `max_records=32`; el piloto `rebuilt-pilot` usa 1. No se ejecutaron las tres cargas de 600 con ese valor 1 ni la tasa de 50/s: el informe explica las omisiones y el presupuesto. Una observación por piloto no demuestra causalmente una mejora A/B.

### Identidades que no deben mezclarse

| Evidencia | Identidad exacta y uso |
|---|---|
| [CG26 histórico, 21/10](../evidence/CG26_REHEARSAL_2026-10-21.json) | Manifiesto `a6cc7a29f0b061e114e046865cf7ac4a3969111a904a0281f1919aff35ea0945`; RF `803ee2e10e0486aaeb1fb65ed43df9d0069c2d5113d1e1ec45777346a0b6735a`; IF `a12304b474f290841a435ffb7d9caaa65c0843ce537267d28686a9d0f49aae79`. Identidad histórica de entrega. |
| [Candidato reconstruido CG32, 28/10](../evidence/CG32_REBUILT_IDENTITY_20261028.json) | `rebuilt_candidate`; manifiesto `b85be76ef47ee88f34294fe009e9f4e21d3b3d78f10c8ba6b276389452136d5a`; RF `67c98ff5c9c265d956e686f151a507f255f0a2bb8864cd259c5736c08d9d0dfc`; IF `4354475cb268fe5777ebeced69316261579070b7a5e184c02b7bae8a4cacacee`. Es el medido en la campaña actual; compartir `model_version` no lo convierte en CG26. |
| [Paquete RF research CG40](../evidence/CG40_CLOSEOUT_20261028.json) | Hash del paquete `34a14ab97a0e1facc4f4eff10b7ed9227516cc853d7400abd351ccef17cffe72`. Refit de investigación y su umbral; no sustituye el RF+IF del servicio. |

La campaña no se ejecutó sobre este merge limpio: la [proveniencia](../evidence/CG32_CAMPAIGN_20261028/provenance.json) conserva arranque en `b815771` con adaptación sin commit y bytes de laboratorio coincidentes con `3061a6c`. Esta guía explica la evidencia integrada en la base indicada, sin atribuirle una ejecución nueva. La API del grafo usa Python 3.11; el suplemento local usa Python 3.12.14. Su HTTP loopback mide ida/vuelta cliente y no sustituye el HTTP servidor de la tabla; véase [runtime y recarga](../evidence/CG32_CAMPAIGN_20261028/supplement-runtime-reload.json).

### Entrada, salida, error y límite

La **entrada** del recorrido es la línea publicada y su identidad estable. La **salida** confirmada exige archivo y documento ES, con trazabilidad hasta Discover. Un **error** de destino deja pendiente el commit aunque la API ya haya respondido 200; se reintenta preservando la respuesta. El **límite** es la recuperación local con estado conservado y un único propietario del offset, sin garantía distribuida ante cualquier caída o pérdida de disco.

### Ejemplo de recuperación

Supongamos que la API ha confirmado una respuesta y el worker se interrumpe antes de terminar ES y el commit Kafka. Este es un recorrido didáctico del contrato, no la ventana exacta acreditada por el kill de la campaña. Kafka puede volver a entregar el registro. El worker conserva el mismo `event_id`, el ledger devuelve el mismo `scored_at` y resultado, y los destinos comparan el contenido. Si el documento ya existe e idéntico, se reconoce; si es distinto, se bloquea. El offset se confirma después de completar y verificar los destinos. Así, repetir una entrega no exige crear un nuevo evento lógico.

### Relevo propuesto

«Ya sabemos dónde se guarda y cuánto tarda una lectura. Para cerrar, veremos por qué una alerta debe interpretarse con sus errores y sus costes, sin convertir un score en una orden automática».

### Preguntas fuera de especialidad

- **¿Guardar todos los eventos demuestra buen recall?** No. CG32 mide transporte nominal y persistencia. Detectar fallos se evalúa con etiquetas y predicciones en otras evidencias.
- **¿Un 409 de ES y uno de la API significan lo mismo?** No. ES puede indicar un documento ya creado y se comprueba igualdad; la API comunica conflicto de entrada/configuración bajo una identidad. No se reintenta cambiando el ID.
- **¿La rareza convierte una alarma en una certeza?** No. Es una señal independiente que ayuda a revisar; no da ground truth de avería ni una probabilidad calibrada.

## Bloque 4 propuesto: decisión RF, errores y coste de las alertas

### Texto oral desarrollado

«La decisión actual conserva Random Forest y los niveles de aula: OK por debajo de 0,15; AVISO desde 0,15 y por debajo de 0,70; CRITICA desde 0,70. Esto describe `alert_level`. Existe además `risk_alert`, que compara el score con `risk_threshold` del manifiesto, y una señal `anomaly_alert` separada. No debemos llamar a todos esos campos “la misma alarma”. El umbral F2 de un bundle, un umbral de investigación y los niveles fijos de aula responden a contratos distintos.

Conservar RF es una decisión apoyada en comparaciones concretas. En CG34, GB presenta ventajas en algunas métricas, pero sus intercambios entre fallos omitidos e inspecciones no bastan para sustituir RF bajo el criterio inicial. Con la matriz docente, RF es la especificación fija elegida en train y tiene el menor coste entre las cuarenta supervisadas cuando se conserva AVISO 0,15. Esto no significa que RF sea superior bajo toda política posible: el informe muestra que una configuración XGBoost obtiene menor coste que RF con umbrales inner de la política A. Ese candidato no fue el elegido por el selector interno ni mejoró RF B al conservar el contrato 0,15. Las variantes calibradas y los detectores de rareza tampoco se promovieron al servicio.

Para interpretar el coste usamos la matriz facilitada en el texto docente aportado por el usuario: FN cuesta 5.000 €, FP 200 €, TP 300 € y TN 0 €. Un FN es un fallo que dejamos pasar; un FP es una inspección innecesaria; un TP implica mantenimiento preventivo, que también cuesta; un TN no genera ese coste en el escenario. La fórmula es `C = 5.000 FN + 200 FP + 300 TP + 0 TN`. Son parámetros del ejercicio, no cuentas industriales verificadas.

El coste de recuperar un fallo omitido no es ahorrar los 5.000 € completos: al pasar de FN a TP aparece el coste de 300 €. La reducción marginal es 4.700 €. Si para detectar ese fallo añadimos falsos positivos, cada uno cuesta 200 €. El equilibrio es `4.700 / 200 = 23,5`. Como los eventos son enteros, con veintitrés FP extra aún se reduce el coste en cien euros; con veinticuatro aumenta en cien. Para varios cambios, interesa que `4.700 × ΔTP > 200 × ΔFP`, manteniendo la misma cohorte y las demás condiciones.

Esto muestra por qué no basta decir “más recall siempre es mejor”. El recall mide fallos recuperados, pero no contabiliza cuántas alarmas adicionales hay ni su tratamiento. También sería incorrecto usar solo precision: una política muy restrictiva podría tener pocas falsas alarmas y dejar demasiados fallos sin detectar. Las decisiones requieren ver la matriz completa, la capacidad humana de revisar y el significado de cada nivel.

En la evidencia CG34, RF con AVISO 0,15 tiene TP168, FN22, FP63 y TN5347 sobre las 5.600 filas outer. Con los costes docentes, el total es 173.000 €, o 30.892,86 € por mil eventos. Es un escenario calculado con etiquetas sintéticas contemporáneas y scores outer; no son euros gastados en una fábrica ni ahorro observado. La hipótesis de que detectar permita evitar el coste de una avería tampoco se demuestra solo clasificando una fila.

El estudio conserva también el escenario histórico de inspección y horas de parada a 1.200 €/h. Tiene otra fórmula y otra cronología; no se suman ambos escenarios ni se transforma ese coste por hora en el FN fijo de 5.000 €. Las curvas económicas se calcularon con scores archivados, sin entrenamiento nuevo, y los umbrales se eligen internamente. Los mínimos de curvas OOF train son ajuste, no un mínimo confirmado por un test independiente.

¿Por qué no fijar el umbral teórico económico de aproximadamente 0,040816? Esa fórmula presupone una probabilidad posterior bien calibrada y dos acciones con los costes descritos. No basta con que `predict_proba` devuelva un número entre cero y uno. El bundle servido declara score contemporáneo sin calibración acreditada, y el añadido económico no autorizó un cambio de política. Conservar 0,15/0,70 permite mantener la decisión vigente mientras se explica la investigación con sus límites.

La autonomía del software consiste en procesar, conservar y presentar la información conforme al contrato. La persona sigue decidiendo si revisa una alerta y cómo interviene. Lo que puede defenderse hoy es una clasificación contemporánea, una comparación de desarrollo y una campaña de transporte con sus tiempos medidos. Esas pruebas permiten una explicación concreta, sin atribuir acciones o validaciones a quien todavía no las ha realizado».

Fuentes: [`scoring/alert_policy.py`](../../scoring/alert_policy.py), [`infer` en la API](../../scoring/score_api.py), [decisión y resultados CG34](../evidence/CG34_EXPLORACION_20261023.md), [matriz de costes y ausencia de cambio operativo](../evidence/CG34_20261023/business-costs.json), [tablas docentes](../evidence/CG34_20261023/business-tables.md) y [resumen económico](../evidence/CG34_20261023/business-summary.json). La atribución docente y la valoración académica aún pendiente figuran en [A05/A06](../rubrica/ACLARACIONES_20261023.md).

### Entrada, salida, error y límite

La **entrada** es el score con su identidad, la matriz de confusión de la cohorte y los costes del escenario. La **salida** es un nivel de alerta y una comparación económica para revisión humana. Un **error** sería ignorar el coste TP, mezclar umbrales o anunciar una reducción hipotética como ahorro realizado. El **límite** es que la elección depende de datos, calibración, costes y capacidad de intervención; esta comparación no acredita generalización industrial ni activa un nuevo corte.

### Ejemplo calculado y lectura de una respuesta

Para RF B en CG34: `22 × 5.000 + 63 × 200 + 168 × 300 + 5.347 × 0 = 173.000 €`; normalizado, `173.000 / 5.600 × 1.000 = 30.892,8571 €/1.000`. Es el escenario docente sobre outer, no la validación CG10 ni los eventos nominales CG32. La suma `168 + 22 + 63 + 5.347 = 5.600` permite comprobar la cohorte.

Como ejemplo didáctico de contrato, un score `0,18` da AVISO; si el manifiesto tiene el `risk_threshold` F2 histórico `0.19082281465428477`, `risk_alert` sería falso. No es una contradicción: cada campo aplica su comparación. Ese ejemplo no afirma que la campaña haya producido una fila con score 0,18 ni traslada un umbral de un paquete a otro.

### Cierre y relevo hacia las preguntas

«Hemos recorrido qué aprende el modelo, cómo se compara, cómo se conserva una respuesta y cómo se interpreta su coste. Podemos consultar las fuentes de cada cifra y distinguir la latencia del modelo de la entrega completa. Ahora podemos responder preguntas de cualquier bloque sin presentar investigación, transporte o intervención humana como si fueran la misma prueba».

### Preguntas fuera de especialidad

- **¿Por qué RF y no una red neuronal más grande?** Porque se decide por el protocolo y sus errores/costes, no por complejidad. El estudio no encontró una sustitución que justificase cambiar el contrato vigente; el AE estudiado es de rareza y no una prueba de AGI.
- **¿Las 1.200 filas excluidas siguen formando parte de las 8.000?** Sí, como pertenencia conservada. No se usan para entrenar ni se vuelven a presentar como test independiente nuevo.
- **¿Dónde se ve una alerta del mismo evento?** En ES/Discover se contrasta `event_id` y hash RF con el registro. La campaña actual incluye un recibo y una captura concreta; no implica que alguien del equipo haya hecho ya el ensayo.

## Comprobación de esta preparación

Se contrastaron las tablas de ambas guías con los siete `run.json` del archivo raw, su CRC y sus 238 hashes; también las identidades, unidades, sumas, fórmulas y enlaces locales citados. Esta preparación modifica texto: no ejecuta entrenamiento, inferencia, campaña o pruebas de producto. Para #37 queda listo el contenido que cada persona puede estudiar y explicar; para #83, la explicación de la ampliación y su relación con el servicio. La participación observada y el ensayo se registran después de realizarlos, sin atribuirlos a la publicación de estas páginas.
