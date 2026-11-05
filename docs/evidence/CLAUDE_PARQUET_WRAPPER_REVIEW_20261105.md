# Revisión independiente: candidato wrapper Parquet 1.18.1 / Jackson 2.22.3

- **Revisor:** sub-agente Claude (Opus 5.5), solo lectura.
- **Commit revisado:** `0dafc5d9d150a813d5676baa0b11c9b459c53667`, inmutable. Revisé `t3-a1e0c4c9`, un checkout aislado en ese commit. Mis pruebas usaron los artefactos del padre desde la caché.
- **Alcance:** `deploy/images/nifi-patches/parquet-jackson/` y `tests/test_nifi_parquet_jackson.py`, en el ensamblado actual.
- **Candidato:** `bad77fac2682d5441ce19e498056ddaf948e89739d933d302b5cf66c868344cf`.
- **Original:** `1914fed4ed18999ce98ad844aa5d0b09f31027be329ffd82d861d6f7c6f097c7`.
- **Última CI real:** `6d67bc2`, con NiFi 59 tuplas únicas (63 registros) y Kibana 2. Nada de este informe la sustituye.
- **Scratch propio:** `/home/tears/.cache/cnc-claude-parquet-review-20261105/`.

## Veredicto

**Sin hallazgos Critical ni High. Sin defectos en los bytes del candidato.** Encontré 3 Medium y 7 Low, todos en tests, evidencia o metadatos. Ninguno impide seguir con el ensamblado acotado y privado.

**Esto no es una aprobación.** No concedo aprobación de runtime ni humana, ni excepciones. En el plan del repositorio siguen `runtime_approved:false` y `replacement:null`.

Tres ideas resumen el resultado:

1. Los bytes son sólidos. Los reproduje sin Java, y el delta equivale al código oficial 2.22.3.
2. La red de tests es mucho más débil que el resultado: **19 de 21 mutaciones sobreviven**. Hoy el resultado es correcto porque lo comprobé por otra vía, no porque los tests lo protejan.
3. Este candidato **por sí solo no cierra ninguna de las 4 tuplas distintas** de la CI, porque hay otros portadores (sección «Límites declarados»).

## Comprobaciones independientes

| Comprobación | Resultado |
|---|---|
| SHA de stock, candidato en `-final2` y candidato del padre | Coinciden con lo declarado |
| 14 `active_source_sha256` de Parquet frente al checkout | Sin deriva |
| `candidate_source`, `inputs` y `support` de la procedencia embebida frente al checkout | Iguales |
| Reensamblado propio con `assemble()` desde los shaded del padre, sin Java (Python 3.14.8) | **SHA idéntico a `bad77fac…`** |
| Shaded 2.22.2 y 2.22.3 de `-final2` frente a los del padre (`cmp`) | Byte-idénticos |
| Baseline | 1121 entradas, 0 discrepancias. Fuera quedan solo los 4 agregados y 2 `pom.*` de parquet-jackson |
| Registros conservados, recorrido ZIP propio sin importar `prepare.py` | **1151 de 1151 idénticos** en bytes locales y atributos centrales, con el orden conservado. `testzip` limpio |
| Entradas seleccionadas | 68 (44 eliminadas y 24 con el mismo nombre); 68 de reemplazo y 1 de procedencia. Coincide con README |
| Delta frente a los JAR oficiales 2.22.3 | Los 4 `pom.*` son byte-idénticos. **63 clases: 0 diferencias en `javap -p -c -s -constants` normalizado** (reubicación; `ldc_w`→`ldc`; se ignoran offsets y destinos de salto). `module-info` no se comparó y es inerte |
| Las 4 clases `code_entry` del plan | Hashes viejo y nuevo correctos en las 4 tuplas |
| Plan de Shade frente a POM del módulo y Apache parent 39 | `minimizeJar=false`, orden de artefactos, 7 reubicaciones, `ServicesResourceTransformer` y Shade 3.6.2 coinciden. El baseline byte-exacto lo confirma |
| Coherencia de versiones | `jackson-bom-2.22.3` fija annotations `2.22` |
| Código de los 4 fixes frente a fuentes oficiales | Presente: bucle sin regex en `NumberInput`; límite de token en `UTF8DataInputJsonParser`; `MAX_CACHED_TYPE_IDS=1000`; `_unresolvedById` y `_pending` en los acumuladores |
| Copias residuales | 0 clases `fdp/v2_22_2`; 0 entradas `com/fasterxml` sin reubicar. Los servicios no cambian |
| Tuplas frente a `nested-archive-scan.json` (`670afc98…`) | 4 de 4. El hash del escaneo coincide con el plan |
| 11 logs del padre | Salida 0, `finished`, flock de 10 s, wall 40 s, sin core, heap 256, meta 96, direct 32, JDK21 |
| Tests y lint en el commit | 19 OK; ruff limpio |
| Stock tras mis pruebas | **215 raíces iguales al lock.** `git status`: 0 líneas en checkout y padre |

