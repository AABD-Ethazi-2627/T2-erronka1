# Revisión independiente del parche Glob/Minimatch de Kibana — PR119

**Fecha:** 2026-11-04 · **Revisor:** Claude (sub-agente de revisión, solo lectura)
**Commit revisado:** `f80c37f72e35d2a5568b5a0801e4304a23a1ce41` frente a la base `2da877c` (14 ficheros)
**Imagen revisada:** `cnc-guard-local:kibana-glob-candidate`, `sha256:34a89b0e…5ddd`, Node 24.21.0

---

## 1. Veredicto

**El parche técnico se puede promover como candidato de integración, con independencia de la puerta del escáner y de la aceptación externa.** No encontré ninguna rotura real causada por la migración ni por el backport. Tampoco hay hallazgos de severidad alta.

Promover no significa liberar:

- La puerta sigue roja con exactamente dos hallazgos (reproducido, §5).
- No hay aceptación de servicio listo, Elasticsearch ni navegador.
- CI fresco, resource gate CG32 y aprobación humana siguen pendientes.
- Esta revisión no autoriza excepciones ni cambia la política de la puerta. Tampoco actualiza `independent_patch_review`, que sigue `pending` en el repositorio.

**Hay que corregir antes de dar la evidencia por cerrada:** dos errores documentales demostrados (M1 y M2). Ninguno afecta a los bytes de la imagen. Conviene corregir ahora solo los documentos: el comentario erróneo de M1 está dentro de un fichero que se copia a una capa de la imagen, y tocarlo cambia su identidad (§6).

| Severidad | Número | Naturaleza |
|---|---|---|
| Alta | 0 | — |
| Media | 2 | Afirmaciones de evidencia falsas o sobredimensionadas; sin efecto en runtime |
| Baja | 7 | Robustez del guard, limpieza y procedencia |

---

## 2. Hallazgos medios

### M1. La evidencia describe un cambio de Glob 14 que no existe

**Dónde:** `docs/evidence/KIBANA_GLOB_MINIMATCH_20261104.md:57-58` y `deploy/images/kibana-patches/test-glob-migration.js:48-49`.

**Afirmación:** «Glob 14 includes `.` in a bare `**` result; this changed behavior is explicit in the control» y «callers must not assume the older glob 10 result shape».

**Medido:** Glob 10.5.0 en la imagen base y Glob 14.0.3 en la final, ambos con Node 24.21.0 y el mismo fixture:

| Llamada | 10.5.0 (base) | 14.0.3 (final) |
|---|---|---|
| `globSync('**', {cwd, ignore:'**/*.txt'})` | `['.', 'a', 'a/b']` | `['.', 'a', 'a/b']` |
| `globSync('**', {cwd})` | `['.', 'a', 'a/b', 'a/b/keep.txt']` | igual |
| `globSync('**/*', {cwd})` | `['a', 'a/b', 'a/b/keep.txt']` | igual |

**Efecto:** ninguno en runtime; la aserción del test es correcta. El error está en presentarla como prueba de compatibilidad, porque registra como cambio algo que no cambió. Los cambios reales de 14.x (`walk()` devuelve arrays, `isRegExp` pasa a `isMatcher`, se elimina `debug`, la raíz de los `ignore` con `/`) siguen sin ejercitarse. Es defendible porque no hay consumidor real, pero debe constar así.

**Corrección:** en el `.md`, sustituir la frase por «el control fija este resultado; es igual en 10.5.0». El comentario del test se corrige en la próxima reconstrucción (§6).

**Reproducción:** `/tmp/claude-1000/-home-tears--t3-worktrees-B-taldea-integration-complete-project-20261103/321ecb79-f897-489b-8990-a8ca595e5d7d/scratchpad/probes/compare.cjs`, ejecutado en ambas imágenes.

### M2. El arranque acotado se describe con más alcance del observado

**Dónde:** `docs/memoria/RECONCILIACION_20261103.md:344` («llega a configurar203 plugins») y `docs/evidence/KIBANA_GLOB_MINIMATCH_20261104.md:130` («reaches setup of 203 plugins and traces all five root Minimatch importers»).

**Medido en los logs crudos:**

