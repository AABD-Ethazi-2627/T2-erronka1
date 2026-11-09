# Recomprobación MM11 sin caché en Benten: parada de 8 MiB y N1

**Fecha:** 2026-11-05 · **Revisor:** Claude (sub-agente de revisión, solo lectura)
**Commit:** `a098a860e4b183d6a0817c527a4a6e9cd1999c97`, inmutable
**Código:** `git diff 2829a6f a098a86 -- deploy/images` solo cambia `MM11_MIGRATION_20261105.md` y `test-mm11-migration.cjs`. El código de producción de `a098` es el mismo que el de `2829a6f` y el de la imagen `f331e91e…`.

Este informe no concede aprobaciones ni excepciones, y no sustituye ninguna puerta protegida.

---

## 1. Veredicto

| Asunto | Clase | Estado | Severidad |
|---|---|---|---|
| Parada de 8 MiB en run05 y run07 | **Artefacto de medición.** La retención la causa el motor V8, no una caché | Causa identificada; la corrección de la prueba **falta validarla** | — |
| T1: la prueba mide en una carrera con los jobs de TurboFan | **Bug de la prueba** | Abierto | Media: bloquea la puerta y da falsos rojos |
| M1-R: caché persistente o crecimiento lineal | Código | **No se reproduce.** Corregido en lo medido | — |
| N1 por número de alternativas | Código | **Corregido** | — |
| **N1-R: un patrón negado aún falla abierto** por los otros 3 límites | **Bug de código** | **Abierto y medido** | Baja en alcance actual; **contradice la documentación** |
| P1: truncado silencioso en patrones positivos | Código | Abierto y medido | Baja |
| O1: `#{1..2000}` lanza en vez de devolver `false` | Código | Abierto y medido | Informativa |
| Integración: imports, opciones y compilación | Código | Correcta en lo comprobado | — |

**Decisión que hace falta:**

1. **Sin cambios de producción**, solo la corrección de T1, la imagen `f331e91e…` sigue describiendo el código. En ese caso hay que corregir `MM11_MIGRATION:290-292` y declarar N1-R y P1. Esa decisión es del coordinador.
2. **Si se corrige N1-R en el adaptador**, cambian `mm11-output-files.json` y los bytes de la imagen. Habría que volver a construir, escanear y revisar.

No propongo subir ningún límite. Los 8 MiB y los 1024 no cambian.

---

## 2. Diagnóstico de la parada de 8 MiB

### Qué lo causa

Un **job concurrente de TurboFan en curso** mantiene viva la clausura que está optimizando. Esa clausura apunta a su `Context`, el contexto a `this`, y `this` es la instancia compilada. Cuando el job termina, todo se libera sin más compilaciones.

`await new Promise(setImmediate)` no espera a ese job, y por eso run07 también paró. El job vive en un hilo de trabajo y tarda unos 50 ms, y el salto de `setImmediate` no lo espera.

### Evidencia que discrimina

Cada fila es la copia instrumentada de la prueba `60a5ac63…` completa, con el mismo estado JIT, sobre las salidas preparadas de run07. Paré cada proceso en la primera parada y no compilé más patrones después.

| Brazo | Disparos ≥ 8 MiB tras `setImmediate` | Residuo |
|---|---|---|
| Flags por defecto, 6 ejecuciones | **3/6**; 5/6 si se mide de forma síncrona | ~10,04 MiB, igual que los 10.042.616 de run07 |
| Solo TurboFan (`--no-maglev`), 4 ejecuciones | **4/4** | 9,65–10,08 MiB |
| Solo Maglev (`--no-opt`), 3 ejecuciones | 0/3 | ≤ 21 KB |
| Sin optimizadores (`--no-opt --no-maglev`), 2 ejecuciones | 0/2 | ≤ 15 KB |
| **TurboFan síncrono** (`--no-concurrent-recompilation --no-maglev`), 3 ejecuciones | **0/3** | ≤ 47 KB |
| **TurboFan con retardo de 1000 ms** (`--concurrent-recompilation-delay=1000`), 2 ejecuciones | **2/2** | **43,3 MiB**, que dura **2,3–2,6 s** |

El último brazo es la prueba más fuerte. Al retrasar el job crecen el tamaño y la duración del residuo: 43,3 MiB son las dos instancias, la de 4095 y la de 1023 caracteres. Después baja a −0,16 y −0,99 MiB sin ninguna compilación nueva.

