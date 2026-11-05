# Revisión conjunta de las migraciones del + Minimatch 11 y del Dockerfile de Kibana

**Fecha:** 2026-11-05 · **Revisor:** Claude (sub-agente de revisión, solo lectura)
**Commit revisado:** `0dafc5d9d150a813d5676baa0b11c9b459c53667` (checkout aislado, limpio al terminar)
**Padres incorporados:** del `d8f6699`, MM11 `a48683c`, driver `80a1909`

Este informe no concede excepciones ni aprobación de runtime, humana o de despliegue. Los recuentos autoritativos siguen siendo los de la última CI real `6d67bc2`: NiFi 59 tuplas únicas (63 registros) y Kibana 2. Todo lo revisado es preparación candidata.

---

## 1. Veredicto

**No hay hallazgos críticos ni altos. La mecánica de la migración es correcta y se reproduce, pero hay un riesgo nuevo que nadie ha decidido todavía.**

- **Lo que funciona:** los bytes oficiales, los guards, las 8 referencias y el Dockerfile se sostienen. Tres fases del padre se repiten con hash idéntico desde mi checkout.
- **Lo que falta decidir (M1):** MM11 retiene en memoria entre 35 y 40 MiB por cada patrón de llaves de unos 10-12 caracteres, en una caché de 256 entradas. MM10 no retenía nada. Los consumidores usan el valor por defecto de 100.000 expansiones, no el «cap 64» que citan la evidencia y los tests.
- **Por qué importa la decisión:** el coordinador autorizó las diferencias de semántica (216 en 36.000), no esta amplificación de memoria. M1 no bloquea el ensamblado reversible del candidato, pero sí debería resolverse o aceptarse explícitamente antes de promoverlo.
- **La contrapartida:** en CPU, MM11 mejora mucho frente a MM10 (§4). No propongo volver atrás.

| Severidad | Número | Naturaleza |
|---|---|---|
| Crítica / Alta | 0 | — |
| Media | 1 | Retención de memoria alcanzable, no medida por el candidato |
| Baja | 5 | Excepción nueva, alcance del corpus, cambio de `del` no declarado, documentos obsoletos, cobertura |
| Informativa | 4 | Sin defecto actual |

---

## 2. Hallazgo medio

### M1. MM11 retiene memoria por patrón y los consumidores no tienen el límite que cita la evidencia

**Dónde:**

- Caché de 256 objetos: `node_modules/minimatch/dist/commonjs/index.js:15,21-36` (bytes oficiales de 11.0.4).
- Valor por defecto: `braceExpandMax = 100_000`, en `index.js:934`.
- Afirmación de evidencia: `deploy/images/kibana-patches/MM11_MIGRATION_20261105.md:128` («bounded expansion cap 64»).
- Tests que pasan la opción explícitamente: `test-mm11-migration.cjs:134` y `test-mm11-installed.cjs:49`. Ningún consumidor real pasa `braceExpandMax`.

**Medido** con heap tras `gc()`. Paré siempre muy por debajo del límite: no hay prueba de OOM real.

| Ruta | Patrón | Heap MiB (inicio → tras cada patrón) | Coste síncrono |
|---|---|---|---|
| Función real `matchesExcludePatterns` + `parseExcludePatterns` | `{1..99990}` (10 caracteres) | 5 → 40 → 75 → 110 | ~0,44 s/patrón |
| Función real `resolveInputToConcreteFields` | `{1..99990}/*` (12 caracteres) | 5 → 45 → 86 → 126 | ~0,8 s/patrón |
| `Bash` público real en fixture físico con MM11 | `ls '{1..99999}/*'` | 10 → 49 | 3,9 s |
| `minimatch()` directo | `{a,b}` × 20 (~102 caracteres) | 4 → 74 → 145 | 0,9-1,3 s |
| **Comparación:** MM10.2.4 de la base | `{a,b}` × 20 | 3 (sin crecimiento en 49 patrones) | ~1,2 s/patrón |
| **Comparación:** fork 10.2.4+cncguard.1 | `{a,b}` × 17 | 3 (sin crecimiento en 7 patrones) | ~2,3 s/patrón |

**Alcanzabilidad, por consumidor:**

