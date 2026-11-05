# Revisión independiente: candidato wrapper Hazelcast 5.7.0 / Jackson

- **Revisor:** sub-agente Claude (Opus 5.5), solo lectura.
- **Commit revisado:** `2b95e9a56a02c6ba8feefb1765393970ea52f5ce`. Fuente ejecutable probada: `6b8d4fd868765054586173b4795587b05fb9b230`.
- **Árbol leído:** extraído con `git archive`. El worktree recibió cambios ajenos durante la revisión (hadoop-snappy, `patch_nested_jars`, etc.). Ninguno toca este alcance: `git status` da 0 líneas sobre `hazelcast-jackson/`, el test y la evidencia del padre.
- **Artefactos:** stock `241ec66c…dc33`; candidato del padre `3c8e5d80…ae85`; candidato del hijo `73e56b7b…abc0` (histórico).

## Veredicto

**ELEGIBLE para ensamblado BOUNDED de NAR/imagen candidata con el JAR `3c8e5d80…ae85`.**

- **Bloqueos de código o consumidor para ensamblar: 0.** Sin hallazgos Critical ni High.
- Hay 4 hallazgos Medium y 8 Low. Ninguno invalida los bytes del candidato.
- **Esto no es aprobación de runtime, ni de despliegue, ni afirmación de verde, ni aceptación humana.** `runtime_approved=false`, `replacement=null` y `closure_approved=false` siguen siendo correctos.

Bloqueos de **aceptación externa** que este dictamen no cierra:

- Comportamiento real en `NarClassLoader` y arranque embebido de Hazelcast.
- Escaneo fresco de imagen final (37 tuplas Hazelcast, más el resto de NiFi y Kibana).
- Gate CG32 de recursos sin cambios.
- Prueba real de NiFi y SMB.
- CI y revisión protegidas de PR119, y aceptación humana.

## Comprobaciones independientes

Todo es local y offline. Las sondas pesadas se ejecutaron con `flock -w 60`, una CPU, 256 MiB de heap, 96 MiB de metaspace, 32 MiB de direct, 40 s de reloj, 30 s de CPU, sin core y con entorno mínimo. No relancé los 21 comandos Java del padre ni la suite completa.

| Comprobación | Resultado |
|---|---|
| Hashes de stock, candidato y NAR (`b734da18…5e08`) | Coinciden con lo declarado |
| 88 `artifact_sha256` y log de tests del padre | Sin deriva |
| 15 `active_source_sha256` frente a blobs del commit | Sin discrepancias |
| `source-before.json` frente a `source-lock.json` | Iguales, 215 raíces |
| Ocurrencias de Hazelcast en las 215 raíces | Exactamente 1: el NAR declarado. Búsqueda por entradas de primer nivel: `hazelcast*.jar` y `com/hazelcast/core/Hazelcast.class` |
| Cambio de lint `0a45aaa..6b8d4fd` | Exactamente 3 imports y 1 asignación; la palabra de acceso se sigue leyendo |
| Baseline de payloads viejos frente al stock | 223 / 815 / 223 / 907 entradas, **0 discrepancias** (incluye SubTypeValidator con Hikari) |
| Reensamblado propio con `assemble()` desde los shaded del padre, Python 3.14.8 | **SHA idéntico a `3c8e5d80…`** |
| Registros conservados, comparación propia | 9839: 0 diferencias en bytes crudos, 0 en atributos centrales, orden conservado, `testzip=None` |
| MANIFEST y NOTICE agregado | Idénticos al stock |
| `entry-delta.json` | 2165 seleccionadas, 2167 de reemplazo, 9101 conservadas, consistente con los JAR |
| Clases cambiadas, eliminadas o añadidas fuera de core/databind | 0. Jackson jr (73 clases) sin cambios |
| Clases viejas residuales en core/databind | 0. Sin copias sin reubicar |
| Código real frente a los JAR oficiales 2.21.7 / 3.1.7 | Todas las clases presentes; firmas y longitudes de código coinciden en la gran mayoría. Las excepciones tienen el mismo perfil en stock y candidato (por ejemplo `ldc` frente a `ldc_w` tras remapear) |
| `pom.properties` | 2.21.7 / 3.1.7; jr 3.1.2; hazelcast 5.7.0 |
| Tuplas del plan frente a `nested-archive-scan.json` (`670afc98…`) | 37 = 37, sin diferencias en ningún sentido; ninguna es de jr |
| Versión propuesta frente a `FixedVersion` en la misma línea | 37/37 suficiente (solo aritmética de versiones) |

