# Revisión final dirigida: guardas NiFi y MM11.4

- **Commit revisado:** `12ca2fa95c0e6e94665dc75923f3cbdaa2468b24`, inmutable, frente a `a098a860e4b183d6a0817c527a4a6e9cd1999c97`. Si la cabecera avanza, este informe sigue cubriendo solo ese commit.
- **Código de producción revisado:** `caec8a9` (NiFi) y `06e7e46` (MM11.4). Entre `06e7e46` y `12ca2fa`, en `deploy`, `scripts` y `tests` solo cambian `MM11_MIGRATION_20261105.md` y `scripts/integration_bundle.py`.
- **Fecha:** 2026-11-06. Revisor: Claude, sub-agente de revisión de solo lectura.
- **No concede** nota, aceptación runtime, permiso de merge, aprobación humana ni excepciones.

## 1. Veredicto

**Para el candidato fijado actual no encontré ningún defecto Critical, High o Medium en el diff de producción.** Las guardas pedidas hacen lo que se declara, y los hashes comprobados coinciden.

| Objeto | Resultado |
| --- | --- |
| Rechazo de negación con llaves (N1-R) | **Cerrado en código.** Coincide con la semántica de `parseNegate`, `nonegate`, `nobrace` y comentarios del Minimatch oficial 11.0.4 |
| Espera de retención sin compilar patrones nuevos | **Correcta por lectura.** La parada de 8 MiB no cambia |
| Control positivo de caché persistente | **No enmascarado.** Retiene unos 10 MB tras unos 2 s en las 3 ejecuciones |
| Perfil NiFi completo de 22 objetivos | **Cerrado.** Se elimina la vía de subconjuntos parciales (L1 anterior) |
| Cierre Maven con los pines actuales | **Coherente:** 8 cierres Jackson y 13 coordenadas RabbitMQ 5.37.0 iguales. Sin efecto de N1′ |
| `maven_closure.py` para un re-pin o familia nueva | **Todavía no** (N1′): hay formas nuevas que el código acepta sin rechazar |

**Hallazgos:**

- **N1′, sin efecto hoy y a resolver antes de cualquier re-pin.** Es hipotético para los pines actuales. El lado Maven está inferido, no medido.
- **Cuatro huecos Low de test y una imprecisión Low de documentación** (sección 4). Ninguno cambia bytes del candidato.

**Sondas:** ninguna es imprescindible para la corrección del candidato fijado actual, más allá de la build ya en cola y de la matriz en curso (sección 6).

## 2. MM11.4

### Semántica de negación

Contrasté `mm11-bounded-match.cjs:10-20` con `official/dist/commonjs/index.js` de la ejecución 01, comparado con los `sha256` registrados. Es lectura, no ejecuté Node.

| Punto | Oficial | Adaptador | Resultado |
| --- | --- | --- | --- |
| Comentario | `!options.nocomment && charAt(0)==='#'` | `!bounded.nocomment && startsWith('#')` | Igual. La vía del comentario no expande y `match()` devuelve `false` |
| Comentario frente a negación | Se evalúa antes de `parseNegate` | Se evalúa antes de contar `!` | Igual. `!#{a,b}` no es comentario y se rechaza |
| Prefijo de negación | Cuenta `!` iniciales; solo los impares niegan | `/^!+/` y `% 2` | Igual |
| `nonegate` | `!!options.nonegate` | `!bounded.nonegate` | Igual |
| `nobrace` | `braceExpand` devuelve `[pattern]` | `!bounded.nobrace` | Igual: sin expansión no hay truncado |
| Entrada no textual | `assertValidPattern` lanza | Salta la regla y lanza en la vista previa | Falla cerrado |
| Regex | `\{(?:(?!\{).)*\}` | `/[{}]/`, más amplio | Solo rechaza de más. Cubre `!\{…\}` y llaves sueltas |

**Vías que busqué y no funcionan:**

- `{!a,b}` y `{!,}{a,b}`: `parseNegate` corre antes de expandir, y `!a` en una fila es literal.
- `x/!({a,b})` a mitad de patrón: es unión de filas, y perder filas solo estrecha el resultado.
- Fila sin expandir por profundidad o reescrituras: tampoco hallé forma de ampliar el conjunto. Es razonamiento, no medición.
- Centinelas `\.` (riesgo citado en la revisión anterior): contienen `{`, así que entran en la regla y se rechazan.

**P1 positivo:** solo importa en listas de exclusión (`matchesExcludePatterns`, `isTaskTypeExcluded`), donde significa no excluir. En `isPathAllowed`, Fleet, campos y `ls` solo estrecha. Está declarado en `MM11_MIGRATION` y en el JSON del coordinador, sin promesa general.

**Llamadores, por lectura de las salidas preparadas:**