| Consumidor | Origen del patrón | Puertas observadas |
|---|---|---|
| Significant Events, `GET /internal/streams/_extraction/_eligible` | Query `excludedStreamPatterns`, hasta 500.000 caracteres, separado por comas | Privilegio `STREAMS_API_PRIVILEGES.read`; `assertSignificantEventsAccess`; ajuste de KI continuo activo; cliente de workflows; conector de inferencia; al menos un stream elegible. La query tiene precedencia sobre el ajuste guardado. Las llaves con rango no contienen comas, así que no las parte el separador |
| Observability `get_field_values` | Entrada de herramienta de agente: 10 campos de hasta 1.024 caracteres | `minimumLicense: 'enterprise'` en Agent Builder; mediado por LLM; basta un `*` en cualquier parte |
| just-bash `ls` en Agent Builder | Comando del agente; `ls` está en la allowlist | Igual que la anterior. `maxBraceExpansionResults: 1000` no protege porque las comillas simples evitan la expansión del shell |
| Task Manager, Security Solution | Configuración de Kibana / configuración de telemetría | Confianza operativa, no entrada de usuario |
| Fleet | `new Minimatch` directo, fuera de la caché | Nombres de integraciones |

**Impacto extrapolado, no ejecutado:** con los 1.024 MiB de heap de `docker-compose.yml:86`, unos 29 patrones de 35 MiB bastan aunque la línea base de Kibana fuera cero, y eso cabe en unos 320 caracteres de una sola petición GET. La caché admite 256 entradas, unos 9 GiB. Un agotamiento de heap de V8 termina el proceso; con MM10 el mismo patrón costaba CPU, pero el proceso se recuperaba.

**Impacto actual:**

- Hoy es nulo en operación: no hay imagen construida ni servicio.
- En la imagen futura, por defecto, es condicional. El compose no activa licencia de pago, y Agent Builder exige `enterprise`. Tampoco hay autenticación que frene (`xpack.security.enabled: 'false'`, `docker-compose.yml:70`), aunque el puerto solo escucha en `127.0.0.1:15601`.
- No resolví el nivel exacto de licencia de Significant Events: leí la llamada a la aserción, no su requisito final. La alcanzabilidad HTTP es estática; no arranqué Kibana.

**Por qué no es alta:** exige una licencia o función que el despliegue por defecto no activa, afecta a disponibilidad y no a datos, y solo se expone en loopback.

**Límite ya declarado frente a defecto:** `MM11_MIGRATION_20261105.md:202` declara que no hay garantía general ante patrones hostiles, y el README oficial avisa de lo mismo. Eso cubre la categoría de riesgo. No cubre que «cap 64» se presente como control sin decir que es una opción que ningún consumidor usa, ni la retención nueva, que ningún test mide.

**Opciones (decisión del coordinador):**

1. **Parchear los dos consumidores `@kbn` con entrada de usuario** para pasar `braceExpandMax` por opción. Medido con `braceExpandMax: 1024`, `64` o `nobrace`: 0 MiB retenidos y como mucho 83 ms, sin tocar los bytes oficiales. No sirve para just-bash sin cambiar los bytes de sus bundles. Truncar la expansión puede dar falsos negativos en patrones enormes.
2. **Aceptar el riesgo explícitamente,** ligado a la puerta de licencia, y corregir la línea 128.

En cualquiera de los dos casos, conviene añadir un test de retención y corregir esa línea.

**Reproducción:** `/home/tears/.cache/cnc-claude-mm11-del-review-20261105/probes/{se,extra,lsf,retain,retain2}.cjs`.

**Aprobación pendiente:** decisión del coordinador sobre esta retención. No la concedo aquí.

---

## 3. Hallazgos bajos

### B1. `minimatch()` lanza `TypeError` con patrones cortos

**Dónde:** `index.js`, `mergeRows` → `parse` → `assertValidPattern` (`assert-valid-pattern.js:9-10`). No está en `MM11_MIGRATION_20261105.md`.

**Medido:** `{1..99999}*` (11 caracteres) y `{a,b}` × 14 seguido de `*` lanzan `pattern is too long` en unos 0,5 s, porque las filas fusionadas superan los 64 KiB. Con `{a,b}` × 12 no ocurre. MM10 devolvía un booleano.