### Resolución de enlaces que cubre los límites de `linkage.py`

Ámbito: todas las clases base del candidato. Scripts `a2.py` y `a7.py`, más `JdkResolve`.

- **Mi primer resolutor era vacuo.** Toda cadena termina en `java/lang/Object`, así que nunca daba "missing". Lo detecté con mutantes y lo corregí; los resultados de abajo son de la versión corregida.
- **Mutantes actuales:**
  - Quitar `JsonParser.currentTokenLocation` y `skipChildren` añade 2 referencias sin resolver y señala a `AbstractJsonGetter`, entre otras clases.
  - Añadir un método abstracto a `JsonParser` añade 10 huecos.
  - El control JDK `nosuchMethod` da UNRESOLVED.
- **Herencia, interfaces y default methods:** de 684 a 685 referencias que caen a tipos externos. La única nueva es `IOContext$EncodingWriter.out` → `java/io/FilterWriter`, y existe.
- **Verificación contra JDK 21:** 2860 correctas y 6 signature-polymorphic. Las 33 UNRESOLVED son `ICache` e `ICacheInternal` contra `javax.cache`, opcional. Las 19 de propietario desconocido son dependencias opcionales (javax.cache, javax.transaction, jline, picocli) y `ObjectIdGenerators$PropertyGenerator` (anotaciones). Todas existen ya en stock.
- **Clases nuevas ausentes:** 0 por referencia de clase (200 en ambos) y 0 solo por descriptor (143 en ambos).
- **Anotaciones:** 66 referencias en ambos, todas presentes en `jackson-annotations-2.21`, que es la versión que fija el BOM 3.1.7.
- **Jerarquía:** 0 huecos abstractos nuevos (20 en ambos), 0 super finales nuevos, 0 cambios clase/interfaz, 0 supertipos perdidos.
- **Accesos desde clases sin cambios:** 0 miembros con acceso reducido, 0 cambios static/instancia, 0 campos nuevos final, 0 overrides de métodos ahora final.
- **Versión de class-file:** sin cambios (52/61 en base, 61/65/67 en MR).
- **Multi-release:** **ni stock ni candidato declaran `Multi-Release`** tras desplegar el manifest. Sus 10 clases versionadas son inertes en `JarFile` normal y el candidato conserva esa misma condición.
- **Reflexión y recursos:**
  - 0 cadenas en clases sin cambios que nombren clases eliminadas.
  - 0 cadenas nuevas de clases Jackson ausentes.
  - Todos los proveedores de `META-INF/services` existen.
- **Serialización:**
  - 0 diferencias en `serialVersionUID` declarados; 0 clases Serializable cambiadas sin SUID.
  - Único cambio de forma: `_acceptArrayTypes` en `BasicPolymorphicTypeValidator` (ambos namespaces).
  - Los únicos campos de tipo Jackson en clases Hazelcast son factorías y `JSON_JR`, sin serialización asociada detectada.
- **Reglas Shade omitidas:** 7 de 8 sin efecto, con 0 coincidencias en cadenas, referencias y descriptores viejos y nuevos.

### Consumidores reales y modelo de classloader