- `isPathAllowed` lanza dentro del suscriptor del `Observable`, sin allowlist permisiva. Por lectura, RxJS lo enruta como error; no lo ejecuté.
- `isTaskTypeExcluded` con `!{a,b}` en configuración lanzará también en cada llamada. Es fallo cerrado, y sigue siendo un límite de disponibilidad bajo configuración explícita.
- Fleet usa `nonegate: true`.

### Retención y control positivo

- `settledDelta` (`test-mm11-migration.cjs:269-274`) solo hace GC, duerme y mide. **No compila patrones durante la espera.** Al agotar 2 s devuelve el delta alto, y el `assert` falla.
- El límite por paso sigue en 8 MiB, y el agregado corto en 24 MiB.
- `longPattern(3800)` da **3.884.973 caracteres por mi aritmética**, por debajo de los 4.000.000 de upstream. Está cerca del límite, y el test no lo fija (T4).
- El control usa `mm.minimatch`, cuya caché real existe en `index.js:21-36`. Valores medidos:

| Ejecución | `raw` | `delta` | `settleMs` | Agregado largo |
| --- | --- | --- | --- | --- |
| 01 | 10.025.176 | 10.062.848 | 2018 | 576 |
| 02 | 10.032.112 | 10.069.784 | 2004 | -12.640 |
| 03 | 10.025.280 | 10.062.952 | 2015 | -9.720 |

**Un matiz sobre lo que demuestran esas tres ejecuciones:** en las 9 filas largas y las 9 de Bash, **`settleMs` es 0**. Ninguna necesitó esperar. Por tanto, estas repeticiones **no ejercitan** el camino "crudo alto y luego liberado". Solo lo ejercita el control, y en su variante "no baja". El informe de la sonda `j` del coordinador no está en el JSON de `12ca2fa`, así que no pude comprobarlo. Las filas cortas no se registran salvo al fallar. No es un defecto: el código es correcto por lectura. Sí significa que "falso rojo eliminado" se apoya en la lógica y en esa sonda, no en estas tres repeticiones.

### Bytes e imagen

| Comprobación | Resultado |
| --- | --- |
| `mm11-bounded-match.cjs` del commit frente a `index.cjs` fijado | `9cc6cbf6…`, iguales |
| 107 salidas preparadas de las ejecuciones 01, 02 y 03 frente a `mm11-output-files.json` del commit | 0 diferencias, 107 ficheros en disco en cada una |
| Imagen `15d5723a…` | `build`, `scan` y `gate` con salida 0. El informe nombra ese `ImageID`, con solo `CVE-2026-19693` y `CVE-2026-56876` |
| Vigencia en `12ca2fa` | El diff `06e7e46..12ca2fa` en `deploy` solo toca un `.md`, y `kibana.Dockerfile` no lo copia. Los bytes de la imagen no se ven afectados |

## 3. NiFi

### Lo corregido

| Forma anterior | Estado | Evidencia |
| --- | --- | --- |
| N6, N6b, N6c, N6e (marca ignorada por `test` o `provided`) | `FAIL-CLOSED` | `new13.log` y sonda propia `ctl6` |
| N7a a N7e (clave heredada que cambia en el hijo) | `FAIL-CLOSED` | `new13.log` y `ctl7` |
| N8, N8b (`type` o `classifier` interpolados) | `FAIL-CLOSED` | `new13.log` y `ctl8` |
| Marca con `optional=true` heredado | Se excluye, como Maven por inferencia | `ctl9`; sin test dedicado de esa combinación |
| Pines reales | 8 Jackson y 13 RabbitMQ 5.37.0 iguales; 5.35.0 rechazada por POM sin pin | `frozen.log`. `oracles.json` lleva `304bc721…` y la clase `3fb91664…` |
| L1 (subconjuntos) | Cerrado: `nifi_candidate_context.py:96-97` | `test_only_the_complete_frozen_profile_is_eligible` falla antes de la corrección (`red.log`) |
| C32 y valores congelados (N2 anterior) | Cubiertos, por lectura | Mensaje específico `post-write sibling content mismatch` y tabla literal |
| Vínculos de metadatos | Cubiertos, por lectura | Tres campos y `review candidate drift`. No repetí mutantes |

**Lock:** `support-lock.json` fija `304bc721…` y `6c16e016…`. Ambos coinciden con los ficheros de `compatible-libraries` en el commit. El lock de `parquet-jackson` no fija `maven_closure.py`. Las referencias restantes a `88b41b42…` son históricas.

### N1′. Formas nuevas aceptadas sin rechazo: sin efecto actual, antes de re-pin

Son formas hipotéticas, **que no aparecen en los pines actuales** en la medida en que los cierres reales salen iguales al oráculo. Ejecuté solo la columna "código" (Python, en scratch privado). **La columna Maven es inferencia mía** a partir de la herencia, interpolación e inyección de gestión; no la medí.

