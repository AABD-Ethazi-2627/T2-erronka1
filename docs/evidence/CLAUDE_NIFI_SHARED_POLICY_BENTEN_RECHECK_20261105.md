# Revisión independiente: política NiFi compartida y evidencia de Benten

- **Commit revisado:** `a098a860e4b183d6a0817c527a4a6e9cd1999c97`, inmutable. La cabecera puede avanzar, pero este informe solo cubre ese commit.
- **Foco:** correcciones de `ce3c1d761ab36f5c69458561cb99647a0f951ef3` frente a la [revisión de 0dafc5d](CLAUDE_NIFI_ATOMIC_CONTEXT_RECHECK_20261105.md).
- **Identidad del código:** entre `ce3c1d7` y `a098a86` no cambia ningún fichero NiFi. Solo cambia `scripts/integration_bundle.py`, que no forma parte de la guarda.
- **Fecha:** 2026-11-05. Sin commits, ediciones del repositorio, builds, servicios, escaneos, push ni PR.
- **No concede** aprobación runtime, humana o de despliegue, ni excepciones. `review.json` y este informe son JSON y Markdown locales: ninguno se autentica a sí mismo ni equivale a una revisión humana.

## Veredicto

**Sin Critical ni High. Dos Medium y dos Low.** M1, M2 y M3 están cerrados, y también los Low de salida estricta y plazo de pared. M4 y M5 quedan parciales.

| Objeto | Resultado |
| --- | --- |
| Guarda de contexto como política compartida | **Correcta en todo lo probado.** M1 cerrado en código |
| Overlay privado de 22 objetivos / 16 NAR | **Elegible para ensamblado reversible en Benten.** Falta ejercitar `verify`/`install` real con esta herramienta (P1) |
| Aceptación runtime, NiFi, classloader, SMB, humana | **Nada de esto se acredita.** Sin imagen candidata ni runtime |
| Gate NiFi | Sigue en **59 tuplas distintas / 63 registros**, último escaneo guardado, recontado de `ci-6d67bc2-nifi/nested-archive-scan.json` |
| PR por M2 y M3 | Esos dos ya no fallan. No es un resultado de CI |
| `maven_closure.py` para re-pin o familia nueva | **No todavía** (N1). Sin efecto sobre los pines actuales |
| Jackson (ABI, wrappers, SDK) | Sigue sin elegibilidad. No revisado aquí más allá del lock |

## Estado de los hallazgos anteriores

| ID | Estado | Comprobación propia |
| --- | --- | --- |
| **M1** blocked, replacement y self-review falsificados | **Cerrado en código.** Queda abierto quién autentica la revisión (decisión, no defecto) | 30 casos sintéticos y 15 falsificaciones sobre metadatos reales |
| **M2** support-lock de Jackson | **Cerrado** | Lock `88b41b42…` igual al fichero en el commit; `verify.py` `6c16e016…` también. Suite de Jackson verde. **No repetí** `jackson/verify.py` completo |
| **M3** test Unicode ZIP en 3.12 | **Cerrado** | 111 tests y 65 subtests en 3.11.17 y 3.12.14 sobre `a098a86`. El regex admite la tercera redacción y sigue exigiendo rechazo |
| **M4** 8 divergencias de 18 | **Los ocho casos, cerrados. La clase, no:** N1 | `fixtures.log` leído: R1, R2, R3, R4, R5, R7, R8 y R16 son `FAIL-CLOSED` |
| **M5** guardas críticas sin test | **Parcial:** N2 | 120 mutantes nuevos |
| **Low** salida estricta | **Cerrado** | `patch_nested_jars.py:440`, mutantes W25 y W26 muertos, y los 16 NAR reales pasan el modo estricto |
| **Low** plazo de pared | **Cerrado** | SIGALRM real entregado (abajo). Queda sin limpiar el directorio de `prepare()` si falla, que es seguro |

## Hallazgos

### N1. Medium, código, sin efecto hoy. `maven_closure.py` aún diverge de Maven sin rechazar