- **Superficie directa fuera de core/databind:** solo 39 clases sobre **J3 core** (30 de jr y 9 de Hazelcast). **0 sobre J2 (core o databind) y 0 sobre J3 databind.**
- **Cadena NAR real, inspección estática de 40 JAR:** `nifi-hazelcast-services-nar` → `-api-nar` → `nifi-standard-services-api-nar`, más `lib/*.jar`. **`JacksonAnnotation` no está en ninguno.** `lib/bootstrap` contiene anotaciones, pero lo asumí fuera del classpath de runtime; no lo verifiqué en un proceso real.
- **`nifi-hazelcast-services-2.12.0.jar`** no referencia `com/hazelcast/shaded` ni Jackson. Usa `IMap`.
- **Diferencial propio `ConsumerProbe`:** compilado una sola vez **contra stock** y ejecutado sobre stock y candidato, sin cambios de bytecode. Cubre `JsonMetadataInitializer` (objeto y `Data`), `JsonSchemaHelper` y round-trip de schema, `JsonGetter`, `JsonDataGetter` con y sin metadata (`String`/`DataInput` NavigableAdapter), y `JsonUtil.mapFrom`/`listFrom`/`beanFrom`/`toJson`. Usa 14 documentos (Unicode, offsets multibyte, profundidad 2000, número de 1200 dígitos, inválidos) y 15 rutas.

| Forma de classpath | Líneas | THROW | Diferencias stock/candidato |
|---|---|---|---|
| Solo wrapper (forma NAR) | 756 | 59 | **0** tras excluir la línea code-source |
| Wrapper + `jackson-annotations-2.21` | 756 | 56 | **0** tras excluir la línea code-source |

Solo con el wrapper, `JsonMapper` de J2 y J3 lanza `NoClassDefFoundError: com/fasterxml/jackson/annotation/JsonSerializeAs` **tanto en stock como en candidato**.

Hashes de salida:

- `old-wrapperonly` `6a572199…`
- `new-wrapperonly` `e0e11a8d…`
- `old-annot` `5bbfa0b2…`
- `new-annot` `de4caacd…`

## Hallazgos

### Medium

**M1. Las sondas no modelan el classloader del NAR.** `probes.py:21,25`.
Todas las sondas añaden `jackson-annotations-2.21.jar`, que el NAR no aporta. `JsonUtil` solo registra `JacksonAnnotationExtension` si esa clase es visible, así que `HazelcastProbe` ejecutó únicamente la rama que el NAR no tomaría. Además, los controles de databind solo pueden ejecutarse con ese JAR añadido.
- **Reproducir:** ejecutar con `-cp clases:<wrapper>` (`new-wrapperonly.txt`, líneas 2-4).
- **Efecto:** las 4 tuplas de sonda de databind (`CVE-2026-91776` y `CVE-2026-59888` en dos namespaces) son evidencia **a nivel de biblioteca**, no de la ruta NAR. No indican que el fix esté probado en runtime. Las sondas `CVE-2026-89425` usan `DataInput`. Ni jr ni Hazelcast tienen referencias directas a ese parser o a firmas Jackson con `DataInput` (0 coincidencias); sus rutas directas usan `String`, `byte[]` e `InputStream`. `JsonUtil.mapFrom(Object)` admite objetos arbitrarios y no analicé ese despacho interno de jr.
- **Acción:** añadir ejecuciones solo-wrapper y dejar escrita esta distinción en la evidencia.
- **Clasificación:** no bloquea el ensamblado, que es justo lo que permite probarlo. Mi diferencial cubre la forma solo-wrapper en una sola ejecución, no en `NarClassLoader`.

**M2. El control de consumidores cubre 1 de 9.** `HazelcastProbe.java:7-16`.
Solo ejercita `JsonUtil`. `HazelcastJsonValue` por `toData`/`toObject` no aparece entre los consumidores directos de Jackson, así que ese control no demuestra compatibilidad Jackson. Quedan fuera:
- `JsonGetter`, `JsonDataGetter`, `AbstractJsonGetter`
- `JsonMetadataInitializer`, `JsonMetadataMutationObserver`, `JsonSchemaHelper`
- `StringNavigableJsonAdapter`, `DataInputNavigableJsonAdapter`