**Efecto por consumidor:**

- just-bash lo captura: `ls` termina con exit 1 y el mensaje `ls: pattern is too long`.
- `resolveInputToConcreteFields` lo propaga (medido). No comprobé qué hace la capa superior de la herramienta.
- `matchesExcludePatterns` e `isTaskTypeExcluded` no lo capturan en su propio cuerpo (lectura estática).

**Impacto:** falla cerrado. Un patrón legítimo necesitaría miles de alternativas entre llaves, así que no espero que aparezca en uso normal.

**Corrección:** declararlo en el documento; cubrirlo si se elige la opción 1 de M1.

### B2. El corpus de «9.000 ordinarios, 0 diferencias» no cubre la forma real de varios consumidores

**Dónde:** `MM11_MIGRATION_20261105.md:126`; `test-mm11-migration.cjs:59-60`. Todos los nombres son `logs-<simple>-default`, con las opciones de Fleet: sin `/`, sin punto inicial, sin cadena vacía y sin `**`.

**Medido:** diferencial propia de 1.234 comparaciones con la forma de cada consumidor, MM10.2.4 de la base frente a 11.0.4. Hay 19 diferencias en tres clases:

| Clase | Casos | Ejemplo | ¿Declarada? | Alcance |
|---|---|---|---|---|
| Porción vacía final | 3 | `/_cluster/?(x)` con `/_cluster/`: antes `true`, ahora `false` | Sí, en el changelog oficial | Más estricto |
| Fleet: `.match()` frente a `makeRe` con `/` final | 15 | `logs-*` con `logs-a-default/`: antes `false`, ahora `true` | No | Un nombre de data stream de ES no admite `/` (conocimiento general, no verificado aquí). Sin efecto práctico esperado |
| Extglob positivo con nombre de punto inicial | 1 | `?(logs)*` con `.kibana-x`: antes `true`, ahora `false` | No de forma explícita | Una exclusión de Significant Events con esa forma deja de excluir ese nombre |

**La línea de seguridad se sostiene:** el allowlist real por defecto de `isPathAllowed` (9 rutas, `configuration.js`), contra 28 nombres que incluyen `..`, `.`, `//` y barra final, da **252 comparaciones y 0 diferencias**. No contiene `!(`, así que la ampliación adoptada de negative-extglob no le afecta con los valores por defecto. El allowlist es configurable y no leí la configuración remota.

**Corrección:** declarar las dos clases no documentadas y añadir controles con esa forma. La afirmación actual es cierta para su corpus, pero se lee con más alcance del que tiene.

### B3. `del.sync` ahora falla donde antes devolvía éxito con el directorio intacto

**Dónde:** `DEL_MIGRATION_20261105.md:116,126`, que describen retries y códigos, no este cambio de resultado.

**Medido** en los registros del padre (`tests.json`) con fallo persistente en `rmdir`:

| Error | Antiguo | Nuevo |
|---|---|---|
| EACCES | Sin error, directorio sigue existiendo | Lanza EACCES, 1 intento |
| EBUSY, EMFILE, ENFILE | Sin error, directorio sigue existiendo | Lanza el error, 4 intentos |

**Impacto:** va en la dirección segura. `remove.js` puede dejar de anunciar `Plugin removal complete` en falso, y `cleanPrevious` en `cleanup.js` puede rechazar donde antes continuaba. El registro usa un directorio vacío; no probé esos dos llamadores con un árbol real. `install.js` borra un fichero, así que no le afecta. «Se conserva el error terminal» es cierto para `unlink`; en `rmdir` síncrono es un cambio.

**Corrección:** una línea en el documento y que el coordinador lo incluya en lo aceptado.

### B4. Documentos y comentarios obsoletos

Ninguno afecta a los bytes ejecutados. El Dockerfile y el test sí afectan a la identidad de capa, así que conviene corregirlos en la próxima reconstrucción.

