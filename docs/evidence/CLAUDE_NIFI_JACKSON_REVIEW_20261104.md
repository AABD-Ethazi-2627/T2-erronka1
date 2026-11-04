# Revisión independiente: candidato NiFi Jackson (PR119)

- **Fuente revisada:** `cd811e35975a1823bc0003ca09738b4206e0e219`, extraída con `git archive`. La base es `6d67bc2ec72d931486174b906654bcc089250cba`.
- **HEAD se movió durante la revisión:** pasó a `8becc80` por otros agentes. Nada de lo que hay aquí se refiere a ese commit.
- **Fecha:** 2026-11-04.
- **Alcance:** los 16 ficheros nuevos del inventario, `docs/memoria/RECONCILIACION_20261103.md` y la entrada `pr119_nifi_jackson_parent` de `docs/memoria/manifest.json`.
- **Modo:** solo lectura. Sin red, Docker, servicios ni suites completas. Las sondas y reproducciones están en el scratch de esta sesión:
  `/tmp/claude-1000/-home-tears--t3-worktrees-B-taldea-integration-complete-project-20261103/5a6dea8b-caf3-4b3c-94b0-66984215699c/scratchpad/rv/`

## Veredicto

**Elegible como PREPARACIÓN DE COMPONENTE. No acredita runtime, imagen, gate, cierre ni excepción.**

- No hay hallazgos Critical ni High.
- Las decisiones del plan son correctas con los bytes fijados. El plan no aprueba nada para runtime (`candidate-plan.json:1834`, `runtime_approved: false`).
- Hay **tres hallazgos Medium**. Ninguno cambia una decisión del plan actual:
  - M1 es un punto ciego de alcance no declarado.
  - M2 es un fallo abierto del verificador.
  - M3 es una falta de protección frente a regresiones.
- Conviene corregir M2 y M3 antes de usar este verificador como base de un escritor de runtime. M1 debe declararse en la evidencia y en el plan de trabajo.

## Elegibilidad frente a montaje de runtime

Son dos preguntas distintas y aquí se separan.

| Objeto | Ocurrencias en `lib` | Preparación de componente | Montaje de runtime |
| --- | --- | --- | --- |
| Hazelcast 5.7.0 (`241ec66c…`) | 1 | Bloqueado correctamente, reemplazo nulo | Bloquea: rebuild específico del wrapper |
| Parquet Jackson 1.18.1 (`1914fed4…`) | 1 | Bloqueado correctamente, reemplazo nulo | Bloquea: rebuild específico del wrapper |
| Core 2.22.2 (`ff167a63…`) | 6 | Propuesto 2.22.3, bloqueado por ABI | Bloquea: ABI y consumidores en 5 NAR/WAR. El bootstrap ya lo sustituye la imagen |
| Databind 2.22.2 (`d0da14c1…`) | 6 | Propuesto 2.22.3 | Bloquea: consumidores en 5 NAR/WAR. El bootstrap ya lo sustituye la imagen |
| Core 3.2.2 (`93d9090b…`) | 3 | Propuesto 3.2.3 | Bloquea: consumidores y delegación |
| Databind 3.2.2 (`d27509f9…`) | 3 | Propuesto 3.2.3, bloqueado por ABI | Bloquea: ABI y consumidores |

**Efecto real sobre el gate anidado.** De las 59 tuplas, 44 son de Jackson y 15 de otras familias. Aplicar los cuatro JAR planos solo retiraría **3 de las 44**, todas de 3.2.2:

- Quedan 41 tuplas de Jackson: 37 solo en Hazelcast (2.21.2 y 3.1.2) y 4 de 2.22.2, que Parquet sigue aportando con la misma tupla.
- Este recuento sale del escaneo anidado fijado en `input-lock.json`, no de un escaneo nuevo.
- Los rebuilds de los wrappers son, por tanto, el trabajo que más mueve el gate.