Los offsets de `JsonSchemaHelper:207-214` dependen de internals del parser (`ReaderBasedJsonParser` y `UTF8StreamJsonParser`).
- **Estado:** mi diferencial cubre 7 de esos 8 directamente, con 0 diferencias. `JsonMetadataMutationObserver` solo queda cubierto por la resolución estática.
- **Acción:** incorporar al repositorio un control equivalente; `ConsumerProbe.java` puede servir de base. Ver L8 antes de colocarlo en este directorio.

**M3. Los tests no protegen ninguna puerta crítica.** `tests/test_nifi_hazelcast_jackson.py:78-108`.
**11 de 11 mutantes sobreviven** (12 tests en verde):
- `linkage`: nunca marca referencias; omite todos los consumidores.
- `Shade.java`: sin la regla Hikari.
- `prepare`: sin comprobación raw, sin contenido, sin metadatos centrales, sin puerta de baseline, sin guarda de salida, sin deriva de stock.
- `bounded`: sin límite de CPU.
- Provenance con `runtime_approved=True`.

El caso peor es `analyze()`, sin ningún test: puede devolver un 0 falso. Las puertas siguen activas en la ejecución de producción y verifiqué este artefacto por otra vía, así que el fallo es de regresión futura, no de este JAR.
- **Acción:** añadir fixtures para `analyze` (clase y miembro eliminados, y caso limpio), `stock()`, la guarda de salida, inventario de reglas Shade frente a POM, y provenance en `main`.

**M4. Espera de lock sin límite en el lanzador.** `bounded.py:28`.
`fcntl.flock(lock, LOCK_EX)` no tiene espera finita, y el control requerido sí la exige. El `timeout=40` empieza después de obtener el lock.
- **Reproducción (`scripts/g.py`, LOCK en scratch):** con el lock retenido, `run(['/usr/bin/true'])` seguía bloqueado a los 4 s y terminó solo al liberarlo.
- **Efecto:** un titular colgado detiene `prepare` y `probes` indefinidamente y sin log.
- **Acción:** `LOCK_NB` con plazo finito y error explícito.

### Low

**L1. Reglas Shade incompletas respecto al POM.** `Shade.java:14-22`, `README.md:29-30`.
`source-pom.xml:216-248` define 8 reubicaciones del módulo, y `Shade.java` solo incluye Hikari. Faltan `org.snakeyaml`, `org.jctools`, `io.github.classgraph`, `nonapi.io.github.classgraph`, `org.everit.json.schema`, `org.json` y `org.objenesis`. Con estos pins hay 0 coincidencias, así que no hay efecto en bytes.
El problema es de método: **la baseline solo valida reglas contra los bytes viejos**, por lo que una regla aplicable solo a código nuevo no se detectaría en un re-pin. El README tampoco declara la omisión.
- **Acción:** incluir las 8 reglas, o una puerta estática de 0 coincidencias sobre el payload nuevo.

**L2. La guarda de salida es léxica.** `prepare.py:112-114`.
`.absolute()` no normaliza `..` ni resuelve symlinks.
- **Reproducción en scratch:** tanto `<scratch>/../tree/generated-out` como `<scratch>/link/generated-out` se aceptan y resuelven dentro del árbol del repositorio.
- `probes.py:9` y `linkage.py` no tienen guarda alguna.
- **Acción:** usar `.resolve()` sobre el padre existente y aplicar la misma guarda a los tres.

**L3. Controles restantes del lanzador.** `bounded.py:30,36-37`; `prepare.py:128`; `probes.py:22,26`.
- `capture_output` no acota stdout, y no hay `RLIMIT_AS` ni `RLIMIT_FSIZE`.
- En timeout no queda log.
- `heap_mib` y compañía son literales, no derivados de los argumentos: `/usr/bin/true` registró `heap_mib: 256`. El campo `command` sigue siendo auditable.
- `javac` carece de `-proc:none`. Hoy no tiene efecto: ningún JAR de la caché declara `javax.annotation.processing.Processor`.