- `DEL_MIGRATION_20261105.md:5,34,93,183`: dice que no instala MM11, que el test comprueba root MM10 y que «the root 10.x finding is expected to remain».
- `DEL_MIGRATION_20261105.md:3-4`: sigue con la aceptación de retries como pendiente, aunque el registro de integración la da por aceptada.
- `kibana.Dockerfile:36`: «root Minimatch retains its API». Ya no es cierto.
- `test-glob-migration.js:48`: el comentario erróneo sobre Glob 14, ya señalado en la revisión del 2026-11-04 y aplazado a la próxima reconstrucción, sigue ahí.

### B5. `MM11_MIGRATION_20261105.md` falta en `active_source_sha256`

**Dónde:** `docs/evidence/INTEGRATION_CANDIDATES_20261105.json`. Su homólogo `DEL_MIGRATION` sí está. `docs/memoria/manifest.json:482` lo cubre con el hash correcto (`e6910efa…`), así que no hay hueco de integridad real, solo una incoherencia entre registros.

---

## 4. Lo verificado

| Requisito | Resultado | Método |
|---|---|---|
| 8 referencias (5 `@kbn` + 3 bundles) | **Confirmado** | Búsqueda literal en 90.107 ficheros sin filtro de extensión, con resolución real. El resto de coincidencias son Glob, `del` antiguo, metadatos o `typesMap` |
| Declarantes runtime | **Confirmado** | Solo just-bash (raíz), Glob 14 (MM11 anidado) y el Glob 7 de `del`, que se retira. Tres dev preexistentes. El campo `overrides` de `openai` no es una dependencia |
| 90 ficheros oficiales | **Confirmado** | Recalculado desde los tarballs: SHA-512 del lock y SHA-256 de cada fichero, igual a `mm11-official-files.json` y a la salida preparada |
| Salida preparada | **Confirmado** | 94 ficheros: 90 oficiales, `.modules.yaml`, Fleet `package.json` y `get.js`, just-bash `package.json` |
| 6 drift + doble aplicación | **Reproducido** | Repetí `test-mm11-migration.cjs`: hash `0574e955…`, idéntico |
| 36.000/216 y 9.000/0 | **Reproducido** | Misma ejecución; ver el alcance en B2 |
| Reemplazo físico y guards previos a mutación | **Confirmado** | Lectura de `mm11-migration.cjs` y `install-del-migration.cjs`; todos los guards preceden al primer `rm` |
| Fleet con `boolean.match` | **Confirmado** | Dos usos de `patternRegex`, ambos sustituidos, en la función real |
| 99 registros de `del` | **Reproducido con la fuente actual** | Hash `960174d4…` idéntico. El diff frente a `d8f6699` es una sola línea, en la rama de imagen final que esa ejecución no recorre. Guards `8df814fc…` idénticos. No reetiqueto el registro histórico: esto es una repetición nueva |
| 6 importadores de `del` | **Confirmado** | Búsqueda propia |
| Guards de imagen final | **Simulados, sin defecto** | Sobre la imagen `34a89…`: 0 symlinks, 0 JSON inválidos, copias y rangos compatibles tras la retirada, `exports` incluye `./package.json`. No se pudieron ejecutar de verdad sin construir |
| Dockerfile | **Sin defecto** | Todas las fuentes `COPY` existen; `.dockerignore` no las excluye; cada `require` relativo está copiado; el orden del + MM11 + borrados es coherente |
| Fuentes y hashes | **Confirmado** | 58 activos, 19 fuentes MM11, 211 artefactos y 298 entradas de artefacto sin discrepancias. Frente al proof de `del` solo difieren, como se espera, `test-del-migration.cjs` y el Dockerfile |
| Arranque endurecido | **Sin defecto** | MM11 CJS/ESM y `del` con `Object.seal` real de Kibana, flags de `bin/kibana` y `--disallow-code-generation-from-strings`. Retry EBUSY con el shim: 4 intentos, ~600 ms, código conservado. Esto no es arranque de Kibana |
| Reintentos async de `del` | **Sin cambio en EBUSY** | Antiguo y nuevo hacen 4 intentos. Descarté mi hipótesis de regresión en la limpieza de Chromium |

**CPU, medida con los mismos patrones:**