"0 divergentes" describe los 18 fixtures elegidos, no el modelo. Con 24 formas nuevas (28 ejecuciones en dos tandas, con 4 repetidas) frente al mismo oráculo Maven 3.9.11 (clase `3fb91664…`, sin red, sobre la VM), **nueve formas distintas divergen sin rechazo**. Siete pierden un JAR requerido en tiempo de ejecución.

| Caso | Forma | Este código | Maven | Dirección |
| --- | --- | --- | --- | --- |
| N6 | Padre: gestión `test` y dependencia. Hijo: gestión `compile` | `root` | `leaf:1, root` | **Falta JAR** |
| N6b | Igual, padre `provided` v1, hijo `compile` v2 | `root` | `leaf:2, root` | **Falta JAR** |
| N6c | Gestión en el abuelo, dependencia en el padre, `runtime` en el hijo | `root` | `leaf:1, root` | **Falta JAR** |
| N6e | N6 en una dependencia transitiva | `mid, root` | `leaf:1, mid, root` | **Falta JAR** |
| N7b | Clave de gestión heredada `${a}`: padre `leaf`, hijo `other`; `test` | `root` | `leaf:1, root` | **Falta JAR** |
| N7c | Igual, con una exclusión heredada | `mid, root` | `leaf:1, mid, root` | **Falta JAR** |
| N7d | Clave `${project.artifactId}-api` en la gestión del padre | `root` | `parent-api:1, root` | **Falta JAR** |
| N7a | Clave `${a}`: padre `other`, hijo `leaf`; `test` | `leaf:1, root` | `root` | Superconjunto |
| N8 | `<type>${t}</type>` con gestión `test` | `leaf:1, root` | `root` | Superconjunto |

**Causas:**

1. **N6:** `maven_closure.py:155` marca la sobrescritura, pero `:178-180` hace `continue` por el ámbito efectivo heredado antes del rechazo de `:184`. Se pone la marca y nunca se comprueba.
2. **N7:** `:69` hereda claves ya expandidas con las propiedades del padre, y `:146` no las recalcula. Maven hereda el valor crudo y lo interpola en el hijo. `uncertain_management` solo cubre propiedades de perfil.
3. **N8:** `:87` y `:92` no expanden `type` ni `classifier` en la clave, aunque `:197` sí lo hace después.

**Impacto actual: ninguno medido.** Escaneo de formas (`real_shape_scan.py`) sobre los pines reales:

- Jackson (8 raíces): 0 marcas N6, 0 claves `${}` heredadas, 0 N8.
- RabbitMQ 5.37.0: 0 marcas N6, 77 claves `${}` heredadas y **ninguna cambia en el hijo**.
- Los `${tcnative.classifier}` y similares de `netty-handler` son `optional=true`, así que salen antes.
- `report.json` (`bbcc413c…`) con hashes de `fixtures.log` y `frozen.log` comprobados: 8 de 8 Jackson iguales, 5.37.0 con 13 coordenadas iguales, 5.35.0 rechazada por POM Netty 4.2.17 sin pin. **Esto es rechazo seguro, no divergencia.**

**Corrección, antes de cualquier re-pin o familia nueva:**

- Evaluar la marca antes de omitir por ámbito.
- Rechazar claves de gestión heredadas cuyo valor crudo cambie al expandirse en el hijo.
- Rechazar `${}` en `type` o `classifier` de dependencias no opcionales.

Cambiar el fichero obliga a actualizar `jackson/support-lock.json` en el mismo commit, como enseñó M2.

**Documentación afectada:** `NIFI_GUARD_CORRECTIONS_20261105.md:13` ("Maven rechaza las formas … que no modela con seguridad") y `RECONCILIACION_20261103.md:590` se leen como garantía general. El mismo texto dice no implementar Maven completo, pero el rechazo tampoco es completo.

**Controles que no divergen:** gestión intermedia no transitiva, `optional` gestionado, exclusión `*:*`, propiedad de versión heredada sobrescrita, N8b y N6d (rechazo). N7e y N15 fallan cerrado, aunque N15 lanza `KeyError` y no `ValueError`.