Fuera de este candidato y siguen pendientes: Kibana (2 hallazgos), un informe anidado nuevo, CI fresco, CG32, SMB, revisión humana y GitHub.

## Hallazgos Medium

### M1. Medium, alcance no declarado: copias reubicadas de Jackson invisibles para el plan, el inventario de extensiones y el gate

- **Ubicación:**
  - `deploy/images/nifi-patches/jackson/verify.py:137-139` deriva el universo de las filas del escaneo.
  - `verify.py:191-192` filtra por rutas de metadatos Maven.
  - `README.md:36-38` y `README.md:112-113`, junto con `docs/evidence/NIFI_JACKSON_PARENT_20261104.md:13-16`, solo nombran Hazelcast y Parquet como wrappers.
- **Hecho:** un escaneo de constant pool sobre los 156 ficheros encuentra dos portadores más de `jackson-core` reubicado. Ninguno está en el plan, en `extension-inventory.json` ni en las filas del escaneo.

| Objeto | Ocurrencias | Paquete reubicado | Metadatos Maven de Jackson | Parser DataInput |
| --- | --- | --- | --- | --- |
| `third-party-jackson-core-2.54.14.jar` (`764ea60a…`) | 4: `nifi-aws`, `nifi-aws-service-api`, `nifi-iceberg-aws`, `nifi-kafka-service-aws` | `software/amazon/awssdk/thirdparty/jackson/core` | Ninguno (`maven: []`) | Sí |
| `azure-json-1.5.1.jar` (`bad21d5e…`) | 3: `nifi-azure`, `nifi-azure-services-api`, `nifi-iceberg-azure` | `com/azure/json/implementation/jackson/core` | Solo `com.azure:azure-json` | No (77 clases) |

**Sonda acotada sobre los bytes reales del JAR de AWS** (JDK 21, una CPU, 256 MiB de heap, sin core):

```text
version=2.21.4 dataErrorLength=4295 streamErrorLength=468
```

Es el mismo patrón del control antiguo del propio candidato (2.21.2 y 2.22.2: 4295/468). La versión 2.21.4 está dentro del rango vulnerable publicado para CVE-2026-89425 y CVE-2026-89407 (`<= 2.21.6`). Además, `NumberInput` conserva los campos `PATTERN_FLOAT` que la corrección retira.

**Límites de esta afirmación:**

- No afirmo que estas rutas sean alcanzables por NiFi ni por el SDK de AWS. Solo probé el camino CVE-2026-89425 de forma aislada.
- En `azure-json` no determiné la versión, porque no tiene `PackageVersion`, y no probé nada.
- El control positivo es que el mismo escaneo detecta los cuatro objetos planos, Hazelcast y Parquet. Solo busca marcadores por nombre de clase (`JsonFactory`, `JsonParser` y `UTF8DataInputJsonParser` en cualquier ruta; `ObjectMapper` y `TypeDeserializerBase` bajo rutas `jackson/databind`), de modo que una copia renombrada de otra forma pasaría inadvertida. Esto **no** demuestra que no existan más copias.

**Consecuencia:** aunque el gate de 59 tuplas llegue a cero, estas copias siguen sin clasificar. Leer "Jackson = cuatro JAR y dos wrappers" sería una afirmación de cierre que nadie ha demostrado. El candidato no la hace de forma explícita, pero tampoco declara el límite.

**Corrección recomendada:**

1. Derivar los portadores de `class_packages` del inventario ya fijado (por ejemplo, `*/jackson/core`).
2. Exigir que cada portador acabe en el plan o en una lista explícita de "no cubierto por el escáner".
3. Citar ambos objetos en `README.md` y en la evidencia.
4. Decidir por separado qué se hace con el SDK de AWS y con Azure.

### M2. Medium, fallo abierto del verificador: la mayoría de los 156 ficheros no se comparan con la adquisición