### Consumidores reales en la NAR

Este análisis reduce los límites declarados de `linkage.py`:

- La NAR contiene 20 JAR. Busqué las formas `/` y `.` de `shaded…jackson` en todas sus clases. **Solo la referencian `parquet-hadoop` (12 clases) y `parquet-variant` (2 clases)**, además del propio wrapper.
- `parquet-avro`, `iceberg-parquet`, el writer de NiFi y `hadoop-common` no la referencian. Ninguna NAR declara dependencia de esta.
- Resolución propia con herencia e interfaces:

| Origen | Stock | Candidato | Sin resolver |
|---|---|---|---|
| Consumidores de la NAR | 118 ok, 2 heredados de JDK | 118 ok, 2 heredados de JDK | 0 |
| Clases base del propio wrapper | 55335 ok, 131 de JDK | 55350 ok, 131 de JDK | 0 |

- Ningún consumidor referencia campos o métodos de las clases cambiadas.
- **Control anti-falso-cero sobre entradas reales:** con un JAR manipulado sin `ObjectMapper` ni `JsonParser`, `analyze()` da 1977 referencias, incluidas `ParquetMetadata`, `KeyMaterial`, `KeyMetadata`, `HadoopFSKeyMaterialStore`, `LocalWrapKmsClient$LocalKeyWrap` y `VariantJsonParser`. Por tanto, el cero del candidato no es vacío.
- **Multi-release es inerte.** El MANIFEST, igual en stock y candidato, no declara `Multi-Release`, así que esos 8 archivos nunca se despachan. El límite de MR de `linkage.py` pesa menos de lo que parece.

### Diferencial de comportamiento

Las entradas fueron benignas. Compilé contra el stock y ejecuté sobre ambos wrappers, cada uno con su classpath fijado.

| Control | Stock | Candidato |
|---|---|---|
| `toPrettyJSON` de un footer real con 1 bloque | Igual | Igual |
| `ParquetMetadata.fromJSON` del mismo footer | Falla (`InvalidDefinitionException`) | Falla igual; **el fallo ya existe en stock** |
| `VariantJsonParser`, 11 documentos, bytes del valor y metadatos | `805198e1…` | `805198e1…` |
| keytools `KeyMetadata` y `KeyMaterial` (reflexión) | Igual | Igual |
| `looksLikeValidNumber`, 597 871 cadenas | `6feeb22a…` (2426 true) | `6feeb22a…` (2426 true) |
| Referencias adelantadas, lista intercalada y mapa | Mismo orden | Mismo orden |
| **128 referencias en orden inverso: llamadas a `Key.equals`** | **8384** | **128** |
| Array con referencias intercaladas | Falla: `Cannot store to object array` | `2,5,1,1,6,2` |
| Parser rápido de double y BigDecimal/BigInteger de 900 dígitos | Igual, carga 27 clases `fdp.v2_22_2` | Igual, carga 27 clases `fdp.v2_22_3` |
| Solo E/S, sin llamadas JSON | `191b157c…`, 519 bytes | `191b157c…`, 519 bytes |

En `ReviewProbe`, el JSON del footer difiere entre wrappers en una sola línea: el orden de `encodings`. Se repite igual al reejecutar. Con el probe `R2`, los 4 JSON salieron idénticos, así que lo atribuyo al orden de un conjunto de enums según la historia de cada JVM, no a Jackson. Es una inferencia: no confirmé el tipo concreto del conjunto.

## Hallazgos

### Medium

**M1. Los tests no detectan un falso cero en el análisis de enlaces.** `tests/test_nifi_parquet_jackson.py:127-136,157-171`; `linkage.py:62,67-71,75,83,102-107`.

- **Defecto actual.** Solo se prueba el parseo y la detección de una clase eliminada. `analyze()` no recibe consumidores en ningún test, y la CLI no exige un mínimo.
- **Reproducir:** `lim.sh 130 python3 -I mutate.py <checkout> <scratch>`, ambos scripts en el scratch. Los 19 tests pasan con cada mutación de esta tabla:

| Mutante superviviente | Efecto |
|---|---|
| L1 | Ignora referencias a miembros eliminados |
| L2 | Ignora cambios de jerarquía o acceso de clase |
| L3 | Ignora cambios de flags de miembro |
| L4 | Ignora referencias en descriptores |
| L5 | **Omite todos los consumidores** |
| L6 | Nunca calcula miembros eliminados |
| L7 | La CLI no falla aunque haya referencias |

- Además, sin consumidores, `analyze()` analiza 1102 clases y da 0 referencias con el mismo `status`.
- **Impacto actual:** ninguno sobre `bad77fac`, porque mi control real da 1977 referencias y los 6 consumidores están en `linkage.json`. Una regresión futura podría producir un «0 referencias» falso.
- **Acción:** añadir un test de miembro y descriptor, un test de cambio de acceso, un caso de `analyze()` con consumidores, una prueba de la salida de la CLI y `require(len(consumers)==6)`.
- **Clasificación:** no bloquea el ensamblado. Debe resolverse antes de usar `linkage.json` como evidencia de cierre.

**M2. Las poscondiciones de ZIP y el flujo de `main()` no tienen caso negativo.** `prepare.py:126-141,177,193-199`; `probes.py:50`; `bounded.py:20-21`.

- **Defecto actual.** Sobreviven:

| Mutante superviviente | Efecto |
|---|---|
| P1 a P4 | Sin comprobación de conjunto de entradas, contenido, registro crudo ni metadatos centrales |
| P6 y P7 | `main()` ignora la deriva del stock y de las fuentes |
| P8 | `main()` omite el baseline |
| P9 | Oculta metadatos de versión del delta |
| P10 | **Conserva las clases `fdp` viejas** |
| R1 | Sin guarda `NativeCodeLoader` |
| B1 y B2 | Sin límites de core y CPU |

Solo mueren P5 (comentario ZIP) y B3 (código de salida). `main()` no se ejecuta en ningún test. El README (líneas 51-59) describe estas comprobaciones como garantías.

- **Impacto actual:** ninguno en estos bytes, porque mi recorrido ZIP independiente da 1151/1151 y 0 clases viejas. Los guardas existen, pero nadie comprueba que disparen.
- **Acción:** extraer de `main()` una función pura y probarla con la deriva de cada guarda. Añadir fallos inyectados para las poscondiciones, y comprobar los argumentos de `preexec_fn`.
- **Clasificación:** no bloquea el ensamblado.

**M3. El control de `CVE-2026-91777` no ejercita la ruta corregida, aunque existe un discriminador barato.** `JacksonProbe.java.in:31-37`.

- **Límite declarado, pero evitable.** El README indica correctamente que no reproduce el coste cuadrático. Sin embargo, las referencias se resuelven **en orden ascendente**, de modo que el código viejo encuentra cada una al principio de su bucle. La ruta inversa y `MapDeserializer` quedan sin ejercitar.
- **Reproducir:** `rp/src/ReviewProbe.java` en el scratch. Usa 128 referencias en orden inverso con una clave `Key` que cuenta llamadas a `equals`: **8384 en stock y 128 en el candidato**, sin tiempos ni entrada hostil, con la misma identidad y el mismo orden.
- **Impacto:** el recuento «2 discriminantes, 2 parciales» es correcto, pero esta tupla podría pasar a discriminante con una aserción determinista.
- **Acción:** añadir ese contador al probe, más lista y mapa intercalados. Para `CVE-2026-89407` basta añadir el diferencial de `looksLikeValidNumber`, que da resultados iguales en ambos wrappers. Sigue sin demostrar el DoS, y hay que decirlo así.
- **Clasificación:** cobertura, no defecto del candidato. `closure_approved:false` sigue siendo correcto.

### Low

**L1. La estructura ZIP del delta es correcta pero no uniforme.** `prepare.py:120-124`.

- Quedan 6 directorios vacíos `…/fdp/v2_22_2/`, y los 6 directorios `v2_22_3` no tienen entrada propia. `entries()` ignora directorios, y por eso ninguna comprobación lo detecta.
- Las 69 entradas reescritas (68 de reemplazo y la procedencia) van sin comprimir, frente a deflate en stock: el JAR crece 302 047 bytes (12,4 %).
- Llevan `external_attr` `0o100644` frente a `0` en stock, y las 24 entradas con el mismo nombre pasan al final.
- **Impacto:** ninguno en la carga de clases; `testzip` está limpio. La cadena `v2_22_2` puede confundir a quien inspeccione rutas.
- **Acción:** usar `ZIP_DEFLATED` y limpiar directorios, o documentarlo. Cambiar esto cambia el SHA, así que debe agruparse con otros cambios.