**Hipótesis mías refutadas, conservadas:** esperaba que la gestión de la raíz alcanzara a las transitivas y que un `test` directo en la raíz ocultara uno transitivo (N1-N5, N13, N14). Las 7 dan **EQUAL**. El driver usa un consumidor sintético `review:consumer` que depende de la raíz, de modo que la raíz está a profundidad 1. **Esa es la semántica del oráculo:** describe a quien consume el POM publicado, no a un `mvn` ejecutado dentro de ese proyecto ni la gestión real de los NAR de NiFi. La fuente del driver es una copia de `claude-nifi-recheck-f4e32bf/keep/mvn/`; no recompilé para atarla al hash de la clase.

### N2. Medium, tests. Las guardas nuevas tienen tests, pero faltan algunos ejes

Mutantes de una línea escogidos por mí (`mutants_new.py`, `logs/mutants.log`), sobre 3 suites en contexto y escritor y 1 en Maven.

| Área | Muertos | Supervivientes |
| --- | --- | --- |
| `nifi_candidate_context.py` | **23** | 25 |
| `patch_nested_jars.py`: validadores y `verify_rewrite` | 24 | 24 |
| `maven_closure.py` | 15 | 9 |

La revisión anterior dio 6 muertos y 23 supervivientes en contexto. Mueren ahora, entre otros, la llamada a `validate_targets`, el perfil congelado, `validate_replacements`, entrada bloqueada, firma, solape, inyección atómica, salida estricta, plazo, bootstrap parcial y deriva de instalación.

**Sin test que los fije y sin otra capa que los cubra, por lectura:**

- **C32, la llamada a `verify_rewrite` desde el contexto.** Es el eje "preservación exacta de hermanos" y se puede borrar con los tests en verde. El comportamiento real sí es correcto (abajo).
- **C39, C40, C41, W47, W48: los valores reales.** Cambiar un hash de `REPLACEMENT_PROFILE`, el de Hadoop en `ATOMIC_HADOOP_SNAPPY`, o quitar el hash bloqueado de RabbitMQ deja los tests verdes. `test_profile_pins_every_current_component_replacement` (`tests/test_nifi_candidate_context.py:210`) solo mira longitud, suma y nombres, y **ningún test contiene `796d8e28…`, `b5309422…`, `bad77fac…` ni `c23f1dff…`**. "Congelado en código" no está congelado frente a una edición accidental. Fallaría cerrado contra el candidato real, pero un cambio conjunto pasaría.
- **C2, C3, C7, C8, C9: vínculo entre review, candidate, plan y manifest, y estado del candidato.** Sus tests reenlazan los hashes o quedan enmascarados por `validate_targets`.
- **W30, W34 a W39: comentario de archivo y metadatos por campo.** Solo `external_attr` tiene test propio.
- **Menores:** W14 (ocurrencias sin mapear, en el dry-run del escritor), C6 (forma de `families`), W21 (atómico anidado en su propio objetivo), C45 (nombre de bootstrap), C48 (rlimit), M7, M20, M21, M24.

**Enmascarados por una capa redundante, por lectura, sin mutantes emparejados:** C14 a C17, C20 a C22, C25 a C29, C31, W3, W4, W9 a W11, W16, W18, W19, W23, el par W27/W28, W40, W45, M8 a M10, M13. No exijo un test por capa.

**Falso superviviente:** M16 lo cubre `compatible-libraries/test_rabbit.py:46`, fuera de mi selección. Puede haber otros (P2).

**Corrección:** un test de contexto con hermano alterado, una tabla literal de los seis perfiles y los tres bloqueados, y un test por cada vínculo entre metadatos.

### L1. Low, código. El perfil limita a 22, pero no exige los 22

**Ubicación:** `scripts/nifi_candidate_context.py:85-95`. Cualquier subconjunto no vacío de familias pasa si cada hash queda completo y Hadoop+Snappy va junto.

- **Sintético, completo:** `subset-of-profile-one-family-of-two` se acepta en `prepare` y `verify`.
- **Metadatos reales, constantes reales:** solo Guava, solo LZ4, solo Hazelcast, solo Parquet o solo Hadoop+Snappy pasan toda la política y solo paran en `image library inventory drift`, porque mi `source` está vacío a propósito.

**No introduce bytes sin fijar:** cada sustitución sigue en el perfil y las ocurrencias quedan completas. Pero la combinación parcial nunca se ha revisado, y `review.json` dice seleccionar solo el candidato exacto.