- **Ubicación:** `verify.py:119-120` y `verify.py:142-153`. La afirmación derivada está en `docs/evidence/NIFI_JACKSON_PARENT_20261104.md:33-34`.
- **Causa:** el verificador solo exige que haya 156 ficheros y que no cambien durante la ejecución. Únicamente compara con `outer_sha256` los archivos de las ocurrencias seleccionadas, de consumidor y de módulo: **22 de 156**. `p.is_file()` sigue enlaces simbólicos, así que los otros 134 pueden ser enlaces.

**Reproducción** con `--source` en un árbol de scratch:

- 22 copias reales de los ficheros seleccionados.
- `nifi-airtable-nar-2.12.0.nar` sustituido por el texto `NOT THE ACQUIRED ARCHIVE`.
- Los otros 133 ficheros como enlaces simbólicos.

**Resultado:**

```text
drift-rc=0
status=component-prepared, source_archives=156
candidate-plan.json sha256 = 825c4d7b… (idéntico al comprometido)
```

**Lo que sí es cierto en esta ejecución.** Comprobé aparte que los 156 ficheros de `proof-final/source-before.json` y del snapshot actual coinciden con `outer_sha256` del inventario (156 de 156), sin enlaces simbólicos. La afirmación de la evidencia es correcta, pero `verify.py` no la produce ni la impone. Una reejecución con una fuente alterada también emitiría `component-prepared`.

**Corrección recomendada:** exigir `source_before == {outer: outer_sha256}` para todo el inventario, rechazar enlaces y registrar el resultado en `summary.json`. Son unas pocas líneas.

### M3. Medium, calidad de tests: 14 de 15 mutantes de guardas sobreviven a los 12 tests

Ejecuté `test_nifi_jackson_candidate.py` contra copias mutadas de `verify.py`.

| Mutación | Resultado |
| --- | --- |
| Baseline sin mutar (12 tests) | Pasa, como debe |
| `pure=True` en la clasificación del wrapper | **Detectada** |
| Quitar el control de miembro ZIP ambiguo | Sobrevive |
| Quitar `source escape` | Sobrevive |
| Quitar el enlace `chain[0]==outer_sha256` | Sobrevive |
| Leer el archivo exterior sin hash | Sobrevive |
| Quitar el hash final de la ocurrencia | Sobrevive |
| Descarga sin comprobar el hash | Sobrevive |
| Descarga con `wb` en lugar de `xb` | Sobrevive |
| Quitar la limpieza del entorno | Sobrevive |
| Quitar `preexec_fn=limits` | Sobrevive |
| Quitar `scan_set==grouped` | Sobrevive |
| **Quitar el bloqueo por ABI** | Sobrevive |
| Quitar el recuento de 156 | Sobrevive |
| Quitar la comparación de fuente antes/después | Sobrevive |
| **`runtime_approved` a `True`** | Sobrevive |

Puntos concretos:

- `test_archive_chain_integrity_and_ambiguity` (`tests/test_nifi_jackson_candidate.py:71-81`) no incluye ningún caso de ambigüedad, pese a su nombre.
- `test_oversized_download_never_publishes_cache_entry` cubre el tamaño, pero no un hash incorrecto.
- Los recuentos anunciados son exactos: 12 tests, 24 con las guardas de dependencias. El problema es lo que protegen.

**La implementación actual sí se comporta bien.** Llamando directamente a las funciones:

- `extract` rechaza miembro duplicado, exterior incorrecto, ruta con escape y ruta absoluta.
- `fetch_checked` rechaza un hash incorrecto sin crear el fichero y no sobrescribe un destino existente.

Es decir, las guardas funcionan hoy, pero nada impide que se rompan mañana.

**Corrección recomendada:**

1. Añadir casos directos para `extract` y `fetch_checked`.
2. Extraer de `main()` una función pura para el bloqueo por ABI y para la igualdad escaneo/agrupación.
3. Añadir aserciones sobre el `candidate-plan.json` comprometido: `runtime_approved` falso, estados coherentes con `symbolic_abi_changes` y wrappers con reemplazo nulo.