1. `Setting up [203] plugins` es el **inicio** de la fase, a las 10:39:57. El heap se agota durante ella (`FATAL` a 81,3 s de proceso). No hay línea de fin de setup ni fase `start`. La redacción española, «llega a configurar», se lee como completado y no lo está.
2. «All five» es incompleto: el inventario estático tiene **ocho** referencias de import a la raíz. Son cinco de `@kbn/*` más tres bundles de `just-bash` (`browser.js`, `chunks/chunk-R4IFXNY5.js`, `index.cjs`), y estos tres no se cargaron.
3. La línea base no llega al mismo punto. Muere antes (63,6 s) y solo traza tres de los cinco importadores `@kbn`. La frase «also exhausts» es cierta, pero la comparación no permite concluir nada sobre fases posteriores.
4. La traza no muestra ninguna carga de `glob` ni `rimraf` raíz. El código migrado **no se ejecutó** en estos arranques: su evidencia de compatibilidad es solo de los tests de build y de mis sondas.

Los descargos que siguen a esas frases son correctos («no hay aceptación de servicio listo»). El problema es acotado, pero la memoria es el documento académico y debe ser exacta.

**Corrección propuesta:** «Inicia el setup de 203 plugins y agota el heap de 512 MiB durante esa fase, sin llegar a `start`; carga los cinco importadores `@kbn` de Minimatch raíz (no los tres bundles de `just-bash`) y no carga Glob ni Rimraf raíz».

---

## 3. Hallazgos bajos

### B1. El guard no detecta varias formas de import literal

`audit-glob-consumers.js:67-69` clasifica como import solo `require(`/`import(`/`__require(` seguidos directamente de la cadena, o `from "…"`. Además `:70` y `:77` comparan `specifier === 'glob'|'rimraf'`, y `:53` solo lee `.js/.cjs/.mjs`. Ejecuté el guard real con `--check-legacy-migration` sobre un árbol sintético:

| Importador añadido | Resultado del guard |
|---|---|
| `require("glob")`, `import a from "glob"`, `require("rimraf")` | Falla (correcto) |
| Literal partido en el límite de 128 KiB | Falla (correcto) |
| Enlace simbólico presente | Falla (correcto) |
| `import "glob"` (efecto lateral) | **Pasa** |
| `require.resolve("glob")` | **Pasa** |
| `` require(`glob`) `` | **Pasa** |
| `require(/*c*/"glob")` | **Pasa** |
| `require$1("glob")` | **Pasa** |
| `require("glob/package.json")`, `require("rimraf/i.js")` | **Pasa** |
| Nombre calculado (`"gl"+"ob"`) | **Pasa** (ya declarado en la evidencia) |
| Importador en `.ts` | **Pasa** |
| Script sin extensión con shebang | **Pasa** |

**Por qué es baja:** con la base fijada por digest no hay ningún caso real. Lo comprobé con un escaneo propio del árbol final (78 188 ficheros, 532 MB, control positivo `require('rimraf')` en `del/index.js`): cero coincidencias de `require.resolve`, plantilla, `require$N`, efecto lateral, subruta, ruta relativa, invocación de CLI y comentario intercalado. La única cadena `node_modules/glob/` o `node_modules/rimraf/` es la etiqueta interna del bundle de `prettier/cli.js` (§7). Las 18 referencias del inventario base que el guard no clasifica como import son datos (tokens de `gpt-tokenizer`, listas de palabras, opciones). Solo quedó sin escanear `typescript/lib/typescript.js` (9,1 MiB, supera mi tope por fichero).

**Riesgo futuro:** al subir la base, el guard podría pasar sin detectar un importador nuevo de estas formas. La evidencia solo menciona los imports calculados. **Corrección barata:** tratar como fallo cualquier referencia con especificador `glob|rimraf` que resuelva a la raíz y no esté en una lista de permitidos revisada, y ampliar las extensiones.

### B2. El guard no fija versiones de partida y solo mira el árbol previo

`report.packages` se recoge, pero `--check-legacy-migration` no comprueba `glob 10.5.0`, `rimraf 5.0.10` ni `minimatch 10.2.4`. Las guardas de `apply-minimatch-patch.js` validan el tarball de `/patches`, no el fichero de la base. Si se cambia la base, `rm -rf` + `COPY` reemplazaría cualquier versión superior sin aviso. Hoy no ocurre, porque el digest está fijado.

El guard tampoco se ejecuta sobre el árbol final, donde hay paquetes sustituidos (`piscina 5.3.2`, entre otros). **Lo ejecuté yo sobre la imagen final con Node 24.21.0: rc=0**, mismos conjuntos. **Corrección:** afirmar las tres versiones en el guard.

### B3. Falsa alarma con multibyte en el borde de bloque

Un carácter de 3 bytes partido en el límite de 128 KiB, con el import dentro de los últimos 512 caracteres, descuadra `base`. Una sola importación produce dos filas (offsets 131039 y 131037) y `deepEqual` falla. **Falla cerrado**, nunca da un falso verde. El inventario real no lo sufre. Solo afecta a la robustez.

