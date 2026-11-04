# Conciliación documental de la candidatura local — 03/11/2026

Este documento relaciona el corte histórico de la memoria con la integración local
`77903937fde925e00bb46e8c32395e9f94f2f802`. Se han leído el manifiesto, el verificador,
los cambios de código/configuración indicados abajo y sus informes de procedencia.
Esta conciliación no ejecuta servicios, modelos, builds ni suites técnicas; ejecuta
solo la comprobación documental. El coordinador realiza otros ensayos por separado.

## Qué significa cada identidad

- `base_commit=f770932…` y `base_tree` siguen siendo la base histórica de las 40
  filas de la matriz. Sus comandos `git show` y revisores `Pendiente` se conservan.
- `historical_snapshot` conserva sin modificar sus 18 hashes, comprobados leyendo
  la revisión histórica con Git. Tampoco se reescribe el registro PR68 al corte de
  octubre: `not_integrated` es metadata histórica, no el estado remoto de noviembre.
- `files` es un inventario seleccionado de los bytes **actuales** usados por esta
  memoria; no es una firma, aceptación humana ni inventario completo del repositorio.
  Ya se había ampliado después de la base histórica. Tenía 25 discrepancias ajenas
  a estos documentos, enumeradas al final, además de las modificaciones documentales
  de esta conciliación. Se registran los hashes anteriores para poder revisar el delta.
- `local_reconciliation_20261103` fija el commit de código inspeccionado y el alcance
  de esta actualización. Un cambio posterior en un fichero inventariado debe volver
  a examinarse y documentarse: no se desactiva el verificador para evitar esa deriva.

El alcance de entrenamiento activo permanece en 8000 filas, con 5600 fit, 1200
validación de desarrollo y 1200 excluidas por inspección previa. Este cambio no
vuelve a evaluar el test ni altera la definición de clasificación contemporánea.

## Cambios clasificados antes de actualizar hashes

| Grupo de ficheros con deriva | Cambio inspeccionado y efecto documental | Evidencia y límite |
| --- | --- | --- |
| `pyproject.toml`, `uv.lock`, `scoring/requirements.txt` | La clausura runtime incorpora DuckDB/PyArrow/HTTPX y concilia dependencias de servicio; se mantiene el entorno científico fijado en lugar de adoptar PyArrow 26 incompatible con NumPy 1.26. | [Conciliación de dependencias](../evidence/DEPENDENCY_RECONCILIATION_20261103.md). Un lock/export comprobado no certifica todas las imágenes. |
| `scoring/score_api.py`, `scripts/cg32_lab.py` | Router GET opt-in y punto de extensión del laboratorio. No sustituyen la respuesta canónica POST ni prueban por sí solos un recorrido vivo. | [Contrato de lectura](../backend/READ_API.md), [candidato de integración](../integration/README.md). |
| Cuatro Dockerfiles de uv/API/NiFi, inventarios `images.json`/`build-targets.json`, `image_inventory.py` y su test | Pins reconciliados, dashboard dedicado, runtime de lectura y etapa uv común con concurrencia acotable. Los inputs se comprueban; el éxito de construcción/arranque requiere su propia evidencia. | [Builds seriales](../integration/LOCAL_IMAGE_BUILDS.md), informe de dependencias. No se reduce el preflight del laboratorio completo. |
| Cinco workflows (`dashboard`, `dependencies`, `es-bind-safety`, `ml-study`, `validate`) | setup-uv fijado actualizado; descubrimiento de pruebas del dashboard, probes de imagen y cobertura de archivos NiFi anidados. | Código versionado de CI; esta actualización no ejecuta ni declara verde el CI de un SHA nuevo. |
| Dockerfiles ES/Filebeat/Kibana y `kibana-patches/package*.json` | Candidatos de bytes JAR/npm, diagnóstico OS separado de Filebeat y controles de consumidores. | [Seguimiento acotado](../evidence/KIBANA_FILEBEAT_BOUNDED_20261103.md); los ensayos posteriores se atribuyen aparte, sin convertir preparación de fuentes en build final. |
| `enforce_image_scan.py`, `test_image_scan_gate.py` | Cobertura de paquetes exigida para dashboard y archivos anidados NiFi. | El gate sigue rechazando vulnerabilidades no verificadas; un hash actualizado no concede excepciones nuevas. |