**Corrección:** si solo la combinación de 22 es válida, fijar `candidate_sha256` o `plan_sha256` en código, o exigir las seis familias. Si los subconjuntos son deliberados, documentarlo. La decisión es del coordinador.

### L2. Low, documentación

- `NIFI_CANDIDATE.md` ("Unknown files or a different base fail closed"): `writer.files` solo devuelve `.jar/.nar/.war/.zip`, así que un fichero desconocido con otra extensión en `lib` no se detecta. El digest fijado de la base lo mitiga. La frase es exacta solo para archivos.
- `hadoop-snappy/prepare.py:314` sigue diciendo `all nine Snappy occurrences remain blocked` y lista `source-bound overlay mapping` como pendiente. Viene de antes y no se tocó, por los JAR congelados.
- `NESTED_PATCHING.md:70` ("additionally refused in code") **ya es cierto**. Se retira ese punto.

### Información

- **Preservación "exacta" significa contenido, orden central y metadatos listados, no bytes.** `ancestor-physical-order-reversed` y `ancestor-utf8-flag-on-all-entries` se aceptan. No hallé bytes ocultos ni cambio de nombre con ellas. No lo cuento como defecto.
- **Sumarios históricos:** `jackson/verification-summary.json` conserva `702c9868…` y `rabbit-transport-summary.json:44` conserva `c503de0c…`. Por lectura, describen ejecuciones anteriores y no son locks activos.

## Comprobaciones de la implementación actual

### Política compartida: `validate_targets` y `validate_replacements`

Lo usan escritor (`patch_nested_jars.py:571,587`) y contexto (`nifi_candidate_context.py:91,142`). La extracción desde `patch()` no pierde ninguna guarda. Añade la exigencia de digest exacto y el error explícito de antecesor ausente. Sintético en `logs/ctx_phase1.log`:

| Caso | Escritor | Contexto |
| --- | --- | --- |
| Positivo con perfil, atómico completo | Acepta | Acepta |
| Entrada bloqueada | Rechaza | Rechaza |
| Antecesor firmado | Rechaza | Rechaza |
| Solape antecesor+hoja | Rechaza | Rechaza |
| No-op | Rechaza | Rechaza |
| Reemplazo que anida un archivo bloqueado | Rechaza | Rechaza |
| Atómico en un hueco ajeno, raíz y anidado | Rechaza | Rechaza |
| Atómico parcial, hash erróneo, intercambio, archivo envolvente | Rechaza | Rechaza |
| Familia, reemplazo, cuenta u hash viejo fuera del perfil | Acepta **por diseño** | Rechaza |

Los bytes del `source` quedaron intactos en todos los casos. La columna del escritor solo mide el plan, no los overlays manipulados.

### Perfil congelado sobre el objeto real

Sobre `/opt/cnc-guard/nifi-candidate-context-22`, con la herramienta del commit:

| Comprobación | Resultado |
| --- | --- |
| `candidate.json` / `plan.json` | `957916e2…` / `477c6eff…` |
| Inventario canónico | `5ef46591…`, 215 raíces, 2.099 filas, igual al pin |
| Objetivos | 22 en 16 NAR, todos a profundidad 1, 0 antecesores firmados |
| Familias | Guava 7, Snappy 9, LZ4 3, Hadoop 1, Hazelcast 1, Parquet 1 |
| Perfil | 6 entradas, suma 22, 0 discrepancias. Los hashes atómicos coinciden con `ATOMIC_HADOOP_SNAPPY` |
| CLI real con 512 MiB y `source` vacío | Pasa la política y para en `image library inventory drift`, 0,11 s, RSS 50 MiB |

**Falsificaciones con `review.json` escrito por mí** (`logs/ctx_phase2.log`):

| Intento | Rechazo |
| --- | --- |
| `amqp-client` bloqueado con etiqueta Guava | `known blocked candidate input` |
| Solo Hadoop, solo Snappy, Hadoop + 8 Snappy | `atomic Hadoop/Snappy group is incomplete` |
| Guava con otro hash, LZ4 etiquetado Guava, familia nueva, otro archivo de stock | `outside frozen assembly profile` |
| Guava 6 de 7 | `selected leaf hash has unmapped occurrences` |