**L4. Redacción de la cifra de linkage.** `HAZELCAST_PARENT_20261105.md:31-32`, `README.md:84-85`.
"10,881 unchanged consumer classes" incluye 1886 clases core/databind idénticas en bytes; las externas a core/databind son 8995. Los consumidores directos reales son 39. Las **262 clases cambiadas o nuevas no se comprueban** en `linkage.py`, de modo que este no cubre las referencias hacia adelante.
- **Acción:** corregir la redacción y añadir la resolución hacia adelante y por jerarquía. El 0 de referencias directas sigue sin ser una afirmación de ABI completa; este informe aporta resolución estática, no prueba de runtime.

**L5. Metadatos residuales no declarados.** `README.md:53-55`.
- Siguen nombrando 2.21.2 y 3.1.2: `META-INF/maven/com.hazelcast/hazelcast/pom.xml`, `THIRD-PARTY.txt`, `attribution.txt` y `META-INF/attribution.txt`. No son "metadatos no relacionados".
- Quedan 5 directorios vacíos `…/fdp/v2_21_2/`, y 5 directorios `…/fdp/v2_21_7/` sin entrada propia. Sin efecto de carga.
- La identidad de fork está solo en el JSON de provenance: `Bundle-Version` y el POM siguen en 5.7.0, como se pretende.
- **Acción:** documentar esto y añadir provenance también a nivel de NAR, sobre todo si el nombre interno sigue siendo `hazelcast-5.7.0.jar`.

**L6. Reemplazos sin comprimir.** `prepare.py:87-89`.
`ZipInfo` usa STORED por defecto, con lo que el JAR pasa de 21,38 MB a 30,20 MB (+41 %, 2168 entradas). Medir el efecto en NAR e imagen dentro del gate CG32. No cambiarlo salvo necesidad, porque altera el SHA.

**L7. Mezcla jr 3.1.2 con core 3.1.7 fuera del BOM.** `README.md:52-53`.
`jackson-bom-3.1.7` fija jr en 3.1.7. Conservarlo es deliberado, y hay enlace estático completo y diferencial limpio, pero la evidencia no lo identifica como combinación no publicada por upstream.
- **Acción:** declararlo explícitamente.

**L8. Churn de SHA y vinculación débil.** `prepare.py:119,149`; `probes.py:8-9`; `linkage.py:72`.
- Las fuentes de sondas y linkage forman parte del provenance **dentro del JAR**: cualquier `.py`, `.java` o `.in` en el directorio cambia el SHA tras reconstruir. Así pasó de `73e5…` a `3c8e…` solo por lint.
- `--candidate` y `--original` no se comparan con el `summary` ni con `OLD`.
- `.replace` en `probes.py:19` puede no hacer nada en silencio.
- **Acción:** vincular en el JAR solo las entradas de construcción, y exigir los SHA esperados en sondas y linkage.

### Observación sin severidad

La evidencia registra `nifi_blocking_tuples=59`, mientras que el `nested-archive-scan.json` guardado contiene 63 tuplas únicas (37 de Hazelcast y 26 de otras rutas). Las 37 están confirmadas; no reconcilié el 59 con el 63 porque queda fuera de este alcance. Conviene trazarlo antes de citar el total.

## Veracidad por advisory

- **6 tuplas con sonda vieja/fija** (3 advisories en 2 namespaces). Son no vacuas:

| Control | Viejo | Fijo |
|---|---|---|
| Longitud de error `DataInput` | 4295 / 4308 | 457 / 471 |
| Caché de type-id con 1500 valores distintos | 1500 | 500 |
| Nombre ignorado en record | false | true |

  Es un control acotado, no una reproducción del exploit ni un cierre del advisory. El comentario de 3.1.7 indica además que los ids basados en nombre de clase solo quedan limitados por `MAX_CACHED_TYPE_IDS`.
- **31 tuplas solo con fuente primaria.** Marcador offline (número de PR o issue de las referencias en comentarios del código nuevo y ausente del viejo) en 32 de las 37 tuplas totales. Sin marcador offline:
  - `CVE-2026-68494` en 2 namespaces y `GHSA-mhm7-754m-9p8w`: siguen siendo solo fuente primaria, sin discriminación local.
  - `CVE-2026-89425` en 2 namespaces: cubierta por sonda.
