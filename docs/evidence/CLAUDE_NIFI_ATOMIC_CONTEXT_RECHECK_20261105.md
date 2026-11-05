# Revisión independiente: grupo atómico Hadoop+Snappy, contexto candidato y correcciones Maven

- **Commit revisado:** `0dafc5d9d150a813d5676baa0b11c9b459c53667`, inmutable. Checkout aislado limpio al terminar (`git status` sin cambios) y extracción con `git archive` para las pruebas.
- **Fecha:** 2026-11-05. Revisión de solo lectura, sin commits, push, PR, red, builds de imagen, servicios, SMB ni suite completa.
- **No concede** aprobación runtime, humana, de despliegue, de CG32/SMB/modelo ni excepciones. `review.json` sigue siendo una selección provisional del coordinador.

## Veredicto

**Sin Critical ni High. Cinco Medium y tres Low.** El objeto privado de 22 objetivos es correcto y reproducible. Las debilidades están en la guarda de contexto, en la suite y en la generalidad del subconjunto Maven.

| Objeto | Resultado |
| --- | --- |
| Overlay privado actual, 22 objetivos / 16 NAR / 21 ficheros de contexto | **Reproducido byte a byte.** Sin motivo técnico para no usarlo en un ensamblado **reversible** |
| Promoción de la herramienta de contexto como guarda fiable | **No todavía:** M1 |
| PR con esta cabecera | **La CI de `validate.yml` fallaría:** M2 en ambas versiones de Python, y M3 además en 3.12 |
| Re-pin o familia nueva con `maven_closure.py` | **No todavía:** M4 |
| Jackson (ABI, wrappers restantes, SDK) | Sigue sin elegibilidad. No revisado aquí más allá de M2 |

**Gate actual, recontado desde el informe guardado:** `ci-6d67bc2-nifi/nested-archive-scan.json` da 63 registros y 59 tuplas únicas. Kibana 2 lo tomo de la evidencia, sin recontarlo. No hay escaneo nuevo, así que 59 y 2 siguen siendo las únicas cifras reales.

## Hallazgos