### B4. Alias sobrante y dependencia del hoisting

`brace-expansion-v5` sigue en `package.json:13` y en el lock, pero el Dockerfile ya no lo copia: ahora copia `/patches/node_modules/brace-expansion` (`kibana.Dockerfile:94`). Ambos son 5.0.12 con `balanced-match 4.0.4` anidado, por lo que el resultado es correcto (byte a byte, §5). La ruta nueva depende de la colocación de npm, mientras que el alias era explícito, y ningún test final afirma esa versión. **Corrección:** volver al alias o quitarlo, en la próxima reconstrucción.

### B5. El Minimatch 11.0.4 anidado no es el que ejecuta Glob

`glob/dist/commonjs/index.min.js` solo requiere builtins de Node; `require("minimatch")`, `path-scurry` y `minipass` no aparecen. El inventario (Trivy) ve `minimatch 11.0.4` anidado, pero la entrada `main` que usa Rimraf ejecuta la copia embebida. Solo `glob/raw` llega al anidado, y también es lo único a lo que afecta el `override`.

Por fechas, Glob 14.0.3 (2026-10-28 04:08Z) es anterior a Minimatch 11.0.3 y 11.0.4, así que la copia embebida sería ≤ 11.0.2. Es una inferencia, no una medición. El fix sí está en `main`: el test de 10 000 patrones lo demuestra por la vía correcta. **Corrección:** añadir una frase a la evidencia para que nadie lea el inventario como el código ejecutado.

### B6. Procedencia incompleta en la caché

Los resultados son correctos, pero no se pueden repetir solo con los artefactos:

- **Sin script conductor:** `minimatch10-differential.json` y `patch-guard-controls.json`. Reproduje ambos de forma independiente (§5), lo que reduce el riesgo pero no sustituye el registro.
- **Sin registrar:** el comando de Trivy. `candidate-scan.log` solo contiene un error de `systemd-run` («Failed to connect to user scope bus») y `candidate-scan-v2.log` no muestra el límite. Por tanto, «512 MiB process limit», `--skip-db-update` y `--offline-scan` (`.md:99-101`) no se pueden verificar con el material guardado.
- **Sin indexar:** `mutated-esm-control/`, con fechas de 08:52, anteriores a la preparación del parche. El JSON de resultado es de las 11:28.
- **Puerta local:** la CLI rechaza el informe por identidad (`image report does not identify the expected scan artifact`, rc=1), porque la imagen local no se llama `cnc-guard-audit:kibana`. Los dos errores documentados solo salen llamando a `validate(..., expected_artifact=...)`. Es razonable, pero la evidencia dice «corrected gate» sin indicarlo.
- **Node del guard:** la evidencia cita Node 24.21.0 para el inventario y dice que el guard se repite en el build, donde corre con **Node 26.13.0** del `apk add npm` sin fijar (`candidate-v2-build.log:42`). Para resolución CommonJS no cambia nada medible, pero no es el Node de Kibana.

### B7. Tipografía de la memoria

`RECONCILIACION_20261103.md:327-341` omite espacios («por14.0.3», «Se verifican96000», «Los68», «inventarioOS», «presupuestoCG32»). Es coherente con errores previos del mismo fichero, pero conviene corregirlo junto con M2. Implica actualizar su hash en el manifiesto.

---

## 4. ¿Introduce la migración una rotura real?

**No se ha establecido ninguna.** Esto es lo comprobado y su alcance:

| Pregunta | Resultado | Método |
|---|---|---|
| ¿Importadores nuevos en el árbol final? | Ninguno | Guard real sobre imagen final, rc=0, Node 24.21.0 |
| ¿Quién declara estas dependencias? | Solo `gaxios 7.1.3` queda fuera de rango (`rimraf ^5.0.1` frente a 6.1.4) | 2 623 `package.json` y `semver` de la imagen |
| ¿Gaxios usa Rimraf? | No: ningún `.js` bajo `gaxios` lo menciona | Escaneo del árbol final |
| ¿Piscina se rompe? | No en producción. `run-tests.js` es el script `npm test`, llama a `globSync(pattern, {absolute:true})` y esa API existe | Lectura y `package.json` |
| ¿API de Glob y Rimraf? | Claves exportadas idénticas en base y final | Comparación por imagen |
| ¿Semántica de Rimraf? | `glob:true`, array, ruta inexistente y `preserveRoot` iguales | Ídem, con fixture propio |
| ¿Límites por debajo del tope? | N=2/8/10 → 4/256/1024 en ambas | Ídem |
| ¿API de Minimatch raíz? | Exports y prototipo idénticos; `just-bash ^10.1.1` admite `10.2.4+cncguard.1` | Ídem |
| ¿Clausura copiada? | **528 ficheros idénticos en bytes y permisos** a `npm ci` con el lock más el parche aplicado | Hash por fichero, sin ausentes ni sobrantes |

