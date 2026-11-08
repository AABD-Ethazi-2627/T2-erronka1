# NiFi closeout — 2026-11-08

Estado: **bloqueado, con migración de consumidor ejecutada**. No merge, push,
despliegue ni aceptación.
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