| Caso | MM10 (fork) | MM11 |
|---|---|---|
| 378 llamadas con `{a,b}` × 10 seguido de `*` | 3.346 ms | 59 ms |
| `ls` real con `{a,b}` × 10 seguido de `*` | 8.858 ms | 83 ms |
| `ls` real con `{1..99999}*` | > 15 s (sin terminar) | ~1 s, exit 1 |
| Extglob y `*` adversos (20 casos, solo MM11) | no ejecutado | 1-5 ms; llaves 0,4-1 s |

---

## 5. Informativos (sin defecto actual)

- **npm distinto en la construcción:** el componente se probó con npm 11.20.0; `kibana.Dockerfile:6` instala un npm sin fijar. Falla cerrado por `mm11-official-files.json`. Es un riesgo de disponibilidad de la construcción, no de bytes.
- **Asimetría de raíz en `del`:** `posixSync` preserva la raíz; `fs.rm` async no. El Rimraf 3 antiguo tampoco la preservaba, así que no es regresión. Lectura estática; no probado, como se pidió.
- **Claves en `.modules.yaml`:** `del@6.1.1` y `rimraf@5.0.10` no reflejan las versiones instaladas, mientras que just-bash y MM sí se actualizan. No encontré lectores literales en `@kbn/*`, excluidos `target` y `public`.
- **Comparador del corpus:** el `old` de la migración es el fork `10.2.4+cncguard.1` de la imagen previa, no el 10.2.4 de la base. Mi diferencial usa la base. Los modos de fichero no están fijados en la salida.

---

## 6. Límites de esta revisión

- **Sin ejecutar:** construcción de imagen, escaneo, arranque de Kibana o Elasticsearch, navegador. Los guards finales no han corrido contra una imagen real. Solo un escaneo real puede establecer la retirada de los dos hallazgos de Kibana; no proyecto ningún recuento.
- **Sin red.** No repetí `npm ci` ni las descargas; usé los artefactos del padre con hashes recalculados. No repetí `prepare`.
- **Sin OOM ni entradas hostiles en nativos antiguos.** Las cifras de M1 son lineales en 3 puntos y extrapoladas más allá. En MM10 solo usé JavaScript y llaves con presupuesto de tiempo, no CodecPool ni nativos.
- **Borrado de raíces:** no probado.
- **`.gz`/`.br`:** en la búsqueda de referencias los traté como bytes, sin descomprimir. `del-inventory` ya los fija por contenido. Excluí `node/` y `data/`.
- **Alcance de red de las rutas:** estático. No resolví el nivel de licencia de Significant Events ni la configuración remota del allowlist.

**Correcciones a mi propio trabajo:**

- Un primer probe de `ls` inyectaba MM11 con un hook de `Module._resolveFilename`, pero `ls` carga un chunk ESM que lo esquiva, y el control discriminante lo delató. Todas las cifras de `ls` con MM11 de este informe salen del fixture físico (`lsf.cjs`, discriminante correcto). Las de `lsc_old` son MM10 de verdad, y `lsc_new` se descarta.
- El probe `reach.cjs` agotó los 140 s (`rc=124`) y no se usa.
- El bloqueo común devolvió `rc=75` varias veces por contención; esas fases se reintentaron con la misma espera finita de 30 s.

**Recursos y estado:** bloqueo común, 1 CPU, contenedor 384 MiB, heap 256 MiB, red ninguna, solo lectura, sin capacidades, 64 PIDs, core 0. Solo las imágenes `46b0a3…` y `34a89b…` con `--pull never`. Cero contenedores residuales. El checkout sigue limpio en `0dafc5d`, sin cambios en ficheros versionados.

**Salidas:** `/home/tears/.cache/cnc-claude-mm11-del-review-20261105/`.

---

## 7. Aprobaciones pendientes

| Asunto | Quién |
|---|---|
| Resolver o aceptar explícitamente M1 antes de promover | Coordinador |
| Incluir B1, B2 (clases no declaradas) y B3 en lo aceptado | Coordinador |
| QA, manifiesto, construcción real y escaneo fresco con puerta intacta | Padre, sujeto a las puertas de recursos |
| Aceptación Kibana / Elasticsearch / navegador | Pendiente |
| Revisión humana, SMB, CG32, modelo, despliegue | Pendiente; nada de esto se infiere de este informe |