## Cambios de ABI simbólico: comprobación real

**Conclusión:** en los 156 ficheros de `lib` no hay ninguna referencia estática externa a los símbolos retirados. **Mantener el bloqueo sigue siendo correcto**, porque este resultado no cubre todo el runtime ni el uso reflexivo.

### Qué se retira de verdad

Diff propio, más amplio que `helper.compare`, sobre los JAR fijados:

| Par | Público o protegido | No público |
| --- | --- | --- |
| Core 2.22.2→2.22.3 | 4 clases `fdp/v2_22_2/*Parser` | 44 entradas en total bajo el paquete con versión (40 no públicas o MR), recreadas como `v2_22_3`; campos privados `PATTERN_FLOAT` y `PATTERN_FLOAT_TRAILING_DOT` |
| Databind 2.22.2→2.22.3 | Ninguno | Campos privados `_accumulator` |
| Core 3.2.2→3.2.3 | Ninguno | Ninguno |
| Databind 3.2.2→3.2.3 | `StdDateFormat.DATE_FORMAT_RFC1123` | `_accumulator`, `ArrayReferring.<init>` y `resolveForwardReference` |
| Databind 3.1.2→3.1.7 (investigación) | El mismo campo más `UnwrappedPropertyHandler._hasUnwrappedAnySetter` | Varias clases internas |

En los ocho pares no hay métodos abstractos añadidos, nuevos métodos de interfaz sin implementación, `final` añadido, acceso reducido, cambios de `static` ni cambios de jerarquía. Esto cubre una carencia de `helper.compare`, que solo mira retiradas.

`DATE_FORMAT_RFC1123` **no** es una constante inlineable. Es un `protected static final DateFormat` (`0x1c`), sustituido por `StdDateFormat$RFC1123Holder`. Un consumidor que lo use falla de verdad. Lo comprobé con una clase sintética:

```text
class X extends StdDateFormat { f() { return DATE_FORMAT_RFC1123; } }
3.2.2: java.text.SimpleDateFormat@…
3.2.3: NoSuchFieldError: Class X does not have member field …
```

### Escaneo de consumidores

Cubre 264 738 clases y 1168 objetos únicos, el mismo conjunto de hashes que el inventario, sin errores.

| Comprobación | Resultado | Control positivo |
| --- | --- | --- |
| Referencias a `…/fdp/…` fuera del paquete `fdp` | Solo `BigDecimalParser`, `BigIntegerParser` y `NumberInput` dentro de cada copia de Jackson (plana o reubicada) | Esas mismas clases |
| Campo `DATE_FORMAT_RFC1123` | Solo `StdDateFormat` dentro de cada copia | Esos hits y la clase sintética `X`, detectada con propietario `X` |
| Campo `_hasUnwrappedAnySetter` | Solo la copia reubicada dentro de Hazelcast | Ese hit |
| Subclases directas de `StdDateFormat` y `UnwrappedPropertyHandler` | Ninguna | La clase sintética `X` |
| Referencias reflexivas en UTF-8 (`internal.shaded.fdp`, `DATE_FORMAT_RFC1123`) | Ninguna fuera de esas copias | Ninguno específico para el texto reflexivo |
| Clases ajenas en los paquetes de core o databind (paquete dividido) | Ninguna | Ninguno |

**Resolución completa antiguo frente a corregido.** Para cada clase de los 156 ficheros ajena a los objetos del plan, resolví las referencias a core y databind contra el modelo antiguo y el corregido, de 2.22 y 3.2:

- 56 472 entradas de constant pool: 28 761 métodos, 24 017 clases, 3 618 campos y 76 métodos cuya jerarquía sale al JDK, sin cambio entre versiones.
- **Cero transiciones de resuelto a no resuelto.**
- Los controles sintéticos con `JavaDoubleParser`, `DATE_FORMAT_RFC1123` y `resolveForwardReference` producen esa transición.

### Límites