| ID | Forma | Código medido | Maven inferido | Dirección |
| --- | --- | --- | --- | --- |
| H1 | Padre: `a=leaf`, gestión `x:leaf` en `test`, dependencia `x:${a}:1`. Hijo: `a=other` | `root` | `other, root` | **Falta JAR** |
| H1c | Igual, con `x:${project.artifactId}-api:1` y gestión `parent-api` en `test` | `root` | `root, root-api` | **Falta JAR** |
| H1b | Padre: `a=other`. Hijo: `a=leaf`, gestión `leaf` en `test` | `leaf, root` | `root` | Superconjunto |
| H2 | Una POM: gestión `<type>${t}</type>` en `compile` y después gestión literal en `test`, con `t=jar` | `root` | `leaf, root` | **Falta JAR** |
| H2b | Mismo par en orden inverso | `root` | `root` | Igual (control) |

**Causas:**

1. **H1:** `maven_closure.py:165-171` funde el ámbito de gestión en la dependencia usando la clave del padre. Después, `:152` la reindexa en el hijo con la interpolación nueva sin revisar esa fusión. Es N7 por el lado de la dependencia, y la comprobación nueva de `:72-74` solo mira claves de gestión.
2. **H2:** `:188-190` excluye por `test` antes de la comprobación de `uncertain_management` en `:192`. Es el mismo orden que `caec8a9` corrigió para la marca heredada. La confianza en la prioridad entre entradas de gestión es menor.

**Corrección posible, solo antes de un re-pin.** No la recomiendo ahora, porque obliga a volver a fijar el lock y rehacer la evidencia:

- Rechazar una dependencia heredada cuyo GA interpolado en el hijo difiera del resuelto en el padre.
- Mover la comprobación de `uncertain_management` al bloque `optional != 'true'`, y comprobar otra vez los 8 cierres y las 13 coordenadas.

La documentación ya es correcta: `NIFI_CANDIDATE.md`, `NIFI_GUARD_CORRECTIONS` y `RECONCILIACION` hablan de subconjunto acotado sin garantía general, y el JSON dice que no hay éxito divergente solo en las filas elegidas.

### P1 de contexto

| Comprobación | Resultado |
| --- | --- |
| `P1-summary-03.json` | `da8b8227…`, como se indicó |
| Archivo de evidencia | `6296fba5…`. Su `attempt-03/report.json` es `a0db3e62…`, igual al registrado |
| `verify` / `install` | 22 objetivos en 16 archivos, 19,46 y 20,47 s. Salidas exactas leídas |
| Ejecución | `nifi` 1000:1000, 1 CPU, 512 MiB, 180 s, `cap-drop ALL`, sin red |
| Vigencia de la herramienta | `source_commit` es `06e7e46`. `nifi_candidate_context.py` (`fc50beb3…`) y `patch_nested_jars.py` no cambian hasta `12ca2fa` |
| Intentos previos | 01 y 02 conservados como fallos de harness |

**Tres matices, todos ya en la propia evidencia:**

- P1 ejercitó el conjunto **original** de cuatro Jackson. La etapa real `candidate-runtime` usa el conjunto **actualizado**, Python 3.11 de Wolfi y `RUN` como root. Esos tres ejes solo se prueban en la build en cola. Los hashes de `BOOTSTRAP` coinciden con los `--checksum` de `nifi.Dockerfile`, y no preveo un fallo por lectura.
- `rss_measured` es `false`. El límite de 512 MiB se cumple, pero no hay RSS medido.
- **`12ca2fa` sigue diciendo que P1 está pendiente**, y `P1-summary-03.json` no está entre sus 2161 artefactos. Es coherente con el orden de los hechos (P1 terminó después). La próxima conciliación debe vincularlo, en vez de darlo por acreditado desde este commit.

## 4. Huecos de test y documentación, todos Low

Sin campaña de mutantes, por petición expresa: son por lectura.

| ID | Hueco | Efecto de no tenerlo | Corrección |
| --- | --- | --- | --- |
| T1 | `test-mm11-installed.cjs:29-34` ya no ejercita el rechazo por filas. `!{1..2000}` entra ahora por la rama negada y solo queda `{1..1024}` en positivo. **Regresión pequeña de esta corrección** | Lo cubren el hash del adaptador y el test de componente | Añadir `{1..1025}` |
| T2 | No hay control de negación par (`!!{a,b}`) ni de `nocomment` con `#{1..2000}` | `negations > 0` solo rechaza de más. Quitar `!bounded.nocomment` truncaría en silencio, pero ningún consumidor pasa esa opción | Dos líneas |
| T3 | Ningún test ejercita `!{…}` por `fields` ni por Bash | Mismo adaptador | Un caso por vía |
| T4 | Nada afirma que `longPattern(3800, …)` conserve sus filas. Margen de unos 115.000 caracteres | Si cambiara, se mediría en silencio un patrón truncado | `assert` del número de filas |
| D1 | `MM11_MIGRATION` dice "Bash reports exit 1 for these unsupported inputs". En `ls`, el matcher solo se alcanza con `*`, `?` o `[`. `ls '!{a,b}'` va por la vía de ruta literal y no llega a él. Esa afirmación no está medida para negación | Sin efecto de seguridad: no hay coincidencia | Matizar la frase o añadir el test de T3 |