Se añaden al inventario las implementaciones y documentos de lectura/integración
que soportan esta candidatura. Los informes antiguos conservan sus fechas y sus
propias advertencias: los resultados posteriores amplían evidencia concreta, no
corrigen retrospectivamente un fallo ni convierten una ejecución anterior en otra.

## Resultado local atribuido y puertas pendientes

La [evidencia fechada del coordinador](../evidence/LOCAL_PIPELINE_BROWSER_20261103.md)
separa tres recorridos con datos sintéticos:

1. HTTP/API/CG15/ES → Chromium: cuatro páginas, modal, refresco, escritorio/móvil y
   degradación/recuperación de ES dentro de la misma sesión del navegador.
2. Worker durable por stdin → API/CG15/ES/GET → navegador: identidad canónica de
   ese evento y sensores contrastados; no hay ACK de Kafka en ese recorrido.
3. Filebeat vendor fijado por digest → Kafka candidato → worker → API/CG15/ES/GET:
   captura vinculada por bytes y clave, offset 0 consumido y commit 1 observado.
   Su replay posterior usa stdin. El evento Kafka de ese informe permanece
   pendiente de reconciliación propia en navegador.

El modelo es un bundle de prueba local. La matriz offline de octubre no queda
ligada automáticamente a él: la lectura de evaluación exige procedencia verificable,
hash de modelo y umbral coincidente, y falla cerrada cuando faltan. AVISO/CRITICA
0,15/0,70 y la regla de decisión del modelo son políticas distintas. El panel muestra
estado inferido actual y antigüedad; no predice siete días, ETA o RUL ni pérdidas
como score multiplicado por coste.

El informe registra una imagen Kafka construida y con gate de escaneo pasado, y
un target **OS** de Filebeat construido. El productor del ensayo fue Filebeat vendor;
no acredita la imagen final parcheada. Las builds API/dashboard en curso al elaborar
este documento no se cuentan como terminadas. NiFi/Kibana de esta candidatura,
escaneos/runtime finales, RSS/concurrencia, capacidad del conjunto simultáneo y
recorrido SMB actual siguen requiriendo evidencia propia. No se repiten ni se
invalidan aquí los ensayos históricos SMB/Kibana de octubre.

Para los descriptores G39/G61/G62 falta una vinculación y aceptación independiente
de evaluación/modelo cuando proceda. G41/G49/G65/G66/G71/G77/G90/G92/G96 requieren
valorar el recorrido exacto y su cobertura, no sumar las etapas como si fueran una
campaña simultánea. G14/G46/G80/G85/G100 no se cierran con un microbenchmark ni con
estas pruebas de un evento. G87 necesita su alcance de accesibilidad y revisión
humana; una captura móvil no acredita conformidad global. Todas las 40 filas
conservan la revisión educativa pendiente. Explicación de los integrantes, acuerdos,
firmas, equivalencia SMB/NFS, defensa, Moodle y entrega siguen siendo actos humanos.

## Reproducción documental

Desde el checkout de esta candidatura:

```sh
python3 scripts/check_cg25_memory.py
git diff --check -- docs/memoria
```

El primer comando exige las 40 celdas, revisores pendientes, enlaces/anchors,
hashes actuales/históricos y alcance activo. Su salida no es un resultado de CI,
una repetición de las suites técnicas ni una aprobación de la rúbrica. Los comandos
de ensayo están en los runbooks enlazados, con sus modelos y recursos requeridos.

## Inventario de la deriva previa

Hashes del inventario anterior frente a los bytes inspeccionados en `7790393`.
La actualización de README/ANEXO4 y este documento se registra además en `files`;
ninguno de estos cambios altera `historical_snapshot`.

