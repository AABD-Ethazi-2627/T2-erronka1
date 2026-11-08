# NiFi closeout — 2026-11-08

Estado: **imagen completa construida desde fuente y ejecutada; scans 0/0**.
No merge, push, despliegue ni aceptación E2E. El checkpoint actualizado al final
de este documento sustituye los pendientes del checkpoint inicial.
Base del checkout aislado: `481b6936e8a090b79e7e83d3b0e38bd1f21a1109`.
Se conservan las capacidades completas; no se selecciona el perfil que excluye
16 NAR. `runtime_approved:false` sigue vigente.

## Evidencia actual y procedencia

Cache propia Windows: `C:/Users/unaiu/.cache/cnc-closeout-nifi-20261108`.
Daemon usado: Docker Desktop `eab72f91-4cdf-4d18-a6dc-e1160f26af25`,
8.329.531.392 bytes RAM. El daemon de Fedora es distinto; no se atribuyen sus
imágenes o caches a esta ejecución. Todos los contenedores propios de NiFi
usan prefijo `cnc-closeout-nifi`; el builder propio se llama
`cnc-closeout-nifi-builder`, limitado a una CPU y 2 GiB. Sin prune.

`gh run download 41833235278 -n image-nifi` descargó el artefacto vigente
13328790828, fuente `6d67bc2ec72d931486174b906654bcc089250cba`.
El scan normal contiene cero ocurrencias; el nested contiene **63 ocurrencias /
59 tuplas CVE-paquete-versión distintas**. Este scan es del CI anterior, no del
candidato local histórico ni del nuevo build. Las 15 tuplas señaladas por Muse
pertenecen a otra etapa de la campaña y no sustituyen estos informes.