Los comentarios sobre `+cncguard.mm11.3` en `MM11_MIGRATION:285` están en una sección etiquetada como histórica. No lo cuento como hallazgo.

## 5. Límites restantes, separados de los hallazgos

- **Sin aceptación de:** Kibana o Elasticsearch en servicio, imagen NiFi, escaneo anidado (último atribuido: 59/63), NAR o classloader, SMB, CG32 completo, CI protegido, modelo ni revisión humana.
- **MM11.4:** sin cota de concurrencia real ni de memoria transitoria. P1 positivo sigue declarado. `v8.queryObjects` es experimental en este Node y emite un aviso esperado por stderr.
- **Maven:** subconjunto acotado. Las filas del oráculo son una selección. Las 28 filas nuevas **no** son 28 formas distintas. Los tests posteriores a la corrección se vincularon después de ejecutarlos, y así lo declara el coordinador.
- **Identidad del candidato:** `plan_sha256` y `candidate_sha256` no están en código. Sí lo están los hashes de reemplazo, cuentas, perfil e inventario, lo que acota el contenido. El registro `review.json` sigue sin firma.

## 6. Sondas

| Sonda | ¿Necesaria ahora? | Motivo |
| --- | --- | --- |
| Build real de `candidate-runtime`, en cola | **Sí, ya prevista** | Único ejercicio de Wolfi, root y los cuatro Jackson actualizados. Conservar el log aunque falle |
| Matriz `full-regression-12ca2fa-01`, en curso | **Sí, ya prevista** | No la leí ni repetí. No doy por conocido su resultado |
| Oráculo Maven de H1, H1b, H1c, H2 y H2b | **Solo antes de un re-pin** | Menos de 1 s por tanda en las ejecuciones anteriores. Convierte la inferencia en medición |
| `j-mut` (adaptador con caché en la prueba real) | Opcional | La lógica ya lo cubre por lectura. Confirmaría el rojo en la prueba comprometida, con unos 70 s de VM según la estimación anterior |

## 7. Qué hice y qué no

**Ejecutado:** 3 procesos Python de menos de 1 s con `nice`, sin Java, Node, red ni VM. Hashes en streaming de los **1311 artefactos** de post-revisión, Kibana `06e7e46` y vinculación de fuentes, de los 2161 del JSON: 0 ausentes y 0 discrepancias. También 72 fuentes activas y 3×107 salidas: 0 discrepancias.

**Sin comprobar por mí:** los otros 850 artefactos. Tampoco repetí `red` ni `green`: leí sus logs, con 122 pasados y 71 subtests en cada Python, y 8 fallos antes de la corrección. Los comandos del oráculo salieron con 0.

**Hipótesis mías refutadas:**

- Fallo por el lock de `parquet-jackson`: no fija `maven_closure.py`.
- Vía de negación por `{!a,b}`: `parseNegate` corre antes.
- Truncado en `longPattern(3800)`: por aritmética queda por debajo.
- Fallo previsible del contexto en el conjunto actualizado de Jackson: los hashes coinciden.

**No hice:** commits, ediciones del repositorio, push, PR, aprovisionamiento, contenedores, credenciales, SMB ni navegador. `git status` del worktree seguía limpio en `12ca2fa`.

**Scratch:** `/tmp/claude-1000/-home-tears--t3-worktrees-B-taldea-integration-complete-project-20261103/3fb2ca5d-1b3b-4dfb-95f6-63e8afba32cc/scratchpad/final-guards/probe/forms.py` (`a2c851ec…`) y `forms.out` en el mismo directorio (`1a5cc52f…`).

## 8. Orden recomendado

1. **Ahora:** seguir con la matriz y la build en cola. No tocar `maven_closure.py`.
2. **Si se reconstruye algún byte de test o documentación:** T1 y T4, y matizar D1. T1 a T4 están en ficheros que la evidencia fija por hash (`mm11-output-files.json` no los incluye, pero `sources-before.json` y el JSON del coordinador sí), así que conviene agruparlos con la siguiente repetición prevista, no forzar una solo por ellos.
3. **Próxima conciliación:** vincular P1 con su `source_commit` real, sin afirmar que sea `12ca2fa`.
4. **Antes de cualquier re-pin o familia nueva:** oráculo de N1′, y corrección con su lock.