- Solo cubre `nifi-current/lib`. Quedan fuera toolkit, `extensions`, procesadores Python, NAR personalizados y el resto de la imagen.
- No cubre reflexión con nombres construidos en tiempo de ejecución, recursos no `.class`, ni servicios.
- Es resolución estática, no enlace por classloader ni ejecución. No prueba la herencia NAR/WAR.
- Para levantar el bloqueo hay que incorporar este escaneo al verificador, con sus controles, y extenderlo a todo el runtime.

### Consumidores de Jackson 3 sin ejecutar

Esto no es un defecto, porque está declarado como pendiente, pero sirve para planificar:

| Contexto 3.2 | Consumidores directos |
| --- | --- |
| `nifi-jolt-nar` | `json-community-utils` (ejecutado), `nifi-jolt-processors` |
| WAR de Jolt | `json-community-utils` (ejecutado), `json-path-3.0.0` |
| `nifi-standard-nar` | `json-base-3.0.0`, `json-path-3.0.0` |

- Spring 7, Spring Security, Spring Data y Vault también referencian `tools/jackson` en otros NAR sin Jackson 3 directo.
- Los tres contextos 3.2 no tienen `jackson-annotations` como hermano directo. `nifi-jolt-nar` y `nifi-standard-nar` declaran `nifi-standard-shared-nar` como dependencia, y ese NAR sí trae `jackson-annotations-2.22`. El classpath plano de la sonda no reproduce esa delegación.

## Hallazgos Low: código y robustez

| ID | Ubicación | Hallazgo y reproducción | Corrección |
| --- | --- | --- | --- |
| L1 | `verify.py:40-42`, test en `tests/test_nifi_jackson_candidate.py:30-32` | `validate_pins` acepta `artifactId=../../outside`. Reproducido: pin aceptado, destino `/cache/../../outside-1.jar`. El test solo cubre `file` manipulado. Exige editar `pins.json`, que pasa por revisión. `compatible-libraries/verify.py:144` sí exige `f.parent==c` | Validar `g`, `a` y `v` con lista blanca y comprobar `f.parent==cache` |
| L2 | `verify.py:180-184` | Para ocurrencias de nivel superior (`members==[]`), los "hermanos" se buscan dentro del propio JAR. Reproducido: 2 de 12 contextos, `bootstrap/jackson-{core,databind}`, salen con 0 hermanos, aunque `bootstrap/` tiene 18 ficheros más, entre ellos `nifi-flow-encryptor`, que usa Jackson. La imagen ya sustituye estos JAR. El estado sigue diciendo "no verificado" | Tratar el directorio del fichero exterior como contexto |
| L3 | `verify.py:83`, `README.md:86` | La limpieza del entorno es una lista negra. Se conservan `LD_AUDIT`, `LD_BIND_NOW`, `GLIBC_TUNABLES`, `MALLOC_ARENA_MAX` y `JDK_AOT_VM_OPTIONS`. `LD_AUDIT` es efectivo: `ld.so` intenta cargarlo con `java -version`. No probé el efecto de las demás. Exige controlar el entorno del operador | Usar lista blanca: `PATH`, `LANG` y `TMPDIR` |
| L4 | `verify.py:115-118`, `verification-summary.json:371`, `deploy/images/nifi.Dockerfile:30` | La prueba comprometida corre en **JDK 27**, tomado de `PATH`, y la imagen usa **OpenJDK 21**. El helper previo fijaba JDK 21 (`compatible-libraries/verify.py:130,139-140`). Jackson 3 core trae clases MR para Java 23 que no se activan en 21. **Sin impacto hoy:** repetí todo con JDK 21 y salen 15 comandos correctos, las mismas métricas y el mismo plan `825c4d7b…` | Añadir `--jdk` y un pin de toolchain 21 |
| L5 | `candidate-plan.json`, estados por objeto | El plan no exige sustituir core y databind juntos, y los bloqueos ABI son asimétricos (core 2.22 bloqueado y databind no; al revés en 3.2). Los pares mixtos enlazan: 0 referencias de databind a core sin resolver salvo 5 métodos heredados del JDK, y una lectura sencilla funciona en ambos sentidos en 2.22. Pero cada mezcla falla un control del CVE (`89425` o `91776`). El gate seguiría señalando la tupla residual | Modelar core y databind como unidad atómica por contexto |
| L6 | `verify.py:29-35` | La descarga tiene tamaño acotado, pero no tiempo total (el `timeout=30` es por operación de socket). Su escritura no es atómica: un disco lleno deja un parcial, que falla cerrado hasta limpieza manual. Las redirecciones no se restringen, aunque lo compensa el hash | Escribir en temporal, `rename`, y plazo total |
| L7 | `verify.py:162`, `verify.py:195-199`, `ModuleProbe.java` | Tres detalles: la versión de annotations está fija en código y no se deriva del cierre (hoy coinciden); la caché de JAR no se revalida al terminar, a diferencia de toolchain y fuentes; `ModuleProbe` no comprueba qué versión cargó (su log es idéntico en ambos lados) | Derivar del cierre, revalidar e imprimir `PackageVersion` |