| Fichero | SHA-256 anterior del inventario | SHA-256 actual inspeccionado |
| --- | --- | --- |
| `pyproject.toml` | `7985c47365465de682b83cf8ebf28d00fe61992259803df46a084f13259d192b` | `034084d48b7cee67f32ee042bca7fa8fa5f7bc709d163da26cd71acb04b416d2` |
| `uv.lock` | `8367a28e49a9b17035a1fd9c303db94a29113ca799dc67c5a0475d96593504d8` | `023da35f63b547e4cd09c0529d8d9cb8bf50827b626e61648e8b73bb15b4f149` |
| `scoring/requirements.txt` | `0e95d2a105d536b5cfb781ff7fb87e860678c3c0941c3306526015fd1e72da9a` | `d33ff0616388dcc56aeeea134732172cbb46980e64e227a19c3b77a8092e1381` |
| `scoring/score_api.py` | `013b6f8499e8dc555456d5548c67512bd99f27bd104e79d72a7e5ed1c099014e` | `7673b38ad5ab064e3eca2f34069ce741d27537d50b8717de372424f68fb359f4` |
| `scripts/cg32_lab.py` | `b0c23cc14964e1ef41124bb34dba508b7414a89d2401000937b2456586acea54` | `0498ecd63b9d81b7026b2d0bec8231c29ae7fb81c207380b4b6e1e916c396f8b` |
| `deploy/images/uv-stage.Dockerfile` | `7a0acdb7396c790e1743ebcaeb905510324923d61c62fc65fd309578285637cf` | `de1fd7afab25cc118c90bf7805d8a0d0034a4d6f7e0f3641609a70b5d6eb102c` |
| `deploy/images/uv.Dockerfile` | `7a0acdb7396c790e1743ebcaeb905510324923d61c62fc65fd309578285637cf` | `de1fd7afab25cc118c90bf7805d8a0d0034a4d6f7e0f3641609a70b5d6eb102c` |
| `scoring/Dockerfile` | `cc2059c9fc5f05e30b7de64dd6506886997bbc81c1cd5243e269a577f155a047` | `17a843475a66da46fd1706bccac43e63337297d46bd0e63b435e76b4c8c5f1c9` |
| `deploy/images/nifi.Dockerfile` | `ea18c3b07f8854dbb4f19e00e713ceeec92a0ac852eea162ce912036d3ade99e` | `a6e0c009b0656fa8c709511e132449f4c49b4dc14ba4c7dac5757f6c1f9f4b83` |
| `deploy/images.json` | `70316311bb25a12199c0537b41c79e45bdf7d88f8061d4d301117b1aa9975789` | `3251117ba04ef51276740ac0ef2553c604fad2a1ab762cdb3830ccfee0995cc1` |
| `deploy/build-targets.json` | `ce5c4c8f0d30dfc554e5967b86bfbc77f16c616f4ac1ec46f03c37426893e593` | `5852a393ca394f08c7351cb20ad30ee77d398ac89395ca92b9d96e89fbe449f2` |
| `scripts/image_inventory.py` | `2b47caac6bff09eff606224299d84e4498349933caa992502ffda179402e068e` | `5f4ea60005ce08e3f76cf56b05c4507dbde0a14822159aa07ddcb7101dd480ba` |
| `tests/test_dependency_infra.py` | `b22aaa323f24286a54cd0bce497db0a3c86d385d0fb375188373719614506a5d` | `a387b9477014e1677deb153fdb4aa3b8a572aec09084563f31f6cda43e426550` |
| `.github/workflows/dashboard.yml` | `272829e339478d6b0319566e17e5aedd5439785056ad3713f18e536281413095` | `b7e8f5c6b81b87af701efbd095928e3d770cf9477e50209352ff8f2a54161a37` |
| `.github/workflows/dependencies.yml` | `69077b9a8b629a3b7735a65eb59dee7e3d4f2cb273bef62c60bb1ffb2629854b` | `bd8a367fb270594f3a664f13dab0501f0f0ef30b3aef5277dc0982c63006a878` |
| `.github/workflows/es-bind-safety.yml` | `c7dd6a94ee45812cf05d7448d4744e621a56b75289992cef5a44516d6da2f734` | `95553c0af814f5bba1ccbe40cc0c17f0edcce57c9d7e6b3cfd835c2ec43626a7` |
| `.github/workflows/ml-study.yml` | `0c00ed281375a5c6ee170f829e4a1c2b88005eb92c1cfbad50c23397bd575018` | `22fe2429f482a008727cc2ae8bc03eeb61f84774ebaa6cb17e35053887c5ab1e` |
| `.github/workflows/validate.yml` | `b7029429a7b678a7baaf2a1861b1ca5c7c6d37950bfef3e767f9ebdffa8ceefd` | `6c5c1af017f0104e3c27fad29be8a94c9e6efe0b72c6897e4607105337d8113e` |
| `deploy/images/elasticsearch.Dockerfile` | `188e64e8d404ba8be0f40fb1b776d6cf432c4cf755b04464aa72cbd578e47d3c` | `7cf7364680690a560ee5004d0ef4e2a7a6c3222159c62556da4568136d4fc73a` |
| `deploy/images/filebeat.Dockerfile` | `01b40d29f663174315c96f9cb46b82c0b81d4a564ca7f5b423da502f169de6b2` | `e0947e3fa4030ba55a60541dfd3d8de3642d6577ee27867e8635c8968a575ad6` |
| `deploy/images/kibana-patches/package-lock.json` | `ab294885dd369f387fcb00aa9c4cacb0a39b77c9256a9298e7387612e52aedfe` | `e90fbb8f5cfc7d4e68829a2941aa9a8d50e2908317f5309c8fe3fa0b16f4b855` |
| `deploy/images/kibana-patches/package.json` | `8869584ee2528db729eea4b568fcdc3a2caffa8a69c51e0a09e9a6fa64936d23` | `76adab4ad02ee6b4673b9715a74e30caf3af7d7229c3de4015118bd48fe2783b` |
| `deploy/images/kibana.Dockerfile` | `90d25722f7539564a027e141c4b1fe1daaad66e5865f353fbe20947bc30e04da` | `331658ec32c0193e9d71cd82739b164f00fa5efb85063a769a6f56bab5d7d3a6` |
| `scripts/enforce_image_scan.py` | `2e987ddbf5043bb7ec4a636328424bf17305ad05c76592bc8489f9afe463b587` | `a7f6486085b229f3f7e92d27eab01890edfaf8d3567f82a94692fb1e7570eb41` |
| `tests/test_image_scan_gate.py` | `11697399c1a620ea59d4cab7963f71c9d7d7cacc8d0854de2cbe3743a5705afe` | `65ca31fd654b2a4b1eeb39ed141d8ce5a058c94ca77a3914b79d384bf418d131` |

