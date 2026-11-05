# Revisión independiente final: guardas NiFi y candidato Hadoop/Snappy

- **Código revisado:** `b5f158c9f4f00cc529bddf233e3a461e60356d69`, extraído con `git archive`. Código ejecutable probado por el padre: `263c464449ac042544237c402f0c244be8f82c79`.
- **El worktree padre se movió durante la revisión** (`a0126da`, `0a45aaa`, `6b8d4fd`, entre otros). Esos commits **no están revisados** y nada de este informe se refiere a ellos.
- **Fecha:** 2026-11-05. Revisión nueva, independiente y de solo lectura. La anterior se canceló sin informe.
- **Modo:** sin commits, push, PR, Docker, red, servicios ni suite completa. Sin aprobación, excepción ni cambio de gate.

## Veredicto

**Sin hallazgos Critical ni High.** Las correcciones de `263c464` se sostienen frente a los hallazgos previos, con residuos acotados que detallo abajo.

| Objeto | Elegibilidad para ensamblado **candidato acotado** | Aceptación runtime |
| --- | --- | --- |
| 7 Guava + 3 LZ4 | **Elegible.** Sin bloqueo de código | Futura. No concedida aquí |
| Hadoop candidato + los 9 Snappy | **Elegible solo como grupo atómico**, tras cerrar M2. Recomiendo corregir L1 antes de congelar el hash | Futura. No concedida aquí |
| Jackson (ABI, wrappers, SDK) | **No elegible.** Sigue bloqueado | No aplica |

"Elegible" significa que no encontré un motivo técnico para no construir el overlay o la imagen con los que se hará la prueba real. **No es aprobación runtime, de despliegue, SMB, CG32, modelo ni humana.** No exijo aceptación de imagen antes del ensamblado que hace falta para probarla.

**Efecto esperado sobre el gate, sin escanear:** el informe fresco `ci-6d67bc2` da 59 tuplas: Jackson 44, Snappy 3, LZ4 3, Wire 3, Guava reempaquetado 2, RabbitMQ 2, Guava 33.7.1 1, OpenTelemetry 1. Es el mismo conjunto de tuplas que el de `f80`.

- El grupo 7+3 retiraría como mucho 4 tuplas.
- El grupo Hadoop+Snappy retiraría como mucho 3.
- Juntos quedarían 52, así que **el gate seguiría en rojo** aunque ambos funcionen.

## Hallazgos