- **`candidate-plan.json`** nombra `73e56b7b…` porque es histórico, y el README lo declara. La evidencia del padre tiene conteos, no tabla por tupla para `3c8e…`. Es aceptable: lo comprobé comparando las 12.007 entradas de ambos JAR, con el mismo orden y `META-INF/cnc-hazelcast-jackson-fork.json` como única diferencia de contenido. Además reconstruí `3c8e…` desde sus shaded.
- **No hay afirmaciones de cierre falsas.** Sí falta precisión en M1, M2, L4 y L5.

## Secuencia recomendada

1. **Congelar `3c8e5d80…` y ensamblar con él**, sin tocar antes las 8 fuentes vinculadas (L8).
2. Mantener la ruta `META-INF/bundled-dependencies/hazelcast-5.7.0.jar`, salvo que se decida otra cosa, y añadir provenance de NAR.
3. Conservar en el NAR todos los demás registros y comparar stock frente a candidato.
4. Pruebas sobre esa NAR:
   - `NarClassLoader` real y code-source.
   - Visibilidad de anotaciones.
   - Rama de `JsonUtil`.
   - `IMap` embebido y consumidores JSON.
   - Controles con el stock.
5. Escaneo fresco y gate CG32 **sin cambiar reglas ni excepciones**.
6. Agrupar M1-M4 y L1-L8 en una sola reconstrucción posterior: al reconstruir cambia el SHA y hay que repetir toda la prueba.

## Límites de esta revisión

- Sin red: el origen oficial de los pins se comprobó por hash y coherencia con POM/fuentes, no contra Maven Central. Las 31 referencias primarias no se consultaron.
- Sin `NarClassLoader` real, sin instancia ni clúster Hazelcast, sin NiFi, sin imagen ni escaneo nuevos. No hice sondas hostiles, de código nativo ni de OOM.
- El análisis estático no ve la reflexión construida dinámicamente, ni ramas de ejecución no probadas. Los métodos abstractos declarados solo en el JDK no se evaluaron como huecos.
- El diferencial es acotado (14 documentos y 15 rutas), no exhaustivo.
- No repetí los 21 comandos Java ni la suite: acepto sus logs tras verificar hashes.
- Las 215 raíces: verifiqué lock contra `source-before.json`, hash del NAR y listado de todas, **no volví a hashear las 215**.
- Consumidores y superficie J2/J3 se refieren a clases base con referencias de clase constantes.

## Reproducción

Scratch: `/tmp/claude-1000/-home-tears--t3-worktrees-B-taldea-integration-complete-project-20261103/ea384658-de30-4278-b006-1b21966e6def/scratchpad`. Puede desaparecer con la sesión.

| Archivo en scratch | SHA-256 (prefijo) | Contenido |
|---|---|---|
| `scripts/cf.py` | `e50fa5b4123eb902` | Lector de class-file |
| `scripts/a7.py` | `c4507c2d8964a286` | Resolutor corregido con mutantes |
| `scripts/a8.py` | `146685f8e5b83f17` | Reensamblado, raw, cadena NAR, marcadores |
| `probe/src/com/hazelcast/query/impl/getters/ConsumerProbe.java` | `e475fe3d251c46fb` | Diferencial de consumidores |
| `probe/src/JdkResolve.java` | `099c6ecc43061060` | Verificación de símbolos JDK |
| `probe/jdkresolve.txt` | `8c15673428a5feaa` | Salida de verificación JDK |

Otros scripts en el mismo directorio: `a1.py`-`a6.py`, `a9.py`, `g.py` (guarda, lock y orden de ZIP), `b.sh` y `j.sh` (lanzadores acotados). Los mutantes de M3 se aplicaron a copias en `mut/`, sin tocar el repositorio.

No se modificó el repositorio, no se hizo commit ni push, y no se usó red, Docker, servicios ni builds de imagen. Tampoco se añadieron excepciones ni supresiones. Stock y candidato conservan su hash al final.