## Ajuste posterior de espera de metadatos

Tras la conciliación de `f9a949d`, se acota también la consulta inicial de
particiones del observador Kafka. La función pública del fork usaba una espera
sin plazo; el adaptador explícito conserva su comportamiento y limita cada
espera de refresco a 15 segundos, restaurando el estado en caso de error. Se
añaden tres regresiones sin servicios (48 pruebas de ambos runners pasan).
Los runbooks aclaran dónde obtener el nombre del contenedor y enlazan la
preparación Filebeat desde el ensayo Kafka. No cambia ningún contrato, modelo,
resultado histórico ni aceptación humana. El inventario actual actualiza solo
el runner Kafka, su test, esos dos runbooks y este documento, tras revisarlos.


## Ajuste posterior de selección del archivo comprometido

Sobre el padre `723ab6b29451578b27d7befdb4c8526310e6ae23`, se inspecciona el delta
local del índice de lectura CG15. El escritor añade la selección por fuente,
modelo, política, umbral, máquina y ventana UTC en la misma transacción que los
recibos aceptados. El lector toma un snapshot breve de SQLite en `mode=ro`, cierra
la conexión y comprueba los hashes del Parquet seleccionado y de su bronze original,
además del evento y recibo aceptado. Los objetos ajenos a esa selección dejan de
consumir el presupuesto de la petición. El test de existencia distingue una máquina
desconocida de una conocida sin observaciones dentro de la ventana.

Esta implementación no certifica la integridad de todos los objetos retenidos.
Los archivos anteriores sin cobertura completa del índice devuelven 503. La vía
recomendada es la migración **offline y explícita**, con todos los escritores detenidos:
`python -m scripts.archive_read_index /owned/archive --writer-stopped`.
La migración verifica recibos/predicciones y conserva los bytes de los objetos y
las tablas originales; GET nunca crea ni repara el índice. El Dockerfile de API
incorpora el helper de lectura. Esto describe el código inspeccionado, no demuestra
que una imagen reconstruida lo contenga ni que se haya migrado un archivo vivo.
También pueden completar la cobertura las predicciones duplicadas aceptadas con
nuevos identificadores de entrega por el escritor actual, si llegan a cubrir todos
los objetos y el índice no está sucio. GET sigue verificando cada entrada elegida.

El agente implementador informa de 129 pruebas y 126 subtests en ocho suites
focalizadas, más una regresión posterior de replay/bronze no canónico; también
informa Ruff y `git diff --check` correctos. Son pruebas locales con SQLite,
Parquet y ASGI, sin servicios ni red. Esta conciliación documental no las vuelve
a ejecutar: la comprobación independiente del coordinador y la validación de la
imagen corresponden a evidencias separadas. Los límites siguen siendo 20 000
objetos seleccionados (dos por predicción, máximo 10 000 predicciones) y 64 MiB;
la paginación no evita validar toda la selección. Los periodos densos todavía
pueden devolver 503. El escaneo global del escritor no cambia y no se afirma
caudal sostenido, RSS/concurrencia, SMB ni aceptación humana.