La [página oficial de Apache](https://nifi.apache.org/download/) sigue ofreciendo
2.12.0. No hay una versión posterior verificada que cierre estos bloqueos mediante
un cambio simple de imagen. Tag original resuelto por API a commit
`19f4df8e048e91d87d3e4967c69b1298f9dbe450`; archivo codeload SHA256
`990d11f202444b32780209a915ee404040eb7e1c86d63f80b36a9a7e69b65f64`.

Imagen stock original fijada:
`apache/nifi:2.12.0@sha256:6f7f2840dbf178c6dd3fa13435b9b358f3be3c6fb7417de467a35a267f4d28ad`;
config local `sha256:a0b4fe3a9c75b13bf3650da0f462a652a91809232a847a6a1ac9449ecdefbabd`.
La primera descarga se interrumpió por timeout de 60 s del MCP PowerShell;
tras comprobar ausencia de imagen completa se continuó con proceso aislado.
La segunda descarga terminó correctamente; no fue un segundo build concurrente.

## Wire: consumidor concreto identificado

`wire-carriers.json` contiene la búsqueda recursiva en los NAR originales copiados
del contenedor stock nunca iniciado `cnc-closeout-nifi-source`.
Los nueve artefactos Wire 5.2.0 están dentro de `nifi-aws-nar-2.12.0.nar`.
Su consumidor externo es `schema-registry-serde-1.1.24.jar`: siete clases
referencian `com/squareup/wire` en su bytecode. NiFi Protobuf lleva por separado
Wire runtime/schema **6.4.7**, coincidente con su POM upstream. Por tanto no se
debe sustituir Wire a partir del nombre del componente Protobuf ni mezclar
schema 5.2 con runtime 6.

Fuentes oficiales examinadas:

- [AWS Glue 1.1.27, commit b280404](https://github.com/awslabs/aws-glue-schema-registry/blob/b280404e615b4e63e2fb33b1aedc228e039fbf31/pom.xml): aún Wire 5.2.0.
- [AWS Glue 2.0.1, commit b47e716](https://github.com/awslabs/aws-glue-schema-registry/blob/b47e716743c64ec3fb7f4e3e780a32e2f0cff0b5/pom.xml): Wire 7.0.1, cambio mayor no elegido a ciegas.
- [Wire, límite negativo](https://github.com/square/wire/security/advisories/GHSA-7xpr-hc2w-34m9): corregido desde 6.3.0.
- [Wire, overflow positivo](https://github.com/square/wire/security/advisories/GHSA-9rm7-3qhh-h2mc): corregido desde 6.4.5.

Se ejecuta reconstrucción del consumidor AWS desde fuente original 1.1.24,
commit `c6a911301ea8ca72260bed3f2dfda83f3effcba2`, tar SHA256
`acd3b1ae461282698c3a3cb08842a5e6180660d5ad5427d2ab1932f10208bcfc`.
Primera variante: Wire 6.4.7/Kotlin 2.4.20, conservando tests upstream.
El intento Windows/JDK21 falló con Lombok 1.18.26; el segundo, con Lombok 1.18.30,
ejecutó 118 tests common pero no pudo generar los tests Protobuf por límite
de longitud de línea Windows. JaCoCo 0.8.8 tampoco soporta clases JDK21;
esos resultados no son aceptación. La ejecución Linux usa Maven oficial
3.9.11/JDK17, config de imagen fijada por manifest
`sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82`,
una CPU/1,5 GiB, heap512 MiB y repositorio Maven privado. No se desactivan tests.

## Baseline runtime stock ejecutado

Contenedor `cnc-closeout-nifi-stock-smoke-v2`, una CPU/1,5 GiB,
heap512 MiB, sin red externa ni puertos publicados ni volúmenes del usuario.
La primera ejecución sin host explícito terminó con
`UnresolvedAddressException`; la siguiente fija HTTPS host127.0.0.1 y consulta
localhost para SNI válido. Acceder mediante IP produce 400 `Invalid SNI`;
no se desactiva esa protección del servidor.

`stock-smoke-proof-4/cold-api-smoke.json` registra:

- UI200, login201, seis lecturas API autenticadas200.
- Control anónimo401 y credenciales falsas400.
- Tipos registrados: 294 processors,125 controller services,10 reporting tasks,
  ocho parameter providers y cinco registry clients.
- Los23 tipos/bundles modernos declarados por `nifi-flows/*.json` están en el
  registro vivo, incluidas las interfaces expuestas por implementaciones.
- SMB, Groovy, Kafka y Elasticsearch permanecen registrados.

Se implementa `deploy/images/nifi-patches/closeout/smoke.py` para repetir esta
captura e identificar daemon/config de imagen/contendor/límites y fuentes.
El endpoint real para tipos de registry es `/controller/registry-types`;
el endpoint `/flow/registry-types` del procedimiento previo devolvía404.
La comprobación inicial fallida se conserva como `stock-smoke-proof-1`.
Una iteración de comparación clasificó erróneamente interfaces como tipos
instanciables; se corrigió usando las declaraciones `controllerServiceApis`
del registro vivo, con control negativo de interfaz ausente.

Esta evidencia prueba arranque, UI/autenticación y registro frío de tipos;
no scheduling, restauración persistida, TLS trust ni integraciones SMB/Kafka/ES.
La captura loopback usa el certificado autofirmado sin validar su cadena;
`tls_trust_qualified:false` queda explícito. No se guardan credenciales ni JWT.

## Checks y continuidad

Antes de editar: Python3.12 Fedora,122 tests y43 subtests pasan en
`test_nifi_candidate_context.py`, `test_patch_nested_jars.py` y
`test_nifi_runtime_profile.py`. El warning ZIP de nombre duplicado pertenece
al fixture negativo. Un intento posterior de WSL falló con
`Wsl/Service/WSAETIMEDOUT`; no se presenta como test ejecutado.

Operaciones activas a este checkpoint:

- Build original `deploy/images/nifi.Dockerfile --target runtime`, tag
  `cnc-closeout-nifi:baseline`, `UV_BUILD_JOBS=1`, builder propio2 GiB/unaCPU.
- La compilación inicial `cnc-closeout-nifi-wire6-build` terminó exit1 con la
  incompatibilidad real del constructor `ProtoFileElement`. Se corrigió una
  llamada con las dos líneas exactas publicadas por AWS2.0.1. La fuente completa
  corregida tiene SHA256 `d1c026cc89599c4575ca72ed4a5699373831bfc91fd40fe40940f922e5e0e872`.
- La reconstrucción corregida `cnc-closeout-nifi-wire6-build-v2` terminó exit0:
  **1445 tests, cero fallos/errores/omitidos**,38 XML Surefire comprobados,
  Checkstyle0 y cobertura cumplida. Duración Maven3m25s. Conservó todos los
  tests upstream y creó identidad explícita `1.1.24-cnc-wire6.1`.
- `wire6-readers-3` ejecutó seis controles en JVM21 con lectores reales extraídos
  de los NAR originales: Wire6.4.7 pasa todos; Wire5.2 falla tres controles,
  manteniendo ambos inputs válidos correctos. Se identifican ejecutables,
  módulos JVM, NAR/JAR, clases y logs por hash. No es prueba del loader NiFi.
- Los diez tests nuevos pasan en Python3.12 Windows; Ruff del código nuevo pasa.
  Evidencia resumida y hashes en
  `deploy/images/nifi-patches/wire6/verification-20261108.json`.

El siguiente bloqueo concreto de Wire es la clausura instalada de su compiler:
JavaPoet0.6.0/KotlinPoet2.0.0/SwiftPoet1.6.5 y serialization1.4.0 del AWS NAR
difieren de las dependencias requeridas por Wire6.4.7. La nueva familia declara
JavaPoet0.12.0/KotlinPoet2.2.0/SwiftPoet1.6.11/serialization1.10.0/Kaml0.104.0.
No se instaló el Serde reconstruido ni un reader aislado sobre esa clausura vieja.
La prueba Maven con su resolución propia no prueba la clausura mediada NiFi.
Esto preserva capacidades y evita presentar el mismo fallo de ABI como solución.

Pendiente: resolver consumidor Wire con tests, reconstruir imagen servida sin
supresiones ni pérdida de NAR, scans normal/nested de sus bytes, runtime por
familia y flujos/integraciones reales. El histórico perfilCNC no tiene baseline
cold OCI independiente congelada; no se cambia su pin ni se afirma que sea
construible. Cero findings sigue siendo el criterio de cierre de PR119.

## Checkpoint de imagen completa y contraste upstream

Se construyó y ejecutó `cnc-closeout-nifi:full-stock-1`, config
`sha256:2660252c8785f61c22af3aefca41fc66de5da551cb388fff8a59a5c97a46f4d3`.
Su audit corresponde a
`sha256:923b2b5030361aba61286c02cbe297f70896b3f8d30d561e41b9297652121fb9`.
Ambas imágenes están en el daemon Docker Desktop identificado arriba. Trivy
0.76.1 fijado por digest `790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c`
terminó con **0 hallazgos normales y 0 anidados**, todas las severidades, sin
ignore-unfixed ni supresiones. `enforce_image_scan.validate`, pasando el tag
local real como `expected_artifact`, devuelve `[]` en ambos informes. Los
`Metadata.ImageID` coinciden con los config IDs indicados; no se reetiquetan
imágenes ajenas ni se modifican los JSON del scanner. El primer intento nested
falló por lock compartido con el scan normal: se repitió secuencialmente y pasó.

El ensamblado `full-overlay-1/changes.json` registra 86 cambios. Conserva todos
los NAR y preserva los registros ZIP y metadatos ajenos a cada corrección.
Los 215 archivos raíz se comprobaron contra el lock original antes de editar.
El audit expuso 1879 dependencias anidadas. La baseline de la imagen del proyecto
es `1fc16ff6b241570ae538856fb59ebb90d5a9dec27df98b7e4ac8da89f9a22fe7`,
con scan normal 0 y nested 63 ocurrencias/59 tuplas; no se confunde con la
imagen Debian original, cuyo scan incluye paquetes de otro sistema base.

Pruebas reales de la candidata completa, conservadas en la cache indicada:

- `full-stock-smoke-proof-1/cold-api-smoke.json`: UI200, login201, API anónima401,
  contraseña errónea400, cinco registros de tipos200 y 23 tipos de flujos
  declarados presentes. Red `none`, sin puertos publicados, heap512MiB,
  límite1536MiB y una CPU. No es ejecución de flujos SMB/Kafka/ES.
- `wire6-installed-1/correct-jetty.log`: clases cargadas de los JAR instalados,
  cadena real NarClassLoader/Jetty, cuatro roundtrips proto2/proto3×PHP0/1 y
  seis controles Wire. El control original falla con `hasPhpGenericServices`
  en Protobuf4. El fork `.5` conserva la opción PHP42 como campo desconocido,
  utiliza `Message.Builder` común y aporta un descriptor privado compatible;
  no altera Protobuf global ni elimina fixtures. La primera prueba instalada
  apuntó mal al directorio Jetty; se corrigió y repitió sin ese warning.
- `installed-families-1/run-nifi-gcp-nar.log`: nueve módulos OTel1.67 identificados
  por hash/origen y consumidor SDK ConfigUtil, trazas, baggage, métricas, logs,
  W3C válido/inválido/sobre-límite ejecutados a través del loader GCP instalado.
- `installed-families-2/run-nifi-amqp-nar.log`: Rabbit5.37 y Netty4.2.18 instalados,
  handshake/canal/publicación/cierre, peer malformado, controles de framing y
  TLS JDK; fixtures locales, no broker externo. El intento de compilar el
  fixture con `--release17` falló por ExecutorService AutoCloseable; se compiló
  con Java21, que es el requisito real de esta distribución, y pasó.
- `wrapper-runtime-2`: Guava simple y sombreado Hadoop/Iceberg, controles de
  deserialización y roundtrips; Hazelcast JSON/serialización y Jackson2/3;
  Parquet JSON y archivo/footer UNCOMPRESSED de tres filas, old/fixed. Iceberg
  original no contiene CompactHashMap: se prueban sus dos clases presentes y
  las tres de la candidata, documentando esa diferencia. Su Guava completa
  añade861 clases respecto de la selección minimizada; no se oculta el tradeoff.
- `hadoop-runtime-2`: parche anterior pasa70 casos y rechaza las dos medias
  correcciones. El Hadoop original también falla con Snappy1.1.10.8 para datos
  normales incomprimibles (`newLimit > capacity`). Esto no se atribuye a la
  nueva candidata ni se presenta como prueba pasada.

El lote inicial de wrappers no ejecutó Java por CRLF en el launcher; se corrigió
a LF. Posteriormente se completaron los controles anteriores. Los avisos SLF4J
sin proveedor pertenecen a JVM de componente aisladas; la instancia NiFi no
registró ERROR de arranque en la inspección realizada.

### Correcciones oficiales publicadas y pendientes

La distribución completa oficial continúa en2.12.0; `nifi-api2.16` no es una
distribución. Se contrastaron los PR y commits con GitHub API, no solo títulos:

- [NiFi11714](https://github.com/apache/nifi/pull/11714), merge
  `e572af9b1c3d03e71deb4effe3b7f9b799d447bb`: Jackson2.22.3/3.2.3, misma
  corrección oficial utilizada. Los Jackson2.21/3.1 sombreados en Hazelcast
  requieren sus patch releases oficiales2.21.7/3.1.7 y reconstrucción del wrapper.
- [NiFi11569](https://github.com/apache/nifi/pull/11569), merge
  `0082de161b1beeb829c676f26a8b842129107ea1`: Wire6.4.5→6.4.6 del consumidor
  Protobuf de NiFi. El NAR publicado ya contiene6.4.7. No corrige el Wire5.2
  independiente de AWS Glue; se conservan los dos consumidores.
- [Parquet3846](https://github.com/apache/parquet-java/pull/3846), merge
  `52339e7902d64b12ef526657a565a96a690db022`: Jackson2.22.3 oficial en rama1.18.x.
  No había wrapper Maven posterior a1.18.1 en el metadata consultado. Se reutiliza
  esa dependencia oficial bajo su namespace; no se reimplementa Jackson.
- [Iceberg18453](https://github.com/apache/iceberg/pull/18453), merge
  `87fed79bf013d77fee320c63b4ce5353c7355e5a`: Guava33.7.2. La release1.12.0
  aún contiene33.7.1 vulnerable. [Backport18753](https://github.com/apache/iceberg/pull/18753),
  head `e37152ea2cc701fea5e6f3edcb5080ee3dc4fb40`, y18761 siguen abiertos.
  El backport documenta pérdida de `Queues` con minimize; nuestra reconstrucción
  conserva la biblioteca completa, con el aumento de clases declarado arriba.
- Hadoop shaded-guava1.6.0 oficial contiene Guava33.7.2; se usa ese artefacto
  publicado en lugar de reconstruirlo localmente.
- [Snappy766](https://github.com/xerial/snappy-java/pull/766), merge
  `2dc4622cc0ddc3f2adbbee24c8c66e3973ae9917`, publicado en1.1.10.12: restituye
  el contrato capacity/position de ByteBuffer. Se descargó el JAR oficial,
  SHA256 `1c03ce77b3f2e926c25a952612e372404d80bc88c6c8052bede964804fabd732`.
  El checksum SHA512 del repositorio devuelve404; se contrastó el SHA1 publicado
  como control de transferencia y se fijó SHA256 localmente, sin atribuirle firma.
  `snappy-official-1/hadoop-original.log` demuestra que Hadoop original aún
  falla con4096 frente a4809 bytes; `hadoop-capacity.log` pasa70 casos conservando
  solo el cambio local de capacidad. Este delta menor sustituye las dos
  modificaciones anteriores en el nuevo Dockerfile.
- [Hadoop8900](https://github.com/apache/hadoop/pull/8900), merge
  `0fbbb871af85733a161f0f369753b2d9c579b7bc`: actualiza Snappy a1.1.10.12,
  pero su diff no modifica SnappyCompressor. La prueba anterior justifica el
  delta local restante; no se declara suficiente un bump por su título.

El nuevo Dockerfile construye AWS desde el commit original con su suite completa,
comprueba contenido de todas las clases/recursos contra el build probado y
ensambla todos los parches dentro del target runtime/default. Esto resuelve el
problema estructural de una overlay externa no servida; su ejecución actual se
registra en `full-source-build-4.log` y no se equipara todavía al scan de la
candidata anterior. Los intentos previos fallaron por nombre de paquete JDK,
sufijo Windows `.exe` y profundidad de la ruta de herramientas; se corrigieron
sin cambiar tests ni criterios de aceptación. El build UV anterior permanece
cacheado; no se repite su compilación de47 minutos.

Checks ejecutados:184 tests/80 subtests y274 tests/42 subtests en Fedora Python3.12;
Ruff de todos los Python modificados y nuevos pasa tras corregir11 observaciones,
sin exclusiones nuevas. Los warnings ZIP duplicado son fixtures negativos.
El E2E integrado, la migración de datos y el gateway LAN pertenecen al coordinador;
ninguna prueba de descubrimiento de tipos sustituye esas validaciones.

## Resultado final entregable

El build real del Dockerfile terminó exit0, target `runtime`, tag
`cnc-closeout-nifi:full-source-2`, config
`sha256:ce5cc16846311a7638412be695c8bceefb4799c28b62064afb8de0629e492fa5`,
manifest `sha256:d4bab99f8865f4a059c6f7e3992543021535d50ec0577770d455487a87cb5624`.
La suite AWS original vuelve a pasar1445/0/0/0 en el build, Checkstyle y cobertura
incluidos, y todas las clases/recursos de producción coinciden con el build
probado. La misma ruta está conectada al target final/default; no requiere una
overlay externa ni cambiar CI para incorporar las correcciones.

Normal `full-source-normal-scan-2.json`: SHA256
`f4d5b0d2c87218413c4d9dce876d02d5e31c55add0849023a81db5596c14f535`, gate `[]`.
Nested exacto `full-source-nested-scan-2.json`: SHA256
`61a1d2e061f496eba514f265895b8ef21c2b67f0238e73b890ffc90b92752081`, gate `[]`.
Este audit deriva directamente de la imagen servida anterior, config
`sha256:2ec71eb0a8a3ed80e685dce1ec3f5bbf0eeeba719c2db155f30d421950bb3a24`,
tag `cnc-closeout-nifi:full-source-exact-audit-2`. No se atribuye a la imagen
servida el ID de su audit. El target `archive-audit` del Dockerfile también
terminó exit0, exponiendo1879 ocurrencias; se conserva aparte como
`cnc-closeout-nifi:full-source-audit-2`, config `408c9e571d97f4f9399184e194fe0b9b89bcc7a0d54e505ddf928151a421f920`.
Se usó el audit exacto para el gate final porque una nueva compilación Maven
puede cambiar timestamps ZIP/comentarios generados sin cambiar las clases.
No se afirma reproducibilidad byte a byte de esos timestamps.

La nueva instancia fuente pasa nuevamente API/auth/UI y todos los controles
instalados Wire, OTel y Rabbit. `hadoop-installed-2` pasa70 casos con el fork
capacity-v3 real y Snappy oficial1.1.10.12, más roundtrip con limit vacío/offset
y rechazo del slice pequeño antes de JNI. `libraries-installed-3` ejecuta Guava,
LZ4 y Snappy reales desde el AWS NAR, con origen/hash comprobado, roundtrips y
controles negativos acotados. No se ejecuta JNI hostil con la versión vulnerable.
Un primer intento de copiar ese fixture apuntó al root de NAR de otra familia;
se corrigió al root AWS existente y pasó.

`wrapper-content-source-2/result.json` compara los wrappers realmente instalados:
las12006 entradas de payload Hazelcast y1219 de Parquet coinciden con las
ejecutadas anteriormente; solo cambia su JSON explícito de procedencia por
el JDK de ensamblado. Las2016 entradas de Iceberg son idénticas, incluido su hash
de archivo. Esto complementa las pruebas reales de esos consumidores anteriores;
no se sustituye una prueba de ejecución por una calificación estática nueva.

Se verifican **119/119 NAR**, ERROR de arranque0 y preservación exacta de tipo+
bundle en los registros:294 procesadores,125 servicios,8 proveedores de parámetros,
10 reporting tasks y5 clientes de registro. El resumen con hashes de pruebas,
identidades y límites explícitos está en
`deploy/images/nifi-patches/closeout/verification-20261108.json`.

Tras capturar las pruebas se detiene el contenedor fuente y el builder propios,
conservando contenedores parados, imágenes, volúmenes y caches. Sin prune ni
alteraciones de servicios/datos ajenos. No queda ninguna compilación NiFi propia
activa. No se declara cerrada la aceptación E2E del coordinador ni se realiza
merge/push/deploy.

Snapshot tras detener los recursos: MemAvailable global6.338.508KiB
(aprox.6.33GiB) y espacio libre del filesystem Docker967.866.748.928bytes.
El builder confirma `Status: stopped`; `docker ps` filtrado por el prefijo propio
no devuelve contenedores activos. Es una medida puntual compartida, no una
reserva para CG32; el coordinador debe usar su preflight en el instante del E2E.