### Otras cuatro señales

- **Se libera solo.** Sin retardo artificial, los 7 disparos de la prueba completa bajan a ≤ 65 KB en **28–35 ms**, sin compilar nada. El peor caso del probe independiente es de 45 ms.
- **No hay crecimiento.** En 8 pasos de 4095 + 1023 caracteres con `--no-maglev` hubo 7 residuos crudos de ~10 MiB, y el agregado final fue de **−0,64 MiB**. Con flags por defecto fue de −0,67 MiB. Las instancias vivas fueron 0 en todas las ejecuciones completas.
- **Cadena de retención**, tomada del snapshot en el momento de la parada:
  ```
  (GC roots) → (Handle scope) → system/Context → previous Context → context:this → BoundedMinimatch
  ```
  Hay **una sola** instancia del adaptador. Es una raíz del motor, no una `Map` ni un módulo.
- **Traza `--trace-opt`.** Dos jobs, `#matchRow` y una función flecha, empiezan justo antes de `after-fields` y terminan **después** de `measured`, con 50,7 y 52,4 ms.

### Control positivo

Una sola llamada a `official.minimatch` con el mismo patrón de 1023 caracteres retiene **10,14 MiB**. No baja en 2 s de sondeo ni tras la GC agresiva de `queryObjects`. Quedan 2 objetos, que interpreto como la instancia cacheada más `BoundedMinimatch.prototype`.

Esto es lo que la distingue del artefacto: la caché real no se libera, y el arnés sí la ve.

### Hipótesis descartadas

| Hipótesis | Por qué no |
|---|---|
| Caché persistente nueva | Agregado máximo de +26 KB, 0 instancias vivas, residuo liberado |
| Caché de módulo de MM11 | `lastSplit` y `lastChecked` guardan la ruta, no el patrón. `foldCache` guarda expresiones regulares de un carácter |
| Raíces del arnés | Existen: el snapshot tiene 30 objetos `Minimatch` normales, y la cadena inspeccionada sale de la caché `cache` del módulo ESM oficial, usada por los controles de la propia prueba. Son de antes del paso y no entran en el delta |
| Temporales de la pila | Con TurboFan síncrono no hay residuo |

### Lo que no queda demostrado

- `(Handle scope)` no nombra el job. La atribución se apoya en la traza, en la dependencia del retardo y en el brazo síncrono.
- Maglev no queda exonerado. Dio 0/3, pero sus jobs usan un mecanismo parecido y pueden ser más cortos.
- No medí `--no-concurrent-recompilation` con Maglev activo.
- El probe mínimo en frío no disparó con flags por defecto (0/4). El fenómeno necesita JIT caliente, así que ese probe por sí solo no sirve de control.

---

## 3. Alcance actual y límites teóricos

| | Actual, medido | Teórico, **no medido** |
|---|---|---|
| Persistente | Nada: ≤ +26 KB y 0 instancias | Sin mecanismo conocido |
| Transitorio por job | ~10 MiB una instancia, 28–45 ms | 43,3 MiB solo con retardo artificial |
| Varios jobs | 2 instancias, solo bajo retardo | La cola de V8 admite 8 jobs (`--concurrent-recompilation-queue-length=8`). Con ~41 MiB por instancia daría unos 330 MiB transitorios. Es una cota de cálculo y no sé si se alcanza |
| Repetición | La traza muestra que las mismas funciones se vuelven a marcar en cada paso, porque cada instancia crea clausuras nuevas | **No es solo el calentamiento inicial.** Puede repetirse con cada patrón largo |

Coincide con lo que ya dice `MM11_MIGRATION:294`: no es una garantía general de memoria transitoria, CPU o disponibilidad. **No he medido presión de memoria real, concurrencia de peticiones ni Kibana en ejecución.**

---

## 4. N1-R: un patrón negado aún falla abierto

### Qué ocurre

El adaptador solo detecta el **número** de filas. `brace-expansion` 5.0.12 tiene otros tres límites internos que recortan **sin error**, y `braceExpand` de Minimatch no permite ajustarlos ni los hace visibles.

Medido con el `isPathAllowed` real y la salida preparada:

| Límite | Patrón | Candidato | Longitud | Resultado | Control |
|---|---|---|---|---|---|
| Número (1024) | `!{1..2000}` | `1500` | 10 | Lanza, correcto | — |
| **Caracteres (4.000.000)** | `!{1..1024}` + 4090 `/` + `x` | `1000/x` | 4.101 | **`true`** (976 filas) | `500/x` da `false` y 1011 caracteres da `false` |
| **Profundidad (1000)** | `!` + `{x,`×1002 + `{a,b}` + `}`×1002 | `a` | 4.014 | **`true`** | profundidad 900 da `false` |
| **Reescrituras (1000)** | `!p{a}` + `}`×1002 + `,z}` | `pz` | **1.010** | **`true`** | 50 reescrituras da `false` |

Es el mismo fallo que N1: la alternativa se pierde, deja de coincidir y la negación lo convierte en acierto.

### Alcance

- **Actual:** exige una entrada `!` en la lista de permitidos. Las 9 rutas por defecto no usan `!` ni llaves. No he leído la configuración remota de esa lista.
- **Fleet** usa `nonegate`, así que no le afecta.
- **Documentación:** `MM11_MIGRATION:291` dice «This replaces silent truncation», y eso **solo es cierto para el número de filas**. La frase sobre `!{1..2000}` sí es correcta.
- **La propia prueba pasa por este camino.** Por aritmética, `longPattern(4095)` debería quedarse en unas 976 filas, no en 1024: lo «aceptado» ya está recortado. Medí 976 y 977 filas con patrones de 4.101 y 4.100 caracteres.

### Riesgo adicional, por lectura de código y sin medir

Los límites cuentan caracteres **internos**. `escapeBraces` convierte `\.` en un centinela de unos 27 caracteres, y cada reescritura añade otro. Por eso la longitud visible del patrón no sirve de frontera:

- `!{1..1024}/` + `\.`×300 podría recortarse con unos 600 caracteres.
- `!{1..1024}p{a}` + `}`×200 + `,z}` podría recortarse con unos 220 caracteres.

**Por eso no recomiendo un tope de longitud.** Mi primera idea era un tope de 1000 caracteres, y este análisis lo descarta como solución única.

### Corrección recomendada (código de propuesta, sin ejecutar)

Comparar con una expansión de límites ampliados, y rechazar si difieren. Cierra los 3 límites en patrones negados y positivos:

```js
const { createRequire } = require('node:module');
const be = createRequire(require.resolve('minimatch'))('brace-expansion');
// ...
constructor(pattern, options = {}) {
  const bounded = { ...options, braceExpandMax: BRACE_EXPAND_MAX };
  const rows = official.braceExpand(pattern, { ...bounded, braceExpandMax: BRACE_EXPAND_MAX + 1 });
  if (rows.length > BRACE_EXPAND_MAX) throw new RangeError('CNC Guard matcher expansion budget exceeded (1024)');
  if (!options.nobrace && /\{(?:(?!\{).)*\}/.test(pattern)) {
    const wide = be.expand(pattern, { max: BRACE_EXPAND_MAX + 1, maxLength: be.EXPANSION_MAX_LENGTH * 2,
      maxDepth: be.EXPANSION_MAX_DEPTH * 2, maxRewrites: be.EXPANSION_MAX_REWRITES * 2 });
    if (wide.length !== rows.length || wide.some((row, i) => row !== rows[i])) {
      throw new RangeError('CNC Guard matcher expansion truncated by internal limit');
    }
  }
  super(pattern, bounded);
}
```

- **Coste:** una expansión más, hasta unos 8 MB de caracteres transitorios.
- **Efecto secundario deliberado:** `longPattern(4095)` pasará a **rechazarse**, porque hoy se recorta. Las pruebas deben usar una longitud sin recorte (hasta unos 3,9 KB) y añadir un caso de rechazo explícito. Esto no es subir un límite, es dejar de aceptar lo que se trunca.
- **Pruebas nuevas:** las 3 filas de la tabla y sus controles, en `test-mm11-migration.cjs` y en `test-mm11-installed.cjs`. Hoy ambas solo cubren el número de filas.
- **Alternativa más pequeña:** rechazar `!` con llaves. Cierra el fallo abierto en la lista de permitidos, pero deja P1. Si se elige, hay que declarar P1.

### Otros dos hallazgos

**P1. Truncado positivo (bajo).** Medido en funciones reales:

- `{1..1024}` + 4090 `/` + `x` no excluye `1000/x` en `matchesExcludePatterns` ni en `isTaskTypeExcluded`, y sí excluye `500/x`.
- `{{` + 1500 comas + `,x},z}` no excluye `x`, y sí excluye `z`.

En una lista de exclusión, eso significa no excluir. Exige un patrón de configuración poco realista. La corrección anterior también lo cubre.

**O1. Comentarios (informativo).** `#{1..2000}` lanza, mientras que el `minimatch()` oficial devuelve `false` para los comentarios. Falla cerrado. Basta con documentarlo.

---

## 5. Integración

| Requisito | Resultado | Método |
|---|---|---|
| 5 consumidores `@kbn` usan el adaptador | **Sí** | Lectura de la salida preparada |
| 3 bundles usan el adaptador y `CncPattern` está dentro de una cadena `let` | **Sí**, no crea una variable global | Lectura |
| Bytes del adaptador en la VM | `3e3f6637…`, igual que en `a098` | Hash |
| Salidas preparadas | 107 ficheros | Recuento en la VM |
| Campos: compila una vez por llamada | **1 compilación para 50 campos** | Medido |
| Exclusiones: compila por llamada y patrón | 20 compilaciones para 10 llamadas × 2 patrones | Medido |
| Coste por llamada con patrón corto | 31 µs frente a 1 µs con caché | Medido |
| Opciones | `braceExpandMax` siempre es 1024, aunque se pida 99999 | Medido |
| Subclase de la oficial | **Sí** | Medido |
| Límite exacto | 1024 pasa y 1025 lanza. También lanzan los casos anidado, cruzado y con vacíos, en negado | Medido |
| Imagen `f331e91e…` | Construcción y puerta con exit 0. El guard instalado imprime `rootVersion 11.0.4`. El escaneo tiene 2 HIGH, ambos de `extract-zip`: CVE-2026-19693 y CVE-2026-56876 | Logs locales. **No es aprobación de runtime** |

**Sin verificar (probe `i`):** qué hacen los llamadores reales cuando salta el `RangeError`, si la llamada a `isTaskTypeExcluded` en cada ciclo de claim encarece algo, y si `just-bash` tiene otras importaciones de `minimatch`.

---

## 6. Corrección de T1 (propuesta, sin validar)

Diff completo: `/tmp/claude-1000/-home-tears--t3-worktrees-B-taldea-integration-complete-project-20261103/ccc9f57b-c221-4fd5-ad8a-334387be7abc/scratchpad/proposed-test.diff`. La copia en la VM es `mine/patched-test.cjs`. Solo pasa `node --check`.

```js
const STEP_STOP = 8 * 1024 ** 2, SETTLE_DEADLINE_MS = 2000;
const settledDelta = async base => {
  await new Promise(setImmediate);
  const raw = heap() - base, t0 = Date.now(); let delta = raw;
  while (delta >= STEP_STOP && Date.now() - t0 < SETTLE_DEADLINE_MS) { await sleep(25); delta = heap() - base; }
  return { raw, delta, settleMs: Date.now() - t0 };
};
```

Se aplica en los 3 sitios que miden retención: el bucle corto, el largo y `Bash`.

**Por qué no oculta fallos:**

- Los límites no cambian: 8 MiB por paso y 8 MiB agregados.
- Se conservan `raw`, `delta` y `settleMs` en la evidencia, así que el transitorio queda visible.
- Una caché real no baja, así que falla al agotar los 2 s. El control medido (2 s estables a 10,13 MiB) lo respalda.
- Añade dos oráculos: `v8.queryObjects(matcher.Minimatch, { format: 'count' })` debe llegar a 0, con sondeo, y un **control positivo obligatorio** con el `mm.minimatch` cacheado, que debe dar ≥ 8 MiB.

**Avisos:**

- `v8.queryObjects` es experimental en Node 24 y emite una advertencia por stderr.
- Con esta corrección sola, la prueba sigue pasando con el `longPattern(4095)` truncado.

**Alternativa que no recomiendo:** ejecutar la fase con `--no-concurrent-recompilation`. Es una sola línea y dio 0/3 con `--no-maglev`, pero mide con flags distintos a los de producción y no probé Maglev activo.

---

## 7. Probes pendientes

**Diferidos por la reserva del lock, no omitidos.** No se han ejecutado. Ya están en mi scratch de la VM, sin cambiar nada del padre ni de los checkouts limpios.