### Preservación de hermanos

**Sobre bytes reales, sin stock** (`logs/ctx_phase2.log`, 15,7 s con 1 GiB):

- 16 hashes `after` y 16 `before` coinciden; 22 hojas correctas; 0 hashes viejos sobreviven.
- `validate_replacements` pasa.
- Los 16 NAR reescritos pasan `validate_layout(for_rewrite=True)`. **Es la comprobación nueva, y no rompe el overlay real.**
- 640 filas de archivos no tocados son iguales en `sha256`, `signed`, `manifest`, `maven` y `class_packages`. Las clases sueltas no son filas.

**Con `verify_rewrite` sintético:** hermano con contenido cambiado, eliminado, añadido o reordenado, `external_attr`, comentario de entrada o de archivo, `UT` opaco local y antecesor anidado se **rechazan** todos.

### Plazo de pared

`deadline_probe.py` usa `main()` real, solo escala 180 a 1 s y no simula señales. Con `sleep` y con bucle ocupado: `TimeoutError`, rc 1, 1,04 s. No lo probé durante un `install` real. El fallo aborta el `RUN`, y por eso el estado parcial de esa capa se descarta.

### Evidencia de Benten, comprobada localmente

| Registro | Resultado |
| --- | --- |
| `nifi-guards/report.json` | `6b9b84d2…`, igual al documentado |
| `sha256.json` | `326469b7…`. Los 8 ficheros coinciden. 1.339 ficheros iguales antes y después, HEAD `ce3c1d7` |
| `py311.log`, `py312.log` | 111 tests y 65 subtests en cada uno. Ruff 0.17.1: sin errores |
| `maven-ce3c1d7/report.json` | `bbcc413c…`. 18 fixtures: 9 iguales, 9 rechazos, 0 divergentes. Oráculo `3fb91664…` |
| Timeout de JDK | Conservado en `historical_failures`, resuelto con JRE desde caché apt |
| 27 fixtures anteriores | Históricos. El documento no los reetiqueta |

Esa evidencia es de `ce3c1d7` y no autentica nada más allá de sus hashes. Mi ejecución sobre `a098a86` confirma las suites. Los fixtures R no los repetí, porque `maven_closure.py` es el mismo fichero.

## Elegibilidad frente a aceptación

**Ensamblado candidato:** sin motivo técnico nuevo para no intentarlo como paso reversible. Los bytes del overlay no cambian y las correcciones pendientes tampoco los tocarían. N1 no afecta al ensamblado, L1 no afecta a la combinación de 22 y N2 no afecta a los bytes.

**Lo que esto no dice:**

- Que la imagen construya.
- Que `install` pase, y por tanto que el hash real de la capa sea el esperado. Falla cerrado si no.
- Que el classloader NAR, NiFi, los procesadores o SMB funcionen, o que el gate baje de 59/63.
- Que los JSON locales demuestren una revisión. **Falta decidir quién autentica el registro de revisión**, y sigue pendiente la aceptación humana.

## Sondas pendientes, señaladas y no omitidas

El coordinador pidió aplazar nuevas fases pesadas para dar una ventana continua a `fullregression04`. No lancé ninguna después de ese aviso.

| ID | Sonda | Motivo | Coste |
| --- | --- | --- | --- |
| **P1** | `verify` e `install` reales de `a098a86` sobre stock | **No existe ninguna ejecución con la herramienta actual.** `context-verify-current.json` es de las 10:12, anterior a `ce3c1d7`. No hay stock en la VM: no extraje imágenes ni transferí la fuente privada. Por eso no medí la comparación de hermanos no archivo, el hash `before` en imagen ni la duración frente a 180 s. La línea de `verify_rewrite` que los compara no cambió, pero eso es inferencia | Ocurre dentro del build candidato. Basta conservar su log |
| **P2** | Repetir C32, C2, C3, C8, C39 a C41, W14, W30, W34 a W39, W47, W48, M7 y M24 contra las suites NiFi más amplias, con `test_rabbit` | Descartar falsos supervivientes como M16. No bloquea | Menos de 180 s con el candado común |