## Hallazgos Low: documentación

| ID | Ubicación | Hallazgo |
| --- | --- | --- |
| D1 | `README.md:3-4` | Dice `Base: f4e32bf` (base del hijo; la base real es `6d67bc2`) y "No … manifest … changes", aunque el commit del padre sí cambia `docs/memoria/manifest.json`. Se refiere probablemente a manifiestos de runtime, pero es ambiguo |
| D2 | Campo `fixed` en `coverage.json` (por ejemplo, línea 41) y `advisory-map.json` | Difiere del `FixedVersion` del escaneo en 18 de 19 ID, casi siempre porque omite versiones 2.x. CVE-2026-89425 muestra `3.1.7, 3.2.3` y omite `2.22.3`, que es el candidato. `official-advisories.json` sí es fiel |
| D3 | `README.md:60-62`, `NIFI_JACKSON_PARENT_20261104.md:18-19` | "Tres de 19 con sonda local" es exacto en los pares de investigación. En los candidatos planos, el contraste antiguo/corregido discrimina solo 2 ID y 4 de 7 tuplas. Quedan sin él `89407` en 2.22 y `91777` en 2.22 y 3.2. CVE-2026-59888 no aplica a 2.22 ni a 3.2 según el escaneo; ahí es un control positivo |
| D4 | `README.md:77-78` | "Cuatro clases" son las públicas. El cambio real afecta a 44 entradas del paquete con versión. El dato no invalida el bloqueo, pero conviene precisarlo |
| D5 | `official-advisories.json` | Datos de upstream poco claros, sin efecto hoy: CVE-2026-59889 tiene el rango `>= 2.21.0, <= 2.22.0` con parche 2.21.5, y por tanto incluye literalmente 2.21.7; GHSA-mhm7 tiene `patched_versions` vacío. Solo afecta al par de investigación |
| D6 | `verify.py:113` | `advisory-map.json` y `official-advisories.json` no entran en `sources_before` ni en `source_sha256` de la evidencia; solo los enlaza el manifest. `verify.py` tampoco comprueba la igualdad de ID entre `coverage.json` y el escaneo. Yo la comprobé: 19 ID en los tres ficheros y en el escaneo, y `official-advisories.json` coincide con las respuestas fijadas |
| D7 | `parent-jackson-…/source-before.json` | Es la captura anterior a las correcciones del padre: difiere en `JacksonProbe.java.in`, `verify.py`, `candidate-plan.json` y `verification-summary.json`. No se cita como prueba final, y el nombre puede confundir con `proof-final/source-before.json` |

## Comprobado y correcto

