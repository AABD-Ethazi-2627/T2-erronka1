# Revisión independiente: escritor de ocurrencias, transporte RabbitMQ y correcciones M1/M2

- **Commit revisado:** `f4e32bf528536c36e5b14efbe702b68383c346aa`, tree `0f7b11f33e773a3578d1d8e6149f8a3e4b57a156`.
- **Cómo se revisó:** extracción con `git archive` a un scratch propio. El worktree padre avanzó durante la revisión hasta `c176080`; **esos commits posteriores no están revisados**.
- **Fecha:** 2026-11-04.
- **Modo:** solo lectura. Sin commits, push, PR, Docker, red ni servicios. Sin ejecutar la suite completa.

## Veredicto

**Apto como PREPARACIÓN. No acredita imagen, NiFi, gate ni aceptación humana.**

| Pregunta | Respuesta |
| --- | --- |
| ¿Están cerrados M1 y M2 del informe anterior? | **Sí.** Reproducido, con mutantes que confirman que los tests los protegen |
| ¿Hallazgos Critical o High? | Ninguno |
| ¿Hallazgos Medium? | Uno (M1): el subconjunto Maven diverge de Maven real en formas no fijadas. **Sin efecto hoy** |
| ¿Bloqueo técnico del escritor antes de ensamblar ocurrencias? | **Ninguno** para Guava 33.7.1, LZ4 y Snappy a nivel de escritor. Ver [condiciones previas](#condiciones-previas-al-ensamblado) |
| ¿Límites declarados por el padre? | Son honestos. Corrijo cuatro frases (L1, L3, L5 y M1) |
| Gate del escáner | Sigue en 59 tuplas (`verify.py:159`). `ea9e84f..f4e32bf` no toca `.github`, el Dockerfile, `expose_nested_jars.py` ni ficheros `.trivyignore`. Sin excepciones |

## Qué demostré ejecutándolo

Todo sobre los bytes de `f4e32bf`, con cachés propias copiadas y comprobadas por hash.

| Comprobación | Resultado |
| --- | --- |
| Hashes de la evidencia frente a `f4e32bf` | 17 de 17 fuentes y 180 de 180 artefactos coinciden |
| Inventario real, CLI | stdout **byte a byte igual** (`ba7c03e8…`), identidad `ce7f5a83…`, 2.040 ocurrencias, 156 archivos, 42,5 s, 54.676 KiB |
| Mapeo del escaneo con script propio | 17 grupos y 19 pares paquete-objeto (15 hashes distintos), todos con al menos una ocurrencia |
| Ocurrencias declaradas | Guava 33.7.1 = 7, LZ4 = 3, Snappy = 9, RabbitMQ = 1, shaded = 1 y 1. **Coinciden** |
| `verify.py` | `rc=0`, plan `a9836f8f…`, **igual** a `candidate-plan.json` |
| `verify_rabbit.py` | Las **siete** configuraciones pasan, `transport-component-tested-nar-mapping-pending` |
| Tests | 27 portables + 13 transporte + 6 negativos pasan **sobre `f4e32bf`**. Esto cubre que los 46 originales se ejecutaron antes de la última edición de `verify.py` |
| NAR frente a referencia oficial | AMQP `4d43e10b…` **y** `nifi-standard-services-api` `89aacd31…` iguales. `lib/slf4j-api-2.0.19.jar` igual al pin |
| Consumidor real | `iconst_0` antes de `setAutomaticRecoveryEnabled`, y dos sobrecargas de `newConnection`. **Ninguna clase** del JAR de procesadores contiene `io/netty`, `useNio` ni `NettyConfiguration` (búsqueda en todos los bytes, no solo en fuentes) |
| Origen | Sin cambios al terminar (156 ficheros, comparación completa de SHA-256) |

### Aplicación real en scratch, sin valor de aprobación

Generé un plan con las 19 ocurrencias de Guava, LZ4 y Snappy, solo para probar el escritor. **No es un plan aprobado.** El resultado se borró.

| Medida | Resultado |
| --- | --- |
| Dry-run y `--apply`, CLI con sus límites | `rc=0`, 15 NAR en el overlay, 54.440 KiB, unos 90 s |
| Dos ejecuciones | **Deterministas**, SHA-256 idénticos |
| Comparación entrada a entrada de 1.017 entradas | Nombres, orden y contenido sin comprimir idénticos. Los 19 objetivos con el hash de reemplazo |
| Diferencia de metadatos | Solo `flag_bits`, que la doc ya declara como bookkeeping |
| Hashes antiguos en el overlay | 0 |
| Parser ZIP de Java | Abre las 15 NAR, lee las 1.017 entradas y 660 JAR anidados en stream |
| Plan de RabbitMQ y de shaded | Rechazados: `known blocked candidate input` |

Esto **no es** un escaneo ni prueba de carga. No demuestra que baje ninguna tupla.

### Cierre independiente del cierre Maven

Ejecuté el **resolver real de Maven 3.9.11**, sin código del proyecto, offline y con repositorio propio:

- RabbitMQ 5.37.0: **exactamente las 13 coordenadas** de `rabbit-closure-lock.json`.
- Guava 33.7.2, LZ4 1.11.4 y Snappy 1.1.10.9: **iguales** a las del verificador.

Es la evidencia más fuerte de que las decisiones actuales son correctas, y por eso M1 no bloquea hoy.

## M1 y M2 del informe anterior: cerrados

### M1, Rabbit desbloqueado por pins falsos

| Ataque | Resultado |
| --- | --- |
| 11 JAR Netty falsos fijados con hash correcto, `verify.py` | RabbitMQ sigue en `blocked-compatibility` |
| 11 JAR Netty falsos, `verify_rabbit.py` | `rc=1`, 19 errores de compilación, **sin** `rabbit-transport-result.json` |
| Quitar el pin del JAR `netty-handler` | `unpinned required JAR` |
| Quitar el POM `netty-parent` | `unpinned POM` |
| Alterar el lock | `required closure changed` |

### M2, POM con fallo abierto

| Caso anterior | Ahora |
| --- | --- |
| Sin `xmlns` u otro namespace | Rechazado |
| Reset de namespace en `dependencies` o en `version` | Rechazado |
| Dependencia en el abuelo | Recorrida. **Igual que Maven real** |
| Perfil `activeByDefault` en el padre | Rechazado |
| Classifier o `type=pom` | Rechazado |
| Padre no fijado o alterado | Rechazado (tests propios, confirmados con mutantes) |

### Correcciones L1 a L5 del informe anterior

Comprobadas también:

- Objetos vacíos: rechazado por hash exacto y por igualdad en ambos sentidos.
- `classes/` y `tmp-*` están dentro de cada `proof-*`.
- Marca de entrada al parser, comprobada en el código del timeout.
- Classfile cortado: **1.244 de 1.244 offsets rechazados con `ValueError`**, y los bytes sobrantes también.
- Las variables de inyección no llegan a los logs y el plan no cambia, salvo lo indicado en L7.
- Las entradas shaded tienen reemplazo `null`. Sus clases están reubicadas (`org/apache/hadoop/thirdparty/...`, `org/apache/iceberg/relocated/...`), como confirma el inventario real.

## Admisión exacta del directorio legacy: correcta

Solo se admite `create_system=3`, `external_attr=0xffff0010`, barra final, STORED y tamaños y CRC a cero.

**Rechazados (sondeado):** FAT y `create_system=19`, `0xffff0000`, `0xffff0011`, modos symlink, bloque y FIFO, sin barra, con contenido, deflated, CRC falsificado, `compress_size` falsificado, `file_size` falsificado, flag de cifrado, traversal, ruta absoluta y colisión con fichero.

**Sobre datos reales:** 141 entradas de esa forma exacta, todas en JAR anidados. El plan real copia esos JAR enteros, así que **no reescribe ninguna**.

**Reescritura, solo con fixture sintético:** un ancestro con la entrada legacy conserva `0xffff0010`, `create_system=3`, STORED y tamaños y CRC a cero, y se vuelve a inventariar sin error (`logs/legacy_rewrite.log`).

La lógica es correcta, pero los tests no la fijan del todo: ver L6.

## Hallazgos

### M1. Medium, código y documentación: `maven_closure.py` da cierres distintos de Maven sin rechazar

**Sondeado** contra el resolver real de Maven 3.9.11. Misma clase que el M2 anterior: lo que no se reconoce debería fallar, y aquí sale otro resultado.

| Caso | Línea | Este código | Maven real | Dirección |
| --- | --- | --- | --- | --- |
| Exclusión `*:*`, `g:*` o la propia dependencia | `maven_closure.py:125,134` | **Elimina la dependencia misma** | La conserva | Fallo abierto |
| `optional` solo en `dependencyManagement` | `maven_closure.py:83` | La excluye | La exige | Fallo abierto |
| Exclusión gestionada + exclusión local | `maven_closure.py:84` | Las une | Solo la local | Fallo abierto |
| El hijo gestiona otra versión de una dependencia heredada | `maven_closure.py:79-85` | `leaf:1` | `leaf:2` | Versión errónea |
| BOM con `${project.version}` o propiedad propia | `maven_closure.py:76` | Evalúa en el consumidor: `leaf:1` | Evalúa en el BOM: `leaf:2` | Versión errónea |
| El hijo gestiona `scope=test` de una dependencia heredada | `maven_closure.py:79-85` | La exige | La excluye | Fallo cerrado |

**Causa de las dos primeras:**

- `visit(target, excluded|exclusions)` comprueba la exclusión sobre el propio objetivo, con el conjunto que incluye sus exclusiones.
- `md|d` copia `optional` desde la gestión, cuando Maven no lo aplica así.

**El test y la doc consolidan el error:**

- `test_rabbit.py:37-40` exige el comportamiento divergente.
- `RABBIT_TRANSPORT.md:28-32` lo describe como correcto.

En los POM reales, Netty declara `<optional>true</optional>` en el propio hijo donde importa, y por eso el resultado coincide.

**Impacto hoy: ninguno.** Las cuatro familias coinciden con Maven real.

**Impacto futuro:**

- El lock (`verify_rabbit.py:75`) solo protege a RabbitMQ.
- Para las demás familias no hay lock, así que un re-pin podría dar `declared_closure_complete` y `component-tested-candidate` de forma errónea (`verify.py:186,208`).
- La forma no es exótica: `amqp-client-5.37.0.pom:503-506` ya usa `io.opentelemetry:*`, aunque en una dependencia de test.

**Corrección:**

1. Rechazar estas formas en vez de modelarlas: exclusiones con comodín, `optional` o exclusiones en gestión, y BOM con interpolación.
2. Corregir `test_rabbit.py:37-40`.
3. **Debe ir antes de cualquier re-pin o familia nueva.** No bloquea los pins congelados de este commit.

### L1. Low, código y evidencia: la verificación posterior solo mira la hoja

`patch_nested_jars.py:340-344` calcula el inventario completo de salida y solo compara el hash de cada objetivo. Ya tiene los datos para exigir que todo lo demás coincida.

**Sondeado con fixtures:**

| Caso | Resultado |
| --- | --- |
| Escritor inyectado que **pierde hermanos** no seleccionados | **Publica** |
| `external_attr=0` | Pasa a `0x1800000` (lo hace `zipfile`) |
| Nombre UTF-8 sin flag EFS (`é`) | Se **renombra** a `├⌐` con EFS |
| JAR ejecutable con preámbulo | **Pierde el preámbulo** |

`NESTED_PATCHING.md:85` promete conservar atributos externos, y no es cierto con valor 0.

**Sobre datos reales** (2.040 ocurrencias): 0 preámbulos, 0 nombres no ASCII y 0 cambios en las NAR del plan real. Hay 223.913 entradas con atributo 0, pero en contenedores que este plan no reescribe.

**Corrección:** comparar el inventario posterior con el esperado, restaurar el atributo tras escribir, y rechazar preámbulo y no ASCII sin EFS.

### L2. Low, código: `BLOCKED_INPUTS` solo mira el preimage de la hoja

`patch_nested_jars.py:301`. **Sondeado**, parcheando el conjunto en memoria para usar hashes de fixture:

| Caso | Resultado |
| --- | --- |
| Hoja dentro de un ancestro bloqueado | **Aplicado** |
| Reemplazo con un hash bloqueado | **Aplicado** |
| Reemplazo que **contiene** la hoja antigua | **Aplicado**, y el hash antiguo sobrevive |
| Reemplazo igual a la entrada | **Aplicado** (no-op) |

Hoy no es alcanzable con los bytes reales: los objetos bloqueados no contienen archivos anidados y los reemplazos previstos tampoco. Exige además un plan erróneo que el revisor apruebe.

**Corrección:** comprobar toda la cadena y el reemplazo, y exigir que los hashes seleccionados desaparezcan del inventario posterior.

### L3. Low, código y evidencia: directorios con modos normales y divergencias entre cabeceras

**Sondeado, admitido en todos los casos:**

- Un `evil.jar/` con contenido, con modo `S_IFDIR`, modo 0 o modo regular. No se recorre (`patch_nested_jars.py:193`).
- Un directorio deflated.
- Directorio central legacy exacto con una cabecera local que oculta un JAR de 136 bytes.

`NIFI_OCCURRENCES_REVIEW_FIXES_20261104.md:44` dice que no se admiten directorios comprimidos o con contenido. Es cierto **solo para la forma legacy**, y la frase se puede leer como general.

**Sobre datos reales**, en las 2.040 ocurrencias: 0 directorios con contenido, 0 diferencias de método entre cabeceras, 0 de tamaño (en entradas sin data descriptor) y 0 huecos de más de 16 bytes entre registros.

**Riesgo bajo:** ningún consumidor conocido carga bytes de un directorio. El exposer usa la misma regla de sufijo.

**Corrección:** rechazar `is_dir()` con tamaño distinto de cero y validar cabecera local frente a directorio central.

### L4. Low, evidencia: el control de «peer malformado» no discrimina

`TransportFixture.java:67-68` acepta cualquier `IOException`, y los logs solo imprimen `invalid peer rejected: IOException`.

**Sondeado con 5.37.0, en bloqueante sin Netty y con Netty 4.2.18:**

| Peer | Excepción visible | Causa real |
| --- | --- | --- |
| Cabecera de versión errónea | `IOException` | `MalformedFrameException`, «protocol version mismatch» |
| Cierre sin escribir | `IOException` | `EOFException` en bloqueante; sin causa adicional en Netty |
| Trama truncada | `IOException` | `EOFException` en bloqueante; sin causa adicional en Netty |
| RST | `IOException` | `SocketException` |

**El comportamiento real es correcto** en las dos combinaciones medidas; el log no lo demuestra. No medí 5.35.0, NIO ni Netty 4.2.17: lo infiero por ser el mismo camino de código.

**Corrección:** exigir `MalformedFrameException` en la cadena de causas.

### L5. Low, evidencia: operaciones reales del consumidor sin ejecutar y sin declarar

Encontré estas referencias en los bytes de las clases reales. El fixture no las ejercita:

| Clase | Operaciones |
| --- | --- |
| `AMQPConsumer` | `basicConsume`, `handleDelivery`, `basicAck`, `basicQos` |
| `AMQPPublisher` | `confirmSelect`, `waitForConfirms`, `addReturnListener`, publicación con esos modos |
| `AbstractAMQPProcessor` | `setSaslConfig(EXTERNAL)` |

El fixture solo hace handshake PLAIN, un canal, una publicación simple y cierre, y lo dice bien. Pero `RABBIT_TRANSPORT.md:97` no menciona entrega entrante ni confirmaciones. **La entrega entrante es donde se decodifican tablas y propiedades.**

Hoy se compensa con la aceptación real de NiFi, que sigue pendiente. Ningún resultado se presenta como esa aceptación.

**Corrección:** añadirlo a la lista de no probado. Mejor aún, ampliar el fixture con `basic.deliver` y confirmación.

### L6. Low, tests: guards correctos que los tests no protegen

Mutantes sobre las dos suites portables, 23 en total:

**Sobreviven:**

- Comprobación de `BLOCKED_INPUTS` (`patch_nested_jars.py:301`).
- Comprobación de solapamiento (`:328`).
- Verificación posterior (`:343`).
- `RENAME_NOREPLACE` (`:348`).
- Cinco condiciones legacy por separado: `create_system`, CRC, `compress_size`, `file_size`, STORED.
- Sustituir el atributo exacto por «cualquier modo `0xffff`».

**Mueren (lo importante de M1 y M2 sí está protegido):**

- RabbitMQ siempre bloqueado.
- Cierre con JAR y POM.
- Namespace, hash, identidad y perfiles del POM.
- Type y classifier.
- Recorrido de padres.
- Classfile truncado.
- Hermanos sin mapear.
- Ancestro firmado.

Mis sondas prueban que el código actual se comporta bien en todos esos casos. Falta que un test lo mantenga.

También: `test_signed_manifest_and_ancestor_overlap` (`tests/test_patch_nested_jars.py:194-200`) no comprueba solapamiento pese a su nombre.

### L7. Low, código: `java -version` sigue viendo las variables de inyección

`verify.py:219` usa `check_output` directo, sin el filtrado ni los límites de `run()`.

**Sondeado:** con esas variables, `toolchain.json` registra `Picked up JAVA_TOOL_OPTIONS…`. Un agente Java se ejecutaría ahí. No afecta al plan (hash igual) ni al resto de logs.

**Corrección:** pasar por el mismo entorno y los mismos límites.

### L8. Low, residual: la raíz del escaneo es más amplia que la del inventario

El exposer recorre `/opt/nifi` (`nifi.Dockerfile:61`). El inventario solo cubre `nifi-current/lib`. El padre lo declara, pero `pending` no incluye cerrar esta diferencia, y `expected_occurrences` solo cuenta sobre `lib`.

**Si un archivo del toolkit anidara uno de los hashes seleccionados, sobreviviría al parche y el gate lo seguiría viendo.**

**Indicios medidos que reducen mucho el riesgo:**

- 1.027 de 1.027 objetos del escaneo anidado están en el inventario de `lib`.
- Ninguna de las cuatro familias aparece suelta en el escaneo normal (70 paquetes en rutas JAR del toolkit y 37 de `nifi-current`).

Esos indicios **no excluyen** que el mismo hash esté también anidado en un archivo del toolkit, porque el exposer deduplica por hash. No pude comprobarlo sin la imagen.

**Corrección:** una sola ejecución de inventario sobre el `/opt/nifi` completo.

### Info

- `verify_rabbit.py:60` escribe `docker_nar_match: False` fijo en cada proof. El padre confirma ahora que coincide. Significa «no comparado aquí», pero se lee como negativo.
- `verify.py:177-186` ignora exclusiones, así que `component-results.json` lista `protobuf-java` y `protobuf-javanano` como requeridos para RabbitMQ. Maven real y `verify_rabbit.py` los excluyen. Es fallo cerrado y RabbitMQ sigue bloqueado aquí, pero las dos pruebas se contradicen.
- `tests/test_patch_nested_jars.py:207` invoca `python` del `PATH`, no `sys.executable`. En esta máquina eso significa que el CLI se prueba con 3.14 aunque la suite corra en 3.11.
- `python -m unittest tests.x` falla con Python 3.14 **por el entorno**: un paquete `tests` ajeno en site-packages. Ejecutados directamente, pasan 15 + 12. No es un defecto.
- La NAR parcheada conserva el nombre `guava-33.7.1-jre.jar` con bytes de 33.7.2. Es consecuencia de reemplazar por ruta exacta. El exposer nombra por hash, así que no debería confundir al escaneo (inferido, no escaneado). Puede confundir a un operador.

## Revisión de las siete configuraciones

| # | Configuración | ¿Se sostiene lo afirmado? |
| --- | --- | --- |
| 1 | 5.35.0, SLF4J 1.7.36, sin Netty | Sí. Control de transporte normal, no discriminador de CVE, y así se presenta |
| 2 | 5.37.0, SLF4J 1.7.36, sin Netty | Sí. `Class.forName` confirma la ausencia y la activación de Netty falla con `io/netty/...` |
| 3 | 5.37.0, SLF4J 2.0.19, sin Netty | Sí. Solo API, proveedor NOP. El `logback` real de `lib/` queda sin probar, y está declarado |
| 4 | 5.37.0 + 4.2.18 declarado | Sí. `NettyFrameHandlerFactory` real y `NioSocketChannel` confirmado por el customizer |
| 5 | 5.37.0 + 4.2.17 de la NAR | Sí. Bytes extraídos de la NAR oficial, igual a la imagen |
| 6 y 7 | Lo mismo con SLF4J 2.0.19 | Sí, con el mismo límite que la 3 |

El fixture **verifica de verdad** la carga publicada y el orden de los métodos AMQP. Un fallo del fixture aflora en `result.get()`.

**Límites de lo afirmado:**

- «Malformed peer»: L4.
- El TLS es de inicialización, sin handshake, y así se declara.
- El `EmbeddedChannel` no es la pipeline privada de RabbitMQ, y así se declara.

**El estado es justo:** `transport-component-tested-nar-mapping-pending` no promete más de lo medido.

## Condiciones previas al ensamblado

No son defectos de este commit, sino lo que falta o hay que cuidar:

1. **Revisión de classloader y consumidor por ocurrencia.** Ya pendiente según el padre. Incluye `nifi-framework-nar` con Guava y el `rawCompress` más estricto de Snappy.
2. **Snappy puede tener un problema nuevo.** El asunto de `c176080` habla de «Snappy Hadoop incompatibility». **No lo revisé.** Confírmalo antes de incluir Snappy en un plan real.
3. **RabbitMQ sigue bloqueado por código** (`BLOCKED_INPUTS`). Es lo correcto hoy. Levantarlo exige un cambio revisado tras la aceptación del consumidor.
4. **El plan se liga al árbol exacto.** `nifi.Dockerfile:36-41` sustituye Jackson en `bootstrap` y en el toolkit. Un plan generado sobre `lib` original falla cerrado si se aplica después de ese paso. Hay que generar y aplicar sobre el mismo árbol.
5. **La salida es un overlay de 15 NAR**, no una distribución. Propietario y modo dependen de quien la copie y del umask. Conviene mantener `--chown`.
6. **Cerrar L8** con un inventario de `/opt/nifi`, antes de esperar que baje una tupla.
7. **Recomendado, de bajo coste, antes del primer plan real:** L1 y L2.

## Límites de esta revisión

- Sin imagen, NiFi, broker, escaneo, classloader real ni entradas hostiles a código nativo.
- La aplicación real es un ejercicio del escritor en scratch. **No demuestra que baje ninguna tupla.**
- Probado solo en OpenJDK 21.0.13, Linux x86_64 y Python 3.11.17. Con 3.14, solo las suites portables.
- La comparación con Maven usa la sesión por defecto del resolver y casos sintéticos elegidos por mí. No es exhaustiva. No ejecuté ningún plugin.
- Maven 3.9.11 se tomó de la caché del padre. Su procedencia está registrada con SHA-512 en `build-tool-provenance.json`, pero no recalculé ese hash.
- Mis sondas Java usaron los límites acordados en ejecución (`-Xmx256m`, 96 MiB de metaspace, una CPU, sin core dumps). Mis `javac` y orquestadores Python solo tenían `-Xmx256m` o nada, y el límite de CPU fue el `timeout` de pared.
- L5 se basa en buscar referencias en bytes de clase, no en ejecutar.
- Sin red durante la revisión.

## Reproducción

**Logs, scripts y fuentes de sondas:** `/home/tears/.cache/claude-nifi-recheck-f4e32bf/keep`.

Borré mis copias de caché y el overlay parcheado para que nadie los use por error. No toqué ninguna caché ni original del padre.

| Tema | Fichero en `keep/` |
| --- | --- |
| Hashes de evidencia | `scripts/binding.py` |
| Estructura ZIP real y objetos | `scripts/realscan.py`, `logs/realscan.json` |
| Planes reales y comparación | `scripts/mkplans.py`, `scripts/cmpapply.py`, `logs/cmpapply.log`, `three-families.json` |
| Admisión, cobertura, publicación | `scripts/probe_patcher.py`, `logs/probe_patcher.log`, `scripts/zero_attr.py` |
| Parser de Java | `jarcheck/JarCheck.java`, `logs/jarcheck.log` |
| Maven real | `mvn/MvnClosure.java`, `logs/mvn-real.log`, `logs/mvn-families.log` |
| Divergencias Maven | `scripts/probe_maven.py`, `logs/probe_maven.log` |
| Peers | `peer/PeerProbe.java`, `peer2/PeerB.java`, `logs/peer-netty.log`, `logs/peer-blocking.log` |
| Raíces y consumidor | `scripts/scanroots.py`, `scripts/consumer.py` |
| Classfile | `scripts/classcut.py` |
| Mutantes | `scripts/mutants.py`, `logs/mutants.log` |

Reproducción mínima de la divergencia más clara, sin red ni JDK:

```bash
cat > /tmp/d14.py <<'EOF'
import hashlib, sys, tempfile
from pathlib import Path
sys.path.insert(0, 'deploy/images/nifi-patches/compatible-libraries')
from maven_closure import Closure
NS = 'http://maven.apache.org/POM/4.0.0'
def pom(a, body=''):
    return (f'<project xmlns="{NS}"><modelVersion>4.0.0</modelVersion><groupId>x</groupId>'
            f'<artifactId>{a}</artifactId><version>1</version>{body}</project>')
root = pom('root', '<dependencies><dependency><groupId>x</groupId><artifactId>mid</artifactId>'
           '<version>1</version><exclusions><exclusion><groupId>*</groupId>'
           '<artifactId>*</artifactId></exclusion></exclusions></dependency></dependencies>')
c = Path(tempfile.mkdtemp()); pins = []
for a, x in (('root', root), ('mid', pom('mid'))):
    (c / f'{a}-1.pom').write_text(x)
    pins += [{'file': f'{a}-1.pom', 'coordinate': f'x:{a}:1', 'sha256': hashlib.sha256(x.encode()).hexdigest()},
             {'file': f'{a}-1.jar', 'coordinate': f'x:{a}:1'}]
print(Closure(c, pins).resolve('x:root:1')['required_coordinates'])
EOF
python3 -B /tmp/d14.py
# Imprime ['x:root:1']. Maven real incluye también x:mid:1.
```

Ejecútalo desde la raíz de una extracción de `f4e32bf`.

## Orden recomendado

1. **Antes de cualquier re-pin o familia nueva:** M1, incluido corregir `test_rabbit.py:37-40`.
2. **Antes del primer plan real:** L8 y las condiciones previas 1 a 5. Recomendado: L1 y L2.
3. **Coste bajo, cuando toque:** L3, L4, L6 y L7, y ajustar la redacción de L5.