Prefijo común:
```sh
S=/opt/cnc-guard/evidence/claude-uncached-recheck-20261105
IMG=sha256:a64bff21e24c1ede57a353fb825bcea91b1d35cba431554172f853d97081a993
BASE=sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5
```

| Fase | Comando | Duración | Resultado que valida la propuesta |
|---|---|---|---|
| `i`, ya dio rc 75 | `bash $S/mine/remote.sh i $BASE /mine/callers.cjs` | < 10 s | Lista los llamadores y `try/catch` de los 5 consumidores, y las importaciones de `just-bash` |
| `j` | `bash $S/mine/remote.sh j $IMG /mine/driver3.cjs /mine/plan-j.json j` | ~70 s | `j-d*` (4) y `j-m*` (3) con rc 0, con `raw` alto y `delta` bajo en algún paso. **`j-mut` debe fallar** con `long-pattern retention`, ya que enruta las exclusiones por la caché. `control.delta` ≥ 8 MiB |
| `k1` | `bash $S/mine/remote.sh k1 $IMG /mine/n1.cjs` | ~5 s | Confirma o refuta las filas `sentinel-*` de la sección 4. Estas filas no se han medido |
| `k2` | `bash $S/mine/remote.sh k2 $IMG /mine/n1-widened.cjs` | ~5 s | Todas las filas `char-`, `depth-`, `rewrite-`, `sentinel-` y `empties-pos-exclude` lanzan el error de truncado. Los controles siguen en `false` o `true` |

**Sin estos probes, no deben darse por probadas ni la corrección de T1 ni la de N1-R.**

También falta ejecutar la prueba real corregida en el padre, varias veces con la misma imagen, para fijar la repetibilidad. Una sola ejecución verde no vale, como ya demostró run03.

---

## 8. Ejecución y límites

**Fases en la VM:** `a`, `n1`, `b`, `c`, `d`, `e`, `f`, `g` y `h` terminaron con rc 0. `i` dio rc 75 (contención, sin ejecutarse). Todas con `flock -E 75 -w 30` sobre `remote-heavy.lock`, `timeout 140`, 1 CPU, 384 MiB con swap igual, heap de 256 MiB, 64 PIDs, tmpfs de 64 MiB, core 0, sin red, solo lectura, `cap-drop ALL`, `no-new-privileges` y `--pull never`.

**Error de mi arnés:** en la fase `c`, 7 ejecuciones dieron `ENOSPC` por acumular fixtures en el tmpfs de 64 MiB. Son fallos de mi probe, no se cuentan en ninguna tasa y los corregí limpiando entre procesos.

**Coordinación:** mis fases compitieron por el lock con la regresión del padre mientras se aclaraba la causa. Atendí la petición de ceder el turno: no he lanzado fases nuevas desde ese aviso.

**No hice:** arrancar servicios, builds, pulls, escaneos, navegador, SMB, tráfico a endpoints de aplicación, hostiles nativos u OOM. No toqué el padre, la raíz, ni los checkouts y fixtures limpios. Al leerlo, `qa-a098a86` seguía sin cambios (`git status` vacío). No quedan contenedores míos.

**Salidas:**

- VM: `/opt/cnc-guard/evidence/claude-uncached-recheck-20261105/` (`mine/` y `out/`), con un snapshot de 35 MB en `out/e-snap.heapsnapshot`. Se puede borrar cuando ya no haga falta.
- Copia local: `/tmp/claude-1000/-home-tears--t3-worktrees-B-taldea-integration-complete-project-20261103/ccc9f57b-c221-4fd5-ad8a-334387be7abc/scratchpad/evidence/`

---

## 9. Pendiente para el padre

| Asunto | Quién |
|---|---|
| Decidir N1-R: corregir con la comparación (recomendado), rechazar `!` con llaves, o declararlo. Si cambia el adaptador, hay que reconstruir y reescanear | Coordinador |
| Dar turno a los probes `i`, `j`, `k1` y `k2` | Raíz |
| Aplicar T1 tras validar `j`, y cambiar `longPattern(4095)` si se adopta N1-R | Padre |
| Corregir `MM11_MIGRATION:290-292` y actualizar `:324-333` con esta causa, una vez validada | Padre |
| Kibana y Elasticsearch en ejecución, y presión de memoria real | Pendiente, fuera de este alcance |