**L2. Los metadatos heredados no reflejan el contenido.** `prepare.py:46,185`; `META-INF/DEPENDENCIES`.

- `DEPENDENCIES` sigue diciendo `jackson-core 2.22.2` y `jackson-databind 2.22.2`, mientras `pom.properties` dice 2.22.3.
- `new_component_notices` solo lleva el NOTICE de core (`e6aef1c0…`). El de databind y annotations (`612b14bc…`) es distinto y no aparece, porque Shade conserva el primero. El README (líneas 47-48) dice que se tratan explícitamente.
- El MANIFEST sigue con `Implementation-Vendor: Apache` y `git-SHA-1` originales. La condición de fork solo consta en `cnc-parquet-jackson-fork.json`.
- **Impacto:** no afecta al escáner ni al runtime. El stock tampoco llevaba estos NOTICE, así que no es una regresión. Puede inducir a error en una auditoría.
- **Aprobación pendiente:** decisión humana sobre licencias. No es una conclusión legal mía.

**L3. El guardián de salida se puede eludir con `..`.** `prepare.py:71-77`.

- `Path.absolute()` no normaliza, así que `is_relative_to` compara texto.
- **Reproducir:** `fresh_output(d/'a'/'..'/'repo'/'x',[d/'repo'])` lo **acepta** y crea `repo/x`, en un directorio temporal. La ruta directa se rechaza.
- **Impacto:** solo argumento local de operador, sin exposición remota. Podría escribir dentro del repositorio, la caché o el stock, pese al guardián.
- **Acción:** usar `os.path.abspath` o rechazar `..`, y añadir un test.

**L4. La igualdad de bytes y el origen del mapper no los impone el código.** `probes.py:48-50,56`; `ParquetProbe.java:36-37`.

- `probes.py` no compara los dos `normal.parquet` ni guarda sus hashes, y tampoco comprueba `mapper-source`. El README lo afirma, pero solo consta en `verification-summary.json`, escrito aparte.
- Lo verifiqué: ambos `normal.parquet` tienen hash `191b157c…`, y `mapper-source` apunta al JAR correcto.
- Esa igualdad **no discrimina los CVE**. La ruta de E/S carga 375 clases Jackson, por lo visto en la inicialización estática de `ParquetMetadata`, y no llama directamente a la API JSON (inferido de las fuentes y del log de clases, sin traza de ejecución). Es una prueba de enlace y de no regresión del escritor, tal como se declara.
- La fila 2 no comprueba su etiqueta.

**L5. La lista de consumidores no probados está incompleta.** `README.md:102-103`; `ParquetProbe.java:11`.

- `VariantJsonParser` usa de verdad el parser Jackson, y no figura ni en las sondas ni en los límites.
- El probe usa `List.of()` como bloques, así que no serializa bloques reales.
- El log de clases de `ParquetProbe` tiene **0 clases `fdp`**: la sonda Parquet nunca carga las 37 clases sustituidas. `JacksonProbe` no registra clases.
- **Impacto:** mi diferencial lo cubre una vez y sin diferencias, pero esa evidencia no está en el repositorio.
- **Acción:** añadir estos controles y mencionar Variant.

**L6. El README es impreciso sobre el fixture.** `README.md:93-103`.

- JTS es **stock-igual**: está en la NAR con el mismo hash. El README lo agrupa con MapReduce como requisito externo.
- `hadoop-mapreduce-client-core` **no está en ninguna de las 215 raíces**.
- Sin él, sobre los JAR de la NAR ensamblada, la escritura termina con el mismo `191b157c…`, y la lectura falla con `NoClassDefFoundError` por `FileInputFormat`, igual con el wrapper stock. Por tanto, la causa no es el candidato.
- La frase «lets the real path pass without substitutes» promete demasiado: la mitad de lectura solo existe en el fixture.
- **Límite ya declarado en parte:** el README sí dice que no prueba la NAR.

**L7. La reproducibilidad está demostrada en un solo entorno.** `prepare.py:89-93,113-119`; `pins.json`.

- El ensamblado usa API privadas de `zipfile`: `_encodeFilenameFlags`, `_didModify`, `start_dir` y `__slots__`. La versión de Python no se fija ni se registra en la procedencia.
- Mi reensamblado y el del padre comparten host, caché y Python 3.14.8; no hay otro intérprete disponible. No hay prueba cruzada.
- `inputs` lista 47 ficheros que `prepare.py` verifica por hash, pero solo consume 13. Por ejemplo, `jackson-datatype-jsr310` y `jackson-dataformat-csv` no se usan: «verificado» no significa «usado».