Se actualizan únicamente los hashes de `scripts/archive_consumer.py`,
`scoring/read_storage.py`, `scoring/read_api.py`, `scoring/Dockerfile`,
`tests/test_read_api.py` y `docs/backend/READ_API.md`, y se añaden
`scripts/archive_read_index.py` y `tests/test_archive_read_index.py`.
También se actualiza el hash de este apéndice. Los valores anteriores quedan en
`local_archive_index_followup.previous_current_hashes`; la base histórica,
`historical_snapshot`, el alcance del modelo y los revisores pendientes no cambian.


## Comprobación posterior en imágenes locales

El coordinador ejecutó en `b5d5d54` 894 pruebas y 374 subtests (4 omitidas),
y 29 pruebas del dashboard con `-W error`. El informe
`docs/evidence/LOCAL_CONTAINERS_20261103.md` distingue las imágenes API/dashboard
construidas y escaneadas, la copia migrada del archivo del ensayo Kafka, el replay
HTTP idéntico y la identidad visible en Chromium. Conserva también los intentos
fallidos (permisos del montaje, URL de prueba errónea y revisión Claude interrumpida
por memoria). No se modifica ninguna aceptación humana ni el alcance del modelo.

El README de integración enlaza esa evidencia; el generador de ZIP incluye el
informe. Se revisan solo esos tres inputs y este apéndice. Las afirmaciones sobre
NiFi/Kibana, SMB, campaña completa y modelo aprobado siguen pendientes.


## Preparación acotada de Filebeat

Se revisó `GO_BUILD_JOBS`: entero decimal positivo, exportado como GOMAXPROCS
y pasado a `go build -p`; no cambia las versiones fijadas ni el gate de imagen.
El coordinador ejecutó 22 tests y 18 subtests de guardia/escaneo, y verificó
el inventario de imágenes. Esto prepara una compilación local con un trabajo;
no demuestra todavía la imagen final ni su publicación Kafka. Se registran solo
Dockerfile, runbook, test nuevo y este apéndice; la base histórica permanece.


## Imágenes posteriores y TLS, alcance acotado

El informe local incorpora la imagen ES construida y sus dos análisis (feed
Chainguard y complemento Wolfi), 12 operaciones de compatibilidad en tmpfs
acotado, y el bloqueo real por espacio del ensayo en disco. No se cambian los
watermarks. Filebeat final compila con un trabajo, pasa el gate conservando la
excepción de módulo prevista y govulncheck confirma cero símbolos vulnerables
alcanzables en el binario; publica un evento real confirmado por Kafka. Ese
nuevo evento no se presenta como otro recorrido completo por modelo/UI.
La rotación TLS aislada pasa 1 test y 60 subtests. Claude no pudo completar
la revisión final (memoria y después límite API); no se inventa aprobación.

Se actualizan exclusivamente el informe, sus dos runbooks enlazados y este
apéndice. NiFi/Kibana y campaña completa siguen pendientes de recursos y
verificación; SMB, modelo aprobado y revisión humana continúan abiertos.


## Revisión Claude reanudada y completada

La revisión acotada del índice `b5d5d54` frente a `723ab6b` terminó tras
reanudarse el proveedor. No encontró errores de corrección bloqueantes. Leyó
cinco fuentes (de los tests solo los nombres); no ejecutó pruebas, Docker ni red,
ni revisó los helpers de contrato/plataforma o el modo de journal en ejecución.
No sustituye la evidencia de pruebas del coordinador ni la aceptación humana.
Se aclara que los duplicados aceptados con nuevos identificadores de entrega
pueden completar el índice antiguo, y que el acceso SQL directo permanece dentro
de la frontera de confianza. Esta aclaración modifica documentación, no código.
El ZIP anterior se conserva íntegro como evidencia histórica anterior a esta entrega
tardía del informe; la revisión se distribuye en una adenda separada.


## Seguimiento del PR119, 2026-11-04

CI de `6a11161` pasa 906 pruebas y 374 subtests, con cuatro omisiones, en
Python 3.11 y 3.12. La repetición local previa se interrumpió por memoria;
se conserva como intento sin resultado completo. El PR exige además revisión
de GitHub; no se cambia ninguna protección ni gate para permitir merge.