**Cadena de hashes**
- `verification-summary.json` y `candidate-plan.json` coinciden byte a byte con `proof-final` (`d0291832…`, `825c4d7b…`).
- Los 45 `proof_artifacts`, las 12 fuentes y el `source_sha256` y `artifact_sha256` de la evidencia también coinciden.
- Los 16 hashes del manifest y `RECONCILIACION_20261103.md` coinciden. El hash previo `8c4ab141…` coincide con `6d67bc2`.

**Entradas**
- 86 pins (42 JAR y 44 POM) y 22 pins de upstream coinciden con la caché, sin ficheros extra.
- `input-lock.json` coincide con los tres informes.
- 2.22.3 coincide con los checksums de `deploy/images/nifi.Dockerfile:23-24`.
- `support-lock.json` coincide con `verify.py` y `maven_closure.py`; no ignoré ni cambié ningún pin.

**Reproducción independiente**
- Offline, desde un `git archive` limpio, en JDK 27 y JDK 21: `rc=0`, 15 comandos y mismo plan.
- Tests: 12 candidatos y 12 de guardas de dependencias correctos. La cifra de 4 subtests no la recuento aquí, porque `unittest` solo imprime los tests.

**Clasificación**
- Cuatro objetos planos iguales a su JAR oficial fijado; Hazelcast y Parquet con reemplazo nulo.
- Las 10 filas de paquete, versión y objeto (6 objetos únicos) coinciden con el escaneo en ambos sentidos. Representan 44 tuplas y 48 filas de vulnerabilidad.
- Todo `FixedVersion` de las 48 filas queda cubierto por el candidato de la misma línea.
- Los cierres resuelven core, databind y annotations sin mezclar mayor ni menor. Jackson 3 usa `com.fasterxml.jackson.core:jackson-annotations`.

**Controles antiguo/corregido** (con probe compilado en JDK 21 salvo donde se indica)
- CVE-2026-89425: datos 4295/4308 frente a 457/471, flujo estable en 465/468.
- CVE-2026-91776: caché 1500 frente a 500, repetido 1.
- Invertir `ignored` falla en la guarda prevista en 3.1.2, 3.1.7, 2.22.2, 2.22.3, 3.2.2 y 3.2.3, lo que extiende los cuatro casos de 2.21.
- Invertir `fixed` falla en 2.22.3 y 3.2.2.
- La sonda del hijo sigue aceptando expectativas erróneas en 2.21 (reproducido en JDK 27), como registra `ignore-control-regression.json`. Su fuente coincide con `16b86b5`.

**Límites de proceso**
- Las banderas y los límites declarados están presentes.
- Las rutas `extract` y `fetch_checked` fallan cerrado (ver M3).
- Ningún fichero de runtime, Dockerfile, escáner ni gate cambia en `git diff 6d67bc2 cd811e3`.

## Declarado frente a real

| Afirmación | Real |
| --- | --- |
| 86 pins, 15 comandos, 12 y 24 tests | **Correcto** (subtests no recontados) |
| 156 ficheros iguales a la adquisición | **Correcto**, pero lo impone la revisión manual, no `verify.py` (M2) |
| Wrappers con reemplazo nulo; investigación no es compatibilidad | **Correcto** |
| Consumidores Jolt, CSV y JSR310 por rutas normales | **Correcto** y acotado: solo esas rutas |
| 3 de 19 con sonda local, 16 solo upstream | **Correcto**, con el matiz de D3 |
| Sin inferir cierre de Jackson | **Correcto en el texto**, pero con punto ciego no declarado (M1) |
| Toolchain hasheada | **Correcto**, pero el JDK no es el de la imagen (L4) |
| Limpieza de variables de inyección | **Parcial**: quedan vectores del cargador (L3) |

## Límites de esta revisión

- Sin red: no pude contrastar los pins con Maven Central ni los avisos con GitHub. Solo comprobé la coherencia interna con la caché fijada.
- No ejecuté NiFi, classloaders, imagen, Docker ni el escaneo anidado.
- Toda conclusión sobre referencias se limita a los 156 ficheros de `lib`.
- La otra revisión activa de `compatible-libraries` queda fuera de este informe.