**Código** es un defecto actual del repositorio. **Compuerta declarada** es un pendiente ya documentado y no aparece aquí como defecto (ver [Límites ya declarados](#límites-ya-declarados-no-son-defectos)).

### M1. Medium, código. La guarda de capa acepta bytes arbitrarios y omite barreras que el escritor sí aplica

**Ubicación:** `scripts/nifi_candidate_context.py:57-60` (registro autoafirmado), `:68-73` (el plan solo debe coincidir con el candidato aportado), `:94-100`, `:117-122`. Comparar con `scripts/patch_nested_jars.py:516-517`, `:540-547`, `:553-558`.

`verify()` nunca comprueba `BLOCKED_INPUTS`, antecesores firmados, solapamiento ni inyección. Fuera del grupo atómico no fija ningún hash de reemplazo. Es decir, 12 de los 22 objetivos (7 Guava, 3 LZ4, Hazelcast, Parquet) solo están fijados por `candidate.json`, que aporta quien prepara el contexto. Y `review.json` solo demuestra coherencia interna: basta `decision: approved` y cualquier texto.

**Reproducción sobre stock real, sin instalar** (`scripts/real_ctx.py`, `logs/real_ctx_blocked.log`). Sustituí `amqp-client-5.35.0.jar`, hash `c23f1dff…`, entrada bloqueada de RabbitMQ, por un JAR inventado con la etiqueta de familia `guava` y la referencia literal `self-written by reviewer probe; NOT a review`:

```text
CONTEXT verify ...: {'mode': 'verified-candidate-context', 'archives': 1, 'targets': 1, ...}
WRITER REJECT ValueError known blocked candidate input; separate review required
```

**Diferencial sintético** (`scripts/ctx_syn.py`, `logs/ctx_syn.log`):

| Caso | Escritor | Contexto |
| --- | --- | --- |
| Entrada bloqueada | Rechaza | **Acepta** |
| Antecesor firmado | Rechaza | **Acepta** |
| Objetivos solapados antecesor+hoja | Rechaza | **Acepta** |
| Reemplazo que anida un archivo bloqueado | Rechaza | **Acepta** |
| Reemplazo atómico en un hueco ajeno | Rechaza | **Acepta** |
| Reemplazo atómico anidado en otro reemplazo | Rechaza | **Acepta** |
| No-op | Rechaza | Rechaza |
| Grupo parcial, hash cambiado, intercambio, archivo envolvente | Rechaza | Rechaza |

**Lo que sí se sostiene:** inventario stock fijado, raíces completas, todas las ocurrencias de cada hash, preimágenes, hermanos, payload y el grupo Hadoop+Snappy.

**Impacto actual: ninguno en el artefacto.** El `candidate.json` real se reproduce byte a byte, sus 22 hashes coinciden con los pines o los candidatos fijados y no toca entradas bloqueadas. El riesgo aparece al preparar un contexto nuevo: un error o una regresión pasaría la guarda de la capa, que es el último control antes de instalar. `NESTED_PATCHING.md:70` dice "additionally refused in code", y eso solo es cierto para el escritor y el emisor. Falsificarlo exige controlar el contexto nombrado de un target opt-in, así que no es High.

**Corrección:**

1. Extraer de `patch()` una función común de validación de plan y llamarla también desde `verify()`.
2. Añadir la comprobación de inyección sobre `writer.inventory` de las hojas del payload.
3. Fijar en código la tabla `familia -> (antiguo, nuevo, cuenta)` para los 22 objetivos, o el `candidate_sha256` exacto.

No cambia los bytes del overlay, pero sí el hash de la herramienta.

**Aprobación pendiente:** decidir quién autentica el registro de revisión. Un JSON local no puede autenticarse a sí mismo.

### M2. Medium, código. Regresión real: `jackson/support-lock.json` quedó obsoleto y hay un test en rojo

**Ubicación:** `deploy/images/nifi-patches/jackson/support-lock.json:3` fija `702c9868…`, y `maven_closure.py` es `a792168b…` desde `4bfee41`. Falla en `jackson/verify.py:159`.

```text
FAILED tests/test_nifi_jackson_candidate.py::JacksonCandidateTests::test_bounded_model_namespace_and_tamper_guards
ValueError: integrity .../compatible-libraries/maven_closure.py
1 failed, 21 passed, 5 subtests passed
```

Lo confirmé en el checkout y en la extracción.

**Impacto:**

- `jackson/verify.py` ya no puede ejecutarse. Falla cerrado, y Jackson sigue bloqueado.
- `.github/workflows/validate.yml:35` ejecuta `pytest -q` completo en cada PR, así que **este check fallará** en las dos versiones de la matriz.
- La suite focal de 135+82 es exacta, pero suma solo siete ficheros y no incluye este. La evidencia declara que no es la suite completa. El hallazgo no contradice ese recuento, aunque sí muestra que la selección dejó fuera al consumidor de un fichero cambiado.

**Corrección:** actualizar el lock y repetir el verificador de Jackson. Los 8 cierres de `jackson-databind` siguen iguales a Maven real con el código nuevo (`logs/real_closure.log`), de modo que el cambio de lock no altera resultados. Conviene revisar qué otros consumidores fijan ficheros compartidos cuando se cambian.

### M3. Medium, tests. Un test nuevo falla en Python 3.12 y 3.13, y 3.12 está en la matriz de CI

**Ubicación:** `tests/test_patch_nested_jars.py:414`. La causa está en `scripts/patch_nested_jars.py:121`.

| Python | Resultado |
| --- | --- |
| 3.11.17 | Pasa |
| 3.12.14 | **Falla** |
| 3.13.13 | **Falla** |
| 3.14.8 | No probado: el venv reutilizado no carga allí |

Desde 3.12, `zipfile` aplica por sí mismo el extra `0x7075`, así que `i.filename` cambia y `checked_entries` rechaza antes con `duplicate/ambiguous ZIP path: evil.jar`. El regex del test espera `ZIP extra|Unicode ZIP path`.

**El comportamiento es seguro: falla cerrado en todas las versiones probadas.** La imagen usa python-3.11, así que no afecta al artefacto. Solo es un check rojo en `validate.yml:14`.

**Corrección:** ampliar el regex para admitir el rechazo por nombre ambiguo, sin relajar la guarda.

### M4. Medium, código, sin efecto hoy. `maven_closure.py` sigue divergiendo de Maven sin rechazar

Los 27 fixtures del padre son correctos: leí `result.log` (20 iguales, 7 rechazados, 0 divergentes). **Esa cifra describe esos fixtures, no el modelo.** Con 18 fixtures nuevos contra el mismo driver Aether/Maven 3.9.11 (`3fb91664…`), offline:

| Caso | Línea | Este código | Maven real | Dirección |
| --- | --- | --- | --- | --- |
| R4: el padre importa BOM `${v}`, el hijo sobrescribe `v` | `maven_closure.py:49,76-84` | `leaf:1` | `leaf:2` | **Versión errónea** |
| R5: el padre importa bomA, el hijo importa bomB | `:63,84` | `leaf:1` | `leaf:2` | **Versión errónea** |
| R1: BOM del hijo gestiona `scope=test` de una dependencia heredada | `:88-95` | `leaf, root` | `root` | Superconjunto |
| R2: BOM del hijo gestiona exclusiones de una dependencia heredada | `:88-95` | `leaf, mid, root` | `mid, root` | Superconjunto |
| R3: el camino más cercano excluye, el lejano no | `:148-164` | incluye `z` | sin `z` | Superconjunto |
| R16: exclusiones distintas por camino | `:148-164` | incluye `q` | sin `q` | Superconjunto |
| R7: clave de gestión con propiedad de perfil | `:70,86,107-113` | incluye `leaf` | sin `leaf` | Superconjunto |
| R8: espacios en un selector de exclusión | `:68` | incluye `leaf` | sin `leaf` | Superconjunto |

Los otros 10 son iguales, incluida una reubicación dentro de un perfil: Maven tampoco la aplica, así que **no es defecto**. La causa de R4 y R5 es que Maven hereda las entradas `import` en crudo, las interpola con las propiedades del hijo y prioriza las del hijo. Este código las resuelve en el contexto del padre y las prioriza.

**Impacto actual: ninguno medido** (`logs/real_closure.log`):

- RabbitMQ 5.37.0: igual, 13 coordenadas. La 5.35.0 se rechaza por POM sin fijar, fallo cerrado.
- Jackson: los 8 cierres iguales.
- Los POM reales fijados no tienen la forma de R4 ni R5: `child_import_with_parent` y `child_prop_overrides_import_prop` vacíos en ambos conjuntos.
- No analicé por separado las formas R3, R7 y R8 en los POM reales. Los cierres coinciden con Maven, que es la comprobación que importa.

**Corrección, antes de cualquier re-pin o familia nueva:** rechazar imports heredados combinados con imports o propiedades del hijo, gestión importada que toque dependencias heredadas, claves de gestión dependientes de perfil y selectores con espacios. Rechazar también cualquier nodo alcanzado con conjuntos de exclusión distintos.

**Reproducción:** `scripts/probe_maven3.py`, `logs/maven3.log`.

### M5. Medium, tests. M3 anterior cerrado en el emisor, pero las guardas nuevas casi no tienen protección

Mutantes de una línea sobre los siete ficheros focales (`scripts/mutants.py`, `logs/mutants_{A,B,pairs}.log`). Línea base: 135 tests y 82 subtests.

| Área | Muertos | Supervivientes |
| --- | --- | --- |
| `emit_plan.py` | 9 | 2 |
| `map_candidates.py` | 6 | 8 |
| Escritor: atómico y ZIP | 16 | 10 |
| `nifi_candidate_context.py` | **6** | **23** |
| `hadoop-snappy/prepare.py` | 2 | 3 |
| `maven_closure.py` | 4 | 1 |

**Los importantes, sin test que los fije:**

- **Contexto:** la llamada a `validate_atomic_targets` (`:100`), el bootstrap parcial y aceptado (`:85-88`), las preimágenes y ocurrencias (`:95-99`), el ámbito del payload (`:102`), base y overlay (`:114-116`), hoja y supervivencia (`:119-122`), `verify_rewrite` (`:123-125`) y la comprobación tras instalar (`:131`).
- **Escritor:** la inyección atómica (`patch_nested_jars.py:544`), que es uno de los cuatro ejes que declara M2, y la llamada a `for_rewrite=True` en `rewrite` y `verify_rewrite` (`:409,439`). El par sobrevive junto. El test `test_typed_..._not_dropped_on_rewrite` llama a `validate_layout` directamente y **no prueba** que el reescritor lo invoque. El comportamiento real sí es correcto (`logs/zipedge.log`).
- **Mapper:** hash, cuenta y consumidor desconocido de Hadoop (`map_candidates.py:130,133,177`), y `validate_atomic_targets` (`:208`).
- **ZIP:** los tamaños de `valid_time` (`:209-210`), el valor del descriptor (`:252`) y el stored oculto (`:257`). El par de datos sobrantes del deflate sí muere; la rama `eof/size` (`:273`) sobrevive.

**Algunos están enmascarados por una capa redundante:** `E11`, `W6`, `M8`. No exijo un test por cada capa, pero sí al menos un test de extremo a extremo por guarda.

**Código correcto hoy:** verifiqué cada comportamiento directamente sobre datos reales o sintéticos. Falta que un test lo fije.

### L1. Low, código. `verify_rewrite` no aplica `for_rewrite` a la salida

`scripts/patch_nested_jars.py:439` solo aplica el modo estricto al original. `inventory(payload)` usa el modo tolerante. Un overlay hecho a mano puede llevar 12 bytes opacos por entrada en un `UT` local de un **ancestro reescrito**, y el contexto lo acepta (`logs/ctx_syn.log`, último caso). El escritor nunca produce esa forma.

**Corrección:** una línea, `validate_layout(dst,dst.infolist(),for_rewrite=True)`.

### L2. Low, documentación y evidencia

- `hadoop-snappy/prepare.py:314` y `summary.json` de la prueba v2 dicen `all nine Snappy occurrences remain blocked` y listan `source-bound overlay mapping` como pendiente. El README y el mapper ya permiten el grupo atómico explícito.
- `stock-occurrences/candidate-plan.json` ya no coincide con la salida por defecto del mapper. Difiere solo en `consumer_scope` y en la ruta `replacement`, sin hashes ni estados afectados. Sigue siendo la versión histórica bloqueada.
- `NESTED_PATCHING.md:70`: ver M1.

### L3. Low, operación. `install` no tiene plazo y el contexto fallido no se limpia

- `nifi_candidate_context.py:166-169` limita memoria y CPU, pero no el tiempo de pared. `RUN` no añade ninguno.
- `prepare()` deja el directorio parcial si `verify` falla. Es seguro: el directorio queda rechazado y `prepare` exige salida nueva.

Sin urgencia.

### Información

- **Semántica tras fallo, previa al parche.** Con el stub, 10000 bytes y fallo en el segundo bloque, original y v2 dan la misma secuencia: `64 X 64F written=128 read=10000`. Quien capture la excepción y reintente **pierde el bloque sin error**. v2 solo elimina la salida obsoleta, que es lo que promete. No lo cuento como defecto del candidato.
- **`COPY --from=nifi_candidate_overlay` sin `--build-context`:** por lectura, BuildKit intentaría resolverlo como imagen. La guarda rechazaría cualquier contenido no fijado y `NIFI_CANDIDATE.md` usa `--pull=false`. No lo ejecuté.
- **Etiqueta `cnc-guard-audit:nifi`:** los candidatos usan la misma que la imagen por defecto en CI. Los `compose` de CG14 y CG32 construyen sin `image:` ni `target:`, así que no la heredan, y el procedimiento avisa de conservar los ID previos.
- **`docs/memoria/manifest.json:1077`** conserva `702c9868…` en `previous_current_hashes`. Es histórico, no un lock activo.

## Correcciones posteriores a `b5f158c`

| ID previo | Estado | Comprobación |
| --- | --- | --- |
| M1 Maven (N1, N1b, N2, N4) | **Cerrado para esos casos.** Residuo en M4 | Los cuatro rechazan. `result.log` leído y lógica comprobada |
| M2 grupo atómico | **Cerrado** en mapper, emisor, escritor y contexto. Residuos en M1 y M5 | Abajo |
| M3 tests del emisor | **Cerrado en lo esencial.** `decision`, `families`, `reference`, digest, familia completa, source lock y bloqueo Snappy mueren. Queda `resource removed` | Mutantes |
| L1 salida obsoleta tras fallo | **Cerrado** | Abajo |
| L2 bytes ocultos | **Cerrado** para el escritor. Residuo en L1 de este informe | `logs/zipedge.log` |
| L3 ramas de layout | **Parcial.** Ver M5 | Mutantes |
| L4 `.war` | **Cerrado** | `prepare.py:200` y README. Sigue sin test (`P3`) |
| L5 pin de JDK y candidato | **Cerrado.** Sin test del cableado en `run()` (`P2`, `P4`) | Lectura y `execution.json` |
| L6 pool mezclado | **Declarado** en el README. No lo reproduje, por la restricción de nativos antiguos | Lectura |
| L7 documentación | **Mayormente cerrado** | L2 de este informe |

### Hadoop v2

| Comprobación | Resultado |
| --- | --- |
| `buffer-protocol.patch` sobre la fuente | `20d08bad…`, igual a `patch_source('fixed')` y al pin |
| Recompilación independiente con el JDK fijado | Clase `a2f96d74…`, igual a la del JAR |
| JAR `e2ff7c64…` frente a `dad07af6…` | Solo cambia la clase y se añade la procedencia con `approval: false`. 0 diferencias de atributos ZIP |
| Prueba del padre | 24 comandos, todos rc 0, salidas e inputs con hash intacto, fuentes iguales a la cabecera |
| FaultProbe con stub, sin nativo | Original 3 de 3 y v2 6 de 6 |
| **Control negativo nuevo**, misma capacidad sin `catch` | **Falla** con `stale output ... bytes=4810`, de modo que la sonda discrimina |

No repetí ninguna sonda con nativos antiguos, ni pool mixto, ni entradas hostiles.

### Grupo atómico

- **Mapper:** con los tres candidatos, reproduce `candidate.json` **byte a byte** (`957916e2…`). Sin ellos, los 9 Snappy quedan `blocked-consumer-incompatibility`.
- **Emisor:** reproduce `plan.json` **byte a byte** (`477c6eff…`).
- **Escritor con el plan real** menos Hadoop, solo con Hadoop y con 8 de 9 Snappy: `FAIL CLOSED` en los tres.
- **Reaplicación independiente del plan real:** 131 s, y los 16 NAR **idénticos** al contexto.
- **Parser independiente, `JarFile` de Java:** 16 NAR, 1.040 entradas, 662 JAR, 22 de 22 hojas con el hash esperado. No equivale al classloader NAR.

### Contexto y ZIP

- **Inventario:** recalculado en Python 3.11 con límites, da `5ef46591…`, 215 raíces y 2.099 filas, idéntico a `cnc-atomic-inventory-20261105-05.json` y al del contexto. Las raíces coinciden con `source-lock.json`, sin cambios.
- **`verify` real por CLI:** 24 s, 16 NAR y 22 objetivos.
- **`install` simulado sobre una copia privada** con el diseño de bootstrap del Dockerfile: instala los 16 hashes esperados y deja el resto idéntico. Una segunda instalación falla, y un bootstrap parcial también. No sustituye a una imagen real.
- **ZIP:** los bytes tras EOCD, el payload tras el deflate, el stored oculto, el descriptor falso, el unicode-path, los extras locales arbitrarios, el `UT` inválido, el `0xcafe` no vacío y el ZIP64 incorrecto se rechazan.
- **Toleradas solo donde deben:** `UT` tipado, `0xcafe` vacío y ZIP64 redundante se aceptan en una hoja hermana, con bytes idénticos tras reescribir, y se **rechazan** en un ancestro reescrito.

## Límites ya declarados, no son defectos

- Construcción de imagen y escaneos de los candidatos.
- Classloader NAR, NiFi y procesadores reales, y extracción nativa en Wolfi.
- Revisiones independientes pendientes: Parquet, combinado y Kibana.
- Protected checks, CG32, SMB, modelo y aceptación humana.
- Copias AWS/Azure sin manifest, RabbitMQ, Wire, Jackson restante y OpenTelemetry.
- `review.json` como selección provisional.

## Límites de esta revisión

- **Sin imagen.** `acquire.py` solo materializa archivos `.jar/.nar/.war/.zip`, mientras que `writer.files` rechaza **cualquier** symlink o ruta no canónica dentro de `lib`. No puedo descartar que la imagen real haga fallar `install`. Fallaría cerrado.
- **Suite parcial.** Ejecuté los 11 ficheros NiFi, ZIP y wiring relacionados, no la suite completa. `test_integration_wiring` falla en la extracción por falta de `.git`, un artefacto de mi método, y su test de bundle pasa en el checkout. No ejecuté el resto de ese fichero en el checkout.
- **Mutantes acotados.** Son de una línea y escogidos por mí. Los supervivientes no son todos carencias reales.
- **Fixtures Maven no exhaustivos.** El driver usa Aether embebido, no `mvn` por CLI.
- **Python 3.14** no probado.
- **Hazelcast y Parquet:** solo comprobé sus hashes y su paso por la guarda. No revisé su contenido, que tiene sus propios informes.
- **Recursos.** Procesos pesados con `flock -w 30`, una CPU y pared hasta 140 s. JVM con heap 256 MiB, metaspace 96 MiB, directo 32 MiB y sin cores. La reaplicación usó 131 s de los 140. El candado expiró varias veces por otros procesos, y reintenté sin espera infinita. Los orquestadores Python usaron de 1 a 2 GiB de espacio de direcciones, y el mapper y el escritor 1 GiB, frente a los 512 MiB de sus CLI.
- **Operaciones de borrado.** Solo sobre mi scratch y sobre copias privadas de los JAR de bootstrap. No toqué el padre ni las raíces originales.

## Reproducción

Base: `/home/tears/.cache/claude-nifi-atomic-recheck-0dafc5d`, con `src/` (`git archive` del commit), `scripts/` y `logs/`.

| Tema | Script | Log |
| --- | --- | --- |
| Runner acotado | `scripts/bound.sh` | |
| Guarda sobre stock real | `scripts/real_ctx.py` | `logs/real_ctx_blocked.log` |
| Diferencial escritor/contexto | `scripts/ctx_syn.py` | `logs/ctx_syn.log` |
| ZIP y reescritura | `scripts/zipedge.py` | `logs/zipedge.log` |
| Mutantes | `scripts/mutants.py`, `scripts/pairs.py` | `logs/mutants_A.log`, `mutants_B.log`, `mutants_pairs.log` |
| Maven sintético | `scripts/probe_maven3.py` | `logs/maven3.log` |
| Maven sobre pines reales | `scripts/real_closure.py` | `logs/real_closure.log` |
| Negativos atómicos y reaplicación | CLI del escritor | `logs/real_atomic_neg.log`, `logs/real_apply.log` |
| Contexto real e instalación | CLI del contexto | `logs/ctx_verify.log`, `logs/ctx_install.log` |
| Estado tras fallo | `hb/p2/FaultSeq.java` | `logs/faultseq.log` |
| Parser Java | `hb/zp/ZipCheck.java` | `logs/zipcheck.log` |

## Orden recomendado

1. **Antes de abrir PR:** M2 y M3, de coste muy bajo. Sin ellos, `validate.yml` falla.
2. **Antes de congelar la herramienta o promover el candidato:** M1, junto con L1 y los tests de contexto de M5.
3. **Antes de cualquier re-pin o familia nueva:** M4.
4. **Cuando toque:** el resto de M5, L2 y L3.

Ninguna de estas correcciones cambia los bytes del overlay actual. M1 y L1 cambian el hash de las herramientas, así que habrá que repetir la verificación del contexto con la versión final.