Se revisan cinco sustituciones acotadas de paquetes Kibana (systeminformation,
re2js raíz, decode-uri-component, Joi y @hapi/content), con lock SHA512 y borrado
de directorios viejos antes de COPY. El coordinador repitió las cinco regresiones
tanto con alias npm como con las versiones transitivas de la imagen vendor.
El Dockerfile las repite con el Node real de la imagen. Todavía falta construir
y escanear esa imagen: Hono, glob, minimatch y copias prebundled siguen abiertos.
Los paquetes nuevos conservan sus dependencias declaradas y los rangos comprobados
se satisfacen con las versiones vendor; el re2js anidado 1.4 queda fuera del rango
afectado y no se cambia de major sin necesidad.

El informe NiFi identifica 59 tuplas vulnerables anidadas y prueba mediante
bytecode oficial que actualizar solo Wire runtime a 6.3 rompería un constructor
que consume Wire schema 5.2. Es diagnóstico, no reparación ni excepción de gate.
Un backport separado está en investigación y no forma parte de esta entrega.
Estos informes y los inputs Kibana revisados actualizan el inventario actual;
la base histórica, el alcance del modelo y la aceptación humana no cambian.


## Adaptador Hono compatible con MCP

Se incorpora @hono/node-server2.1.3 porque el consumidor MCP1.32 admite
explícitamente esa rama, el peerHono4 existe y el Node de Kibana satisface
su requisito. El coordinador repite pruebas HTTP y MCPinitialize CJS/ESM y
controles de archivos estáticos codificados; el original1.19.17 reproduce200
frente al404 esperado. El Dockerfile repite estas pruebas con los módulos
y Node finales. No se añaden dependencias runtime; el lock conserva el resto
de entradas. Glob/minimatch, las imágenes finales y NiFi siguen pendientes.
La revisión independiente ha bloqueado promover el candidatoWire inicial;
el trabajo de lectores ampliados sigue separado de la imagen y del gate.


## Candidato Wire separado de la imagen

La revisión independiente bloqueó promover Wirev1. El implementador se detuvo
por autenticación de clavehardware; el coordinador conservó sus cambios y amplió
la prueba a44casos (original falla9), con pins de entradas, herramientas y salida.
El scanrootfs reconoce el fork renombrado por hash y conserva el hallazgo visible;
se rechazan inventarios sin cobertura. La varianteKMP se identificó sin clasesJVM.
Todo ello prepara revisión: no cambia NiFi, su classpath ni el gate. Faltan
comparación completa, inventario/classloaders reales, consumidores NiFi, nuevas
revisiones y ambos escaneos de imagen. El resultado de Claudev1 no se atribuye aV2.
El bundle incluye fuentes.java para que conserve la regresión del candidato.
Los archivos nuevos y documentos revisados actualizan el inventario; no cambian
la aceptación humana, la base histórica ni el alcance del modelo.


## Transporte del instalador Trivy

Los jobsAPI/Kafka en d7cfa18 construyeron sus imágenes, pero fallaron al
instalar Trivyv0.76.1 con curl exit6, antes de escanear. La falta de artefacto
fue consecuencia, no hallazgo de vulnerabilidad. El workflow añade un wrapper
curl local al job con reintentos y tiempos acotados; mantiene argumentos,
checksums, pins, severidades y gate. La prueba usa curl real contra503/503/200
en loopback y verifica tres peticiones, bytes finales y estado200. Pasan16tests
y18subtests. La recuperación del runner requiere la nueva ejecuciónCI.
No se afirma todavía escaneo verde ni se modifican las aprobaciones de GitHub.


## Instalación directa del escáner

El dashboard21ecb04 falló pese a reintentos. La URLreal del tarball del
instalador es get.trivy.dev: su resolución falla también desde la comprobación
local. La URLdirecta GitHub que se había probado no era la usada por el script.
Se instala ahora Trivy0.76.1 desde su release oficial con SHA256 fijo, coincidente
con digestAPI y checksum publicado; se omite solo el setup de la action, no su
escaneo. Se mantiene el binario para el gate anidado NiFi. La instalación directa
y un scanreal del candidatoWire funcionan y conservan el hallazgo. Pasan17tests
y18subtests, con rechazo de descarga corrupta antes de instalar. CI nuevo debe
validar el runner; no se cambia ninguna aceptación ni gate de vulnerabilidades.