**El grafo se apoya en cuatro pruebas independientes:** el guard, mi escaneo de formas, el censo de dependencias declaradas y la traza de arranque. Las cuatro coinciden. Un import calculado sigue siendo indemostrable por análisis estático.

---

## 5. Comprobaciones que confirman la evidencia

**Backport de Minimatch 10:**

- El diff real son exactamente los tres cambios de `11.0.0 → 11.0.1` (solo difieren comentarios y `100_000` frente a `100000`), más la retirada de `sourceMappingURL`.
- Con el script real sobre el tarball verificado se obtienen los hashes de la imagen: CJS `f38a510a…c365`, ESM `289f7a11…fa5d`. La imagen también coincide con sus `outputs`.
- Diferencial propio (otra semilla, otro corpus): 4 000 patrones × 11 conjuntos de opciones × 32 rutas, en CJS y ESM. **2 816 000 coincidencias comparadas, además de `set.length`, `makeRe`, `negate` y `globParts`: 0 diferencias.** Opciones incluidas: niveles 0, 1 y 2, `dot`, `matchBase`, `nocase`, `partial`, `nonegate`, `noglobstar` y `preserveMultipleSlashes`.
- En niveles 0 y 1 las dos fases no se invocan nunca (0 llamadas en 6 000 construcciones; control de nivel 2 = 2). El parche es inerte con el nivel por defecto.
- Al cruzar umbrales: `{x,*}/{0..999}` pasa de 1 000 a 2 000 entradas, sin diferencias en 400 rutas. Con tope 64: 256 original, 64 parcheado. N=30 en la primera fase: 100 000 en ~1,1 s.

**Guardas del parche:** ESM mutado, CJS mutado, versión distinta y doble aplicación. Las cuatro dan rc=1 y dejan el árbol sin cambios (hash antes y después).

**Test de abort (control negativo):** sí discrimina.

| Fixture | 10.5.0: lecturas al rechazar → después | 14.0.3 |
|---|---|---|
| Del test (3 directorios) | 2 → **3** | 1 → 1 |
| 127 directorios | 3 → **127** | 1 → 1 |

El margen en el fixture del test es de una sola lectura. Es suficiente junto con la aserción de versión.

**Identidad y hashes:**

- 22/22 ficheros de `tested_source_sha256` coinciden con `f80c37f`.
- 31/31 artefactos crudos coinciden.
- Los snapshots v1/v2 difieren solo en `audit-glob-consumers.js` y `kibana.Dockerfile`.
- El log de v2 re-ejecuta `patches` y reutiliza las capas finales. Los tests finales corrieron en v1.
- `previous_current_hashes` coincide con `2da877c` y las 13 rutas del inventario coinciden.
- `check_cg25_memory.py`: **PASS** (40 criterios, 99 enlaces, 344 hashes actuales y 18 históricos). `historical_snapshot` no se modificó en el diff.

**Escáner:** `validate` con el nombre local reproduce exactamente los dos errores:

- `minimatch 10.2.4+cncguard.1`, en `node_modules/minimatch`.
- `minimatch 3.1.5`, en `del/node_modules/minimatch`.

Glob 10.5.0 y Minimatch 9.0.9 ya no aparecen. `enforce_image_scan.py` no cambia y `VERIFIED_FINDINGS` sigue igual.

**Otros datos confirmados:** 78 273 ficheros y 541 467 035 bytes, 0 enlaces simbólicos, inventario OS 68/68, inventario Node 2 309, duraciones 139,72 s y 66,73 s, salidas 137 y 134, `OOMKilled=false`, `Setting up [203] plugins` en ambas imágenes.

---

## 6. Qué corregir y cuándo

**Ahora, solo documentación (no toca la imagen):**

1. M1 en el `.md`.
2. M2 en el `.md`, la memoria y el JSON si procede.
3. B5, y lo que aplique de B6 (scripts conductores, comando de Trivy, `expected_artifact`, Node del guard).
4. B7.
5. Actualizar hashes del manifiesto y volver a pasar `check_cg25_memory.py`.