### Informativo

- **Combinación ensamblada.** La NAR `7c27ffae…` contiene `bad77fac…`, con los mismos nombres de entrada en el mismo orden. Cambian 3 JAR: `parquet-jackson`, `hadoop-common` y `snappy-java`. La evidencia del repositorio usa `hadoop-common` stock. Ejecuté `ParquetProbe` una vez con los JAR ensamblados en classpath plano: pasa, con `191b157c…` y 0 clases de códec o nativas. Pertenece a la revisión combinada pendiente.
- **Bit UTF-8 del miembro.** En la NAR ensamblada, `parquet-jackson-1.18.1.jar` pasa de `flag_bits` 2048 a 0. No afecta al contenido y corresponde al reempaquetado de la revisión combinada.
- **Nomenclatura.** El `plan.json` privado dice `approved-exact-occurrence` y `review.json` dice `decision: approved`. El texto los limita a ensamblado reversible y `context-*.json` mantiene `runtime_approved:false`. Son privados y no contradicen el plan del repositorio, pero no deben citarse como aprobación.
- **Mejora en 2.22.3.** Un array con referencias intercaladas falla en 2.22.2 y funciona en 2.22.3.

## Límites declarados: no son defectos

- **Las tuplas.** Los 4 pares CVE/paquete 2.22.2 tienen también portadores simples (`ff167a63…` y `d0da14c1…`) en 5 NAR: `amqp`, `framework`, `kafka-to-s3`, `standard-shared` y `update-attribute`. Su estado es `blocked-atomic-core-databind-review-required`, y están **fuera del ensamblado actual**. El plan los excluye como «plain Jackson objects». La consecuencia, que el README no explica, es que **Parquet elimina como máximo 4 registros, sin reducir las tuplas distintas**. Solo un escaneo real lo confirmará.
- Enlaces directos, sin reflexión ni classloader completo en `linkage.py`.
- AVRO, cifrado real, códecs, grupos de filas grandes, evolución y delegación de NAR sin probar.
- `CVE-2026-89407` solo con marcador estático.
- Ausencia de `NarClassLoader`, servicios, imagen y SMB.
- Sin versión upstream de Parquet con este Jackson: el catálogo capturado termina en 1.18.1.

## Aprobación pendiente

Esto sigue pendiente y no lo concede este informe:

1. Revisión combinada y aprobación atómica de ocurrencia por el padre.
2. Reconstrucción real de imagen y escaneo: la CI no ha visto este candidato.
3. Decisión sobre los portadores simples de Jackson y los no manifestados de AWS y Azure.
4. Ejecución en `NarClassLoader` y aceptación de servicios.
5. Compuerta de recursos CG32 sin cambios.
6. SMB real y aceptación humana, incluida la decisión de licencias de L2.

## Límites de mis pruebas

- **No hice:** red, compilaciones de imagen, pulls, servicios, SMB ni suite completa. No volví a ejecutar `prepare.py` ni Shade: me apoyé en los shaded del padre, y en su comparación con `-final2`.
- **Recursos:** procesos pesados con flock finito de 30 s (reintenté cuando estaba ocupado), wall ≤140 s, 1 CPU y sin core. Java con heap 256 MiB, metaspace 96 y direct 32. El proceso Python no tuvo límite de heap propio. Las lecturas ligeras (`unzip`, `diff`, `sha256sum`, listados de NAR) corrieron sin cerrojo.
- **Evitado:** nada de OOM, entradas hostiles ni código nativo antiguo; ningún `CodecPool` mixto (0 clases de códec o nativas en los logs revisados); ningún borrado real de raíces.
- **Mis probes son classpath plano y JDK21 fijado:** no modelan `NarClassLoader`. Dan evidencia de biblioteca y consumidor, no de runtime.
- **La normalización de `javap`** elimina offsets y destinos de salto, así que no es una prueba completa de bytecode. Se complementa con el baseline exacto de Shade. `module-info` no se comparó.
- **Mutaciones:** son 21 elegidas a mano, no una campaña exhaustiva.
- **Resolución de enlaces:** las ramas que suben a una clase JDK quedan como «heredado de JDK» sin resolver contra el JDK. Son las mismas en stock y candidato.
- **Licencias:** comparé hashes de ficheros; no es un análisis legal.
- **CVE:** no verifiqué explotabilidad ni si 2.22.3 tiene otros hallazgos.