Clasificación: **código** es un defecto o carencia del repositorio. **Compuerta externa** es lo ya declarado como pendiente, y no es un defecto (ver [más abajo](#compuertas-externas-declaradas)).

### M1. Medium, código, sin efecto hoy: `maven_closure.py` sigue dando cierres distintos de Maven sin rechazar

El M1 anterior está cerrado para sus 30 fixtures. Con 27 fixtures nuevos contra Maven 3.9.11 real: 21 iguales, 2 rechazados (uno por un defecto de mi fixture, N8) y **4 divergentes**.

| Caso | Línea | Este código | Maven real | Dirección |
| --- | --- | --- | --- | --- |
| N1: dependencia con `distributionManagement/relocation` | `compatible-libraries/maven_closure.py:32-137` (no modela la reubicación) | `mid, old, root` | `new, fresh, root` | Fallo abierto: omite lo requerido |
| N1b: igual, sin dependencias propias | Igual | `mid, root` | `new, root` | Fallo abierto |
| N2: la gestión del hijo añade exclusiones a una dependencia heredada | `maven_closure.py:89-90` (solo compara `version` y `scope`) | `leaf, mid, root` | `mid, root` | Superconjunto |
| N4: selector de exclusión con propiedad cambiada por un perfil activo | `maven_closure.py:127-128` (solo vigila selectores requeridos) y `:135` | `b, mid, root` | `a, mid, root` | Artefacto erróneo |

**Impacto hoy: ninguno medido.**

- Los `<relocation>` de los POM fijados (1, 1 y 8 ficheros) son configuración del plugin shade. Ninguno está bajo `distributionManagement`.
- RabbitMQ sigue exacto en 13 coordenadas.
- Los ocho cierres de `jackson-databind` son **iguales** a Maven real. Esto es evidencia nueva: `logs/jackson_maven.log`.

**Corrección:** rechazar `distributionManagement/relocation`, cualquier campo de gestión del hijo que afecte a una dependencia heredada, y exclusiones que usen propiedades de perfil. **Debe ir antes de cualquier re-pin o familia nueva.** No bloquea los pins congelados.

**Reproducción:** `keep/scripts/probe_maven2.py`, resultado en `keep/logs/maven2.log`.

### M2. Medium, carencia de código para el grupo Hadoop+Snappy: no hay vía sancionada ni guarda atómica

- `stock-occurrences/emit_plan.py:17,49` y `map_candidates.py:20`: no existe la familia `hadoop`.
- `map_candidates.py:155` y `emit_plan`: los 9 Snappy quedan `blocked-consumer-incompatibility` para siempre, porque el estado se deriva del Hadoop stock. Comprobado: `emit` rechaza `snappy` incluso con registro de revisión válido.
- `scripts/patch_nested_jars.py:406`: el escritor solo mira la cadena de estado. Por lectura del código, un plan a mano con los 9 Snappy **sin** Hadoop pasaría. Un plan a mano con los 10 pasa, lo ejecuté. Si faltara Hadoop, el fallo en runtime sería la `IllegalArgumentException` de `compress`, no un problema de memoria.

**Corrección mínima:** un grupo hash-bound en el emisor que exija `dad07af6… -> candidato` y los nueve `50485d06… -> 35228628…` juntos, y falle si falta alguno.

**Riesgo de ensamblado relacionado:** los grupos comparten 4 NAR (`nifi-aws`, `nifi-kafka-3-service`, `nifi-kafka-service-aws`, `nifi-standard`). Dos overlays separados no se pueden copiar uno sobre otro: el último restauraría los bytes antiguos de la otra familia. Usa un único plan por imagen candidata. El plan combinado de 20 objetivos funcionó en el ejercicio.

### M3. Medium, tests: las guardas del emisor y el bloqueo de Snappy no están protegidos

Mutantes sobre `tests/test_nifi_stock_occurrences.py`: **7 muertos y 11 supervivientes**. Algunos se enmascaran entre sí (`blocked lib` y `signed selected`).

| Sobreviven | Línea |
| --- | --- |
| Estado bloqueado de Snappy | `map_candidates.py:155` |
| `decision`, `families`, `review_reference` | `emit_plan.py:31-33` |
| Digest del reemplazo | `emit_plan.py:40` |
| Familia completa, `source lock`, fuente completa, recurso retirado | `emit_plan.py`, `map_candidates.py:90,94,111` |

**El código actual se comporta bien.** Sondeado directamente sobre el plan real:

- Registro malo en `decision`, `families`, `reference`, hash o con clave extra: rechazado.
- Sin registro: estado `candidate-pending-parent-QA`.

Falta que un test lo fije, incluida una aserción sobre `candidate-plan.json` comprometido. `emit_plan` es la frontera que produce `approved-exact-occurrence`.

### L1. Low, código introducido por el parche: tras un fallo de `Snappy.compress`, el compresor expone salida obsoleta

- **Ubicación:** `hadoop-snappy/prepare.py:67` y `buffer-protocol.patch`. `clear()` deja `limit=capacidad` justo antes de la llamada y no se restaura si lanza. `README.md:25` promete que no se exponen bytes sin inicializar, pero solo lo cubre para entrada vacía.
- **Reproducción sin nativo**, con un `org.xerial.snappy.Snappy` sintético que falla en la segunda llamada (`logs/fault.log`):

```text
original:  retry returned bytes=0    stale marker=0   bytesWritten=0    finished=true
candidato: retry returned bytes=4810 stale marker=64  bytesWritten=4810 finished=false
```

El reintento devuelve 4810 bytes: el bloque anterior y el resto del buffer directo. También falla `needsInput` (false frente a true).

- **Alcanzabilidad:** baja. Con Snappy corregido, buffers directos y capacidad suficiente, solo lanzaría por un error nativo o de JVM. `CodecPool.returnCompressor` llama a `reset`, que limpia el estado. Afecta a quien capture la excepción y reintente sobre la misma instancia.
- **Corrección:** restaurar `limit(0)` si falla. Son pocas líneas, **pero cambia el SHA del candidato**. Conviene hacerlo antes de ligar evidencia a `599a61b2…`.

### L2. Low, código y evidencia: quedan bytes ocultos que el escritor descarta sin avisar

`validate_layout` (`scripts/patch_nested_jars.py:140`) y `verify_rewrite` (`:332`) no los detectan. Todos se publican y el marcador desaparece (`logs/zipedge.log`):

| Fixture | Resultado |
| --- | --- |
| Bytes tras el EOCD | Publica, marcador 1 -> 0 |
| Bytes tras el fin del deflate, dentro de `compress_size` | Publica, marcador 1 -> 0 |
| Extra solo en la cabecera local | Publica, marcador 1 -> 0 |
| Entrada con descriptor y tamaños locales falsos | Publica |
| Extra Info-ZIP unicode-path que nombra `evil.jar` | Aceptado, y **no se recorre** como archivo |

**Datos reales:** 0 colas tras el EOCD en las 2.099 ocurrencias. 0 diferencias de extra local/central y 0 entradas con descriptor en las 1.017 entradas de las 15 NAR que se reescribirían. El caso del deflate no lo medí sobre datos reales. El docstring dice "Refuse hidden payloads": esa promesa es parcial.

**Corrección:** exigir que el fin del EOCD sea el fin del fichero y que el stream deflate agote `compress_size`.

### L3. Low, tests: ramas nuevas de layout sin proteger

Mutantes del escritor sobre `tests/test_patch_nested_jars.py`: **18 muertos y 20 supervivientes**.

- **Cerrado respecto al L6 previo:** ancestros bloqueados, solapamiento, `RENAME_NOREPLACE`, verificación posterior.
- **Enmascarados por una capa redundante:** retención de seleccionados, hash antiguo superviviente, hoja posterior, hermanos sin mapear, dos checks de payload de directorio.
- **Realmente sin test:** `create_system`, atributo exacto y STORED de la forma legacy; flags, método y nombre locales; hueco, firma y valores del descriptor; hueco final; directorio deflated; comparación de metadatos en `verify_rewrite`; las dos ramas ZIP64.

### L4. Low, código y doc: `prepare.py` no recorre `.war`

`hadoop-snappy/prepare.py:168` usa `.jar/.nar/.zip`, y `README.md:66` afirma "Complete recursive traversal". El inventario tiene 5 WAR y 94 filas por debajo. **Efecto real: ninguno.** El inventario completo no tiene ningún paquete `*/snappy` bajo un WAR y contiene un único `hadoop-common`. Mi escaneo de `Methodref`, que sí entra en los WAR, tampoco encuentra consumidores de `org/xerial/snappy` dentro de ellos.

### L5. Low, código y tests: pin de JDK no impuesto y transformación sin test portable

- `prepare.py:199` registra los hashes del JDK pero no los compara con pins, aunque el resumen diga "pinned". Jackson sí lo impone. Tampoco comprueba el SHA esperado del candidato. Hoy coincide: recompilé y obtuve la misma clase `5429bc50…`.
- Tres mutantes de `prepare.py` sobreviven a los tests portables: las dos ediciones del parche (`clear()` y `limit(0)`) y `.zip`. Los protege la prueba Java, no la suite raíz.

### L6. Low, comportamiento: con pool mezclado cambia el modo de fallo

`CodecPool` reutiliza compresores sin mirar el tamaño de buffer. Con un compresor de 4096 y un stream de 65536, datos incompresibles (`logs/codec2.log`):

- **Candidato:** la escritura funciona. Lee un descompresor de 65536. Un descompresor de 4096 falla con `FAILED_TO_UNCOMPRESS`.
- **Original con Snappy antiguo:** falla al escribir, con `newLimit > capacity`.

Con **configuración uniforme** (84 casos por cada uno de 4096, 65536 y 262144, en JVM separadas): **0 fallos**. Las escrituras en varias llamadas con pool mezclado ya daban `MISMATCH` en el original, así que ese fallo es previo al parche. Hay que declararlo, no bloquea.

### L7. Low, documentación

- `hadoop-snappy/README.md:91` y `NIFI_SECOND_REVIEW_CORRECTIONS_20261104.json:397` mantienen pendiente el export fallido y el CI de disco. `RECOVERY_20261105.json` ya lo cierra.
- `NESTED_PATCHING.md:74-75` dice que no se proporciona generador de planes. `stock-occurrences/emit_plan.py` lo es.

### Información

- **Enlace anticipado:** el constructor del candidato ya referencia `Snappy`. Sin la clase en classpath lanza `NoClassDefFoundError` al construir, cuando el original construía y fallaba después. Probado. Hadoop y Snappy son hermanos en la misma NAR.
- **Memoria y límites:** el compresor usa unos 2,17n de buffer directo frente a 2n. `maxCompressedLength(1840700241)` sigue válido. Por encima de ese límite, 1.1.10.9 está programado para lanzar `SnappyError` (por bytecode, sin ejecutar).
- **`libsnappyjava.so` de Linux x86_64 no cambia** entre 1.1.10.8 y 1.1.10.9. La corrección en esa plataforma está en las guardas Java. Ningún consumidor externo llama a `SnappyNative`, según mi escaneo.
- **Semántica de `approved-exact-occurrence`:** el escritor la exige incluso para producir un overlay de prueba. Quien la use debe citar en `review_reference` que el alcance es solo de ensamblado candidato, para que no se lea como aceptación runtime.
- `test_rabbit.py` exige `RABBIT_CACHE` y no parece formar parte de la suite raíz. No medí sus mutantes. Sí sobreviven en `test_nifi_dependency_guards.py`: selector de perfil, conflicto de versión, versión exacta y tipo de BOM.

## Candidato Hadoop: revisión del parche

**Correcto en los caminos normales.** Esto va más allá de lo que el padre declaró probado:

| Comprobación | Resultado |
| --- | --- |
| Hash del candidato y del original | `599a61b2…` y `dad07af6…`, coinciden |
| Diferencias respecto al original | Solo la clase `SnappyCompressor` y el fichero de procedencia, con `approval: false` |
| Atributos ZIP | 0 diferencias en 2.754 entradas |
| Recompilación independiente | Fuente `900e06e7…`, clase `5429bc50…`, ambas iguales a la procedencia |
| `buffer-protocol.patch` | Aplicado sobre el fuente, da el mismo `900e06e7…` |
| Diff de bytecode | Solo `maxCompressedLength`, `limit(0)` y `clear()` |
| Estado de buffers | Constructor, `reset`, entrada vacía, lecturas parciales y `finished` son coherentes |
| `SnappyCodec` + `CodecPool` reales, jars de la NAR en classpath plano, candidato + 1.1.10.9 | **252 casos, 0 fallos** |
| Control: original + 1.1.10.9 | 72 de 84 fallos, con la guarda de espacio |
| Control: original + 1.1.10.8, candidato + 1.1.10.8 | 0 fallos |
| `SnappyDirectDecompressor` | Pasa, también con offset de destino |

**Otros consumidores de Snappy.** Escaneé los `Methodref` de `org/xerial/snappy` en las 2.099 ocurrencias, WAR incluidos. Hadoop es **el único** que llama a `compress(ByteBuffer, ByteBuffer)` sin usar `maxCompressedLength`. Parquet, `DirectCodecFactory`, Avro y MongoDB la usan.

En ejecución, 30 casos normales pasan con 1.1.10.9: Parquet heap y direct, Avro, `SnappyOutput/InputStream`, framed y `SnappyHadoopCompatibleOutputStream` leído por el `BlockDecompressorStream` real. ZooKeeper y MongoDB quedan solo con análisis estático. Kafka lo cubre la prueba previa del padre.

## Estado de hallazgos previos

**Revisión `f4e32bf`:**

| ID | Estado |
| --- | --- |
| M1 Maven | **Cerrado para los 30 fixtures.** Clase residual en M1 de este informe |
| L1 hermanos, atributos, preámbulo, nombres | **Cerrado.** Residuo en L2 |
| L2 hashes bloqueados y no-op | **Cerrado.** Mutantes muertos |
| L3 directorios y cabeceras | **Cerrado.** Residuo en L2 |
| L4 peer malformado | **Cerrado.** Reproducido: 7 de 7 logs con `MalformedFrameException protocol version mismatch` |
| L5 operaciones sin ejecutar | **Cerrado como declaración.** Sigue sin probar en runtime |
| L6 tests | **Parcial.** Ver L3 |
| L7 `java -version` | **Cerrado** |
| L8 raíz de escaneo | **Cerrado** para la imagen stock: 215 raíces y ninguna familia seleccionada en toolkit |

**Revisión `cd811e3`:**

| ID | Estado |
| --- | --- |
| M1 copias sin manifest | **Declarado, no resuelto.** 4 AWS + 3 Azure quedan `blocked-unassessed`. Ejecuté el detector sobre las 215 raíces: sin más portadores en toolkit. Sigue sin ver copias renombradas |
| M2 raíz no seleccionada y symlinks | **Cerrado.** Mutantes muertos |
| M3 tests | **Mayormente cerrado.** Sobreviven guardas de `main()`: pin JDK21, deriva de avisos, revalidación de caché y enlace de la raíz. El bloqueo ABI sobrevive enmascarado por el atómico |
| L1, L2, L3, L4, L5, L7 | **Cerrados.** Los 9 pares atómicos están `blocked` |
| L6 descarga | **Abierto, Low:** `verify.py:29` sigue sin escritura atómica ni plazo total |
| D1-D5, D7 | No reevaluados, salvo lo citado |
| D6 | **Cerrado** |

## Elegibilidad detallada

### Grupo 7 Guava + 3 LZ4

- **Escritor:** ejercicio del padre confirmado por hash. Lo volví a ejercitar en el plan combinado.
- **Guava 33.7.1 -> 33.7.2:** sin retiradas. Solo cambian 4 clases (`CompactHashMap`, `CompactHashSet`, `MapMakerInternalMap$AbstractSerializationProxy`, `module-info`) y los metadatos. Se ejecutó 1 de 93 archivos consumidores (Jimfs). La deserialización de esas clases no se ejercita.
- **LZ4 1.11.2 -> 1.11.4:** sin retiradas de API, con nativos cambiados. El único archivo consumidor, `kafka-clients`, pasa un roundtrip normal.
- **Mapeo:** `map_candidates.py` reproducido, **byte a byte igual** al `candidate-plan.json` comprometido (`3532233a…`).

**Falta para ensamblar, sin ser defecto:**

1. Un registro hash-bound con alcance explícito de candidato. Es una decisión del padre, no de este informe.
2. El cableado: `nifi.Dockerfile` no consume ningún overlay. Debe copiarse con `--chown=1000:1000` en `runtime`, antes de `archive-audit` (`:58`), para que el exposer y el escaneo vean los bytes nuevos.
3. Decidir cómo llega el overlay a CI, porque hoy vive en una caché local.

### Grupo Hadoop + 9 Snappy

- Ejercicio solo de prueba, plan de 10 objetivos en 9 NAR: **aplicado** con los límites del CLI. El parser de Java abre las 9 NAR, 643 entradas y 380 JAR anidados.
- Plan combinado de 20 objetivos en 15 NAR: **aplicado**. Todos los objetivos con su hash de reemplazo. 0 derivas de metadatos en 1.017 entradas. JAR y WAR hermanos con hash igual. El parser de Java abre 15 NAR, 1.017 entradas y 660 JAR anidados.
- Hadoop y Snappy son hermanos en `nifi-iceberg-parquet-writer-nar`.

**Condiciones:** cerrar M2 o usar un plan único de los 10 objetivos revisado a mano. Recomiendo corregir L1 antes, para no repetir la evidencia con otro SHA.

Borré ambos overlays. Eran ejercicios privados, **no aprobaciones**. Los planes `review-exercise-only-plan-*.json` conservan el literal de estado solo para reproducir, y sus salidas ya no existen.

### Jackson

Sigue no elegible: 9 unidades atómicas `blocked`, 6 entradas de wrapper `blocked-wrapper-specific-rebuild-required` y 7 copias de SDK sin evaluar. Sin cambios.

## Compuertas externas declaradas

No son defectos ni requisitos previos al ensamblado candidato:

- Classloader NAR, delegación padre/hijo y procesadores NiFi reales.
- Extracción nativa en la imagen final (Wolfi, Java 21).
- Reconstrucción de la imagen y los dos escaneos. Kibana sigue con 2 tuplas.
- Wrappers Hazelcast y Parquet, y SDK AWS/Azure.
- Protected checks, revisión GitHub, CG32, SMB, modelo y aceptación humana.

## Límites y desviaciones

**Desviación que debes conocer.** Mi primera versión de `CodecProbe` ejecutó el control **original + Snappy 1.1.10.8** con el pool mezclado. Con entrada aleatoria normal, el nativo antiguo devolvió 4100 y 4101 bytes sobre un buffer directo de 4096, es decir, **escribió fuera del buffer unos pocos bytes** antes de que saltara `newLimit > capacity`. No fue entrada hostil ni hubo crash o `hs_err`, y ocurrió en una JVM aislada con 256 MiB y sin core dumps. Aun así, no fue lo que pretendía bajo la restricción de sondas sobre nativos antiguos. No lo repetí: la segunda versión no ejecuta ese caso.

**Otros límites:**

- Sin NiFi, classloader real, imagen, escaneo nuevo, red ni servicios.
- El classpath de `SnappyCodec` es plano y sale de dos NAR. **No equivale al classloader NAR.** Probado en Linux x86_64 y OpenJDK 21 local, no en Wolfi.
- Los 30 fixtures Maven previos no los reejecuté: leí el log del padre y comprobé el código y los mutantes. Mis fixtures nuevos no son exhaustivos.
- `CodecPool`: mezclé tamaños, pero no concurrencia.
- El fallo de L1 usa un stub sintético. No demuestra que el nativo real lance en uso normal.
- No ejecuté la suite raíz. Focalizadas: 85 tests y 39 subtests pasan en Python 3.11 sobre `b5f158c`. Las suites de escritor y Hadoop también pasan en Python 3.14.
- Los recuentos de tuplas retiradas son predicción, no escaneo.
- **Límites de proceso:** sondas Java y compilaciones con una CPU, `-Xmx` de 256 MiB o menos, límite de pared, sin core dumps y bajo `candidate-heavy.lock`. Los orquestadores Python no siempre tuvieron límite de memoria. `realzip.py` usó 1 GiB de espacio de direcciones, y mapeo y escritor 512 MiB.
- **Borrado denegado:** el control de seguridad bloqueó un `rm -rf *` que escribí para mi propio directorio. No se ejecutó nada, y usé un directorio nuevo. Solo borré mis dos overlays, con ruta explícita.

## Reproducción

**Código fuente de la revisión:** `/home/tears/.cache/claude-nifi-final-recheck-b5f158c/src` (`git archive b5f158c`). Scripts y logs: `/home/tears/.cache/claude-nifi-final-recheck-b5f158c/keep/{scripts,logs}`. Sondas Java: `/home/tears/.cache/claude-nifi-final-recheck-b5f158c/hb/{probes,stubsrc}`.

| Tema | Script | Log |
| --- | --- | --- |
| Hashes de evidencia y tuplas | `binding.py`, `tuples.py` | `binding.log`, `tuples.log` |
| Consumidores Snappy y colas ZIP | `realzip.py` | `realzip.json` |
| Fallo de L1 | `hb/probes/FaultProbe.java` | `fault.log` |
| `SnappyCodec` y hermanos | `hb/probes/CodecProbe2.java` | `codec2.log`, `codec.log` (primera versión) |
| ZIP | `zipedge.py` | `zipedge.log` |
| Overlays de ejercicio | `mkplan.py`, `checkov.py` | `jarcheck.log`, `all20.log` |
| Mutantes | `mutants.py`, `mutants_mv.py`, `mutants_stock.py` | `mutants.log` (las filas Maven de este log no valen: baseline erróneo), `mutants_mv.log`, `mutants_stock.log` |
| Maven | `probe_maven2.py`, `jackson_maven.py` | `maven2.log`, `jackson_maven.log` |
| Emisor y RabbitMQ | `emit_neg.py` | `emit_neg.log`, `rabbit.log` |

**Comando base de las sondas Java:**

```bash
flock -w 300 /home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock \
  env -i PATH=/usr/lib/jvm/java-21-openjdk/bin:/usr/bin:/bin LANG=C.UTF-8 \
  timeout 60 taskset -c 7 prlimit --core=0 --cpu=40 \
  java -Xmx256m -XX:MaxMetaspaceSize=96m -XX:ActiveProcessorCount=1 -XX:-CreateCoredumpOnCrash ...
```

## Orden recomendado

1. **Antes de ensamblar Hadoop+Snappy:** M2. Recomendado: L1, por el cambio de SHA.
2. **Para ensamblar cualquiera de los dos:** un único plan por imagen, registro con alcance de candidato, y `COPY` antes de `archive-audit`.
3. **Pronto, de coste bajo:** M3 y L3.
4. **Antes de cualquier re-pin o familia nueva:** M1.
5. **Cuando toque:** L2, L4, L5, L6, L7 y el L6 de Jackson.