**En la próxima reconstrucción, sin reconstruir solo por esto:** comentario de M1, B1, B2, B3 y B4.

**Por qué separarlos:** `test-glob-migration.js` se copia a una capa final (`kibana.Dockerfile:99`) y luego se borra con un `RUN`. Editarlo, incluso solo el comentario, cambia esa capa y por tanto la identidad de la imagen. Eso invalidaría el escaneo y los hashes registrados. Hasta entonces, la evidencia puede anotar que el comentario es incorrecto.

Los cambios de B1 a B3 son distintos: solo tocan `audit-glob-consumers.js` en el stage `patches`, y la v2 ya demostró que un cambio así conserva el ID de la imagen final. Aun así, cambian los hashes de `tested_source_sha256` y hay que ejecutar el guard en un build, así que no compensa hacerlo por separado.

---

## 7. Límites, no defectos

- **Fase `start` no observada.** Fleet, Task Manager y el resto solo cargaron sus módulos. No se ejecutó `.makeRe()` dentro de Kibana (sí en test). El servicio del proyecto usa `--max-old-space-size=1024` (`docker-compose.yml:86`), el doble que la sonda. La aceptación completa sigue siendo externa.
- **La traza `Module._load` no cubre imports ESM.** El arranque de Kibana es sobre todo CJS, pero la cobertura no es total.
- **Copia sin acotar en el navegador.** `@kbn/maps-plugin/target/public/maps.chunk.957.js` embebe el optimizador sin `braceExpandMax` en la primera fase ni tope en la segunda. Solo se entra con nivel ≥ 2 y su nivel por defecto es 1. Es invisible para Trivy, el parche no la toca y no es una regresión. La evidencia ya advierte de copias sin manifiesto de forma genérica.
- **`prettier/cli.js`** embebe un Glob y un Rimraf antiguos. No es el mecanismo de este advisory.
- **`optimizationLevel` dinámico.** Ningún servidor fija `optimizationLevel:` de forma literal, pero no descarté opciones pasadas por variable.
- **El backport acota, no abarata.** Sigue siendo costoso (informe anterior, §4). `ignore` controlado por un atacante sigue sin ser seguro, ni aquí ni en Glob oficial.
- **Mi diferencial** es un corpus con semilla, no exhaustivo. Mis comprobaciones usan Node 24.21.0 en contenedor, salvo `npm ci`, la aplicación del parche, las guardas y las mutaciones del guard, que corrieron en el host con Node 26.12.0.
- **Los 132 registros OS omitidos** siguen sin trazar, como declara la evidencia.
- **DB y paquetes:** el escaneo es local, con la DB de 2026-11-04. CI puede usar otra DB y obtener otro resultado de `apk upgrade`, así que hay que repetirlo allí.
- **Decisión de política:** los hallazgos restantes (`10.2.4+cncguard.1` corregido en código; `3.1.5` sin el mecanismo) son una decisión aparte del responsable. Esta revisión no la toma ni la anticipa.

---

## 8. Corrección a mi informe anterior

`CLAUDE_GLOB_MINIMATCH_ASSESSMENT.md` §3 citaba una copia en línea en `just-bash/dist/bin/chunks/chunk-N6YW4W3Z.js`, tomada del paquete publicado. **Ese fichero no existe en la imagen:** `just-bash/dist` solo contiene `bundle`, `commands`, `AGENTS.md` e `index.d.cts`. Ningún fichero de `just-bash` contiene `firstPhasePreProcess`, así que esa superficie no se aplica a esta imagen. La única copia embebida del optimizador fuera de los paquetes manifestados es la de `maps`.

---

## 9. Ejecución de esta revisión

**Permitido y hecho:**

- Lectura del repositorio y de los artefactos, y sondas en `/tmp/claude-1000/-home-tears--t3-worktrees-B-taldea-integration-complete-project-20261103/321ecb79-f897-489b-8990-a8ca595e5d7d/scratchpad/`.
- Contenedores desechables con `--network none --read-only --memory 512m --cpus 1 --cap-drop ALL`, solo con scripts míos o el guard real. Ninguno quedó residual.
- Descargas públicas de npm, con integridad verificada.

**No hecho:** builds de imagen, arranque de Kibana o Elasticsearch, agotamiento deliberado de memoria, fuzzing sin límite, instalaciones globales, sub-agentes, ediciones del repositorio, pushes, mensajes externos ni excepciones. `git status` limpio, `HEAD` sin cambios.

**No repetido:** las suites Python (el padre informa 15 tests y 21 subtests). Solo ejecuté `check_cg25_memory.py`.