## Límites de esta revisión

- **Python:** solo 3.11.17 y 3.12.14. Sin `jackson/verify.py` completo, sin revisar el contenido de Hazelcast ni Parquet y sin sondas de Hadoop nuevas.
- **Fixtures Maven no exhaustivos**, con Aether embebido. Los supervivientes y el enmascaramiento son una selección mía.
- **Suite completa:** no la ejecuté. Leí `full-regression-a098a86-02`: en py311, 1 fallo, 1.095 pasados y 4 omitidos, con `test_active_pin_drift_and_floating_images_are_rejected` fallando en la llamada a `docker compose`, y un error en unittest; el resultado de `commands.json` llega hasta `py311-audit`. El coordinador lo atribuye a Compose 2.40 y dice que 5.6.1 lo corrige. **Mi lectura es compatible, pero no lo verifiqué.**
- **Prefetch de NiFi:** `pull.exit` es 143, interrupción deliberada del coordinador para liberar el candado, con capas conservadas.

## Resultados fallidos y desviaciones, conservados

- **rc 75:** la suite focal en py311 falló por contención en el primer intento (`logs/ctx_phase1.log`) y pasó en el único reintento (`logs/ctx_phase2.log`). No se saltó el candado.
- **Error de mi harness:** el primer `real_meta.py` copió campos extra al plan y 13 falsificaciones dieron `unreviewed plan projection`. Era **un rechazo falso**, no una prueba de la guarda. Está conservado en `ctx_phase1.log`; las cifras válidas son las de la segunda ejecución.
- **`unshare -rn` no está permitido en la VM.** Para el oráculo usé `sudo -n unshare --net` con `setpriv` a UID 1000, el mismo método que declara `report.json`. Solo usé `sudo` para eso y para una comprobación `sudo -n true`.
- **Candado:** dos lecturas iniciales con `flock -n` lo tomaron de forma no bloqueante e instantánea. La primera dio `LOCK_HELD`. No esperé ni interferí, pero fue una toma real.
- **`grep` de `netty-handler`:** falló la primera vez por una sustitución de shell mía. Se repitió.
- **Salidas truncadas:** los logs de fases llevan `cut -c`, y por eso algunos mensajes aparecen cortados. Los recuentos no se ven afectados.

## Reproducción

**Local:** `/home/tears/.cache/claude-nifi-shared-recheck-a098a86/`, con `scripts/` y `logs/`.
**VM:** `/home/cncguard/claude-nifi-shared-a098a86/` (154 MiB, conservado). `src/` viene de `git archive` del commit.

Las fases pesadas usaron `flock -E 75 -w 30 /opt/cnc-guard/evidence/remote-heavy.lock`, una CPU, hasta 175 s y sin cores. JVM con heap 256 MiB, metaspace 96 MiB y directo 32 MiB. Sin pytest bajo 512 MiB. Solo la CLI real corrió con su propio límite.

| Tema | Script | Log |
| --- | --- | --- |
| Maven: primera tanda | `probe_maven_new.py`, `run_maven.sh` | `maven_new_01.log` |
| Maven: segunda tanda | `probe_maven_new2.py`, `run_maven2.sh` | `maven_new_02.log` |
| Formas en pines reales | `real_shape_scan.py` | `real_shape.log` |
| Diferencial sintético, plazo, suites | `ctx_resyn.py`, `deadline_probe.py`, `run_ctx.sh` | `ctx_phase1.log` |
| Metadatos y payload reales | `real_meta.py`, `run_ctx2.sh` | `ctx_phase2.log` |
| Mutantes | `mutants_new.py`, `run_mut.sh` | `mutants.log` |

## Orden recomendado

1. **Ahora:** seguir con el ensamblado reversible y conservar el log de `install` (P1).
2. **Decisión del coordinador:** L1, si solo vale la combinación de 22. Conviene resolverlo antes de congelar la herramienta, igual que N2.
3. **Antes de congelar la herramienta o promover el candidato:** los tests de C32 y de los valores congelados (N2). Cambian `tests/`, y no los bytes del overlay.
4. **Antes de cualquier re-pin o familia nueva:** N1, junto con su lock.
5. **Cuando toque:** P2 y L2.
