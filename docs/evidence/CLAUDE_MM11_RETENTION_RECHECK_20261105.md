# Recomprobación focal: retención MM11 (M1) y B1–B5

**Fecha:** 2026-11-05 · **Revisor:** Claude (sub-agente de revisión, solo lectura)
**Commit revisado:** `080b6f9ec41b5f7aacd05fcaef6e9aec0f2ab057` (checkout aislado, limpio al terminar)
**Diff:** `0f60b3e..080b6f9`. Los ficheros bajo `deploy/` son idénticos en `6e54f11` y en `080b6f9`.
**Informe de origen:** `docs/evidence/CLAUDE_KIBANA_MM11_DEL_REVIEW_20261105.md` (revisaba `0dafc5d`)

Este informe no concede aceptación, excepciones ni aprobación de runtime, y no sustituye ninguna aprobación protegida de GitHub. Los recuentos autoritativos siguen siendo los de la última CI real `6d67bc2`: NiFi 59 tuplas (63 registros) y Kibana 2. El fixture de componentes no es una imagen de servicio y no lo califico de verde.

---

## 1. Veredicto

**M1 queda corregido solo en parte. Sigue abierto con severidad media, y B1–B5 quedan resueltos.**

- **Lo que arregla:** los patrones cortos del informe original pasan de 35–40 MiB a unos 0,35 MiB por patrón. Es una mejora real, de unas 100 veces.
- **Lo que no arregla:** `braceExpandMax` limita el número de alternativas, no su longitud. Con la misma cota de 1024, un patrón de 4 KB retiene **unos 41 MiB**. Es el mismo orden de magnitud que M1, por las mismas rutas y en la misma caché de 256 entradas.
- **Consecuencia para la decisión:** el padre rechazó aceptar este riesgo por licencia, así que M1 no puede darse por cerrado con este commit. Hace falta otra corrección o una decisión nueva y explícita del coordinador.
- **Lo demás se sostiene:** bytes oficiales, 8 ubicaciones, 6 forks, 105 ficheros pinned, dominios ordinarios y fidelidad de la evidencia. La evidencia no afirma una cota general, así que no es falsa. Tampoco prueba la forma de patrón que sigue abierta.

| Asunto | Estado | Severidad actual |
|---|---|---|
| M1, patrones cortos | Corregido | — |
| **M1-R, patrones de 1–4 KB** | **Abierto** | **Media** |
| N1, patrón negado con más de 1024 alternativas | Nuevo, no declarado | Baja |
| B1 `TypeError` | Documentado, con un matiz | Informativa |
| B2 clases semánticas | Declaradas y con controles | — |
| B3 `del.sync` | Aceptado por el coordinador y documentado | — |
| B4 textos obsoletos | Corregidos | — |
| B5 `active_source_sha256` | Corregido | — |

No hay hallazgos críticos ni altos.

---

## 2. Hallazgo medio: M1-R, la retención reaparece con patrones de 1–4 KB

### Mecanismo

1. `minimatch()` guarda cada objeto compilado en una caché de 256 entradas (`minimatch/dist/commonjs/index.js:22-38`). Son bytes oficiales, sin cambios.
2. `braceExpand` solo transmite `max` (`index.js:101`). El otro tope, `EXPANSION_MAX_LENGTH = 4.000.000` caracteres, no se puede ajustar desde las opciones de Minimatch.
3. El objeto compilado conserva `globSet`, `globParts` y `set`. Con `{1..1024}/a/a/a/…`, cada una de las 1024 filas tiene cientos o miles de porciones, y dos de esas estructuras son arrays por fila.

Por eso `braceExpandMax: 1024` acota las filas, pero no las porciones por fila. Por lectura de código, a partir de unos 3,9 KB manda el tope de 4 MB y la cota 1024 deja de influir. En ese tramo el resultado debería ser muy parecido al de antes de la corrección. No medí la variante sin cota con esta forma.

### Medido

Bytes retenidos con `gc()` doble, sobre las funciones reales con `braceExpandMax: 1024` ya aplicado y la salida preparada del padre. Paré la serie al superar 96 MiB acumulados, como se pidió.

| Ruta | Longitud del patrón | Retenido | Tiempo |
|---|---|---|---|
| `matchesExcludePatterns` | 10 (control corto) | 0,35 MiB | 62 ms |
| `matchesExcludePatterns` | 255 | 2,63 MiB | 75 ms |
| `matchesExcludePatterns` | 1.023 | 9,57 MiB | 198 ms |
| `resolveInputToConcreteFields` | 1.023 (máximo por campo) | 9,62 MiB | 230 ms |
| `matchesExcludePatterns` | 4.095 | 41,33 MiB | 617 ms |
| `matchesExcludePatterns` | 4.095 (segundo patrón) | 40,39 MiB | 576 ms |
| `Bash` público real, CJS, fixture físico | 1.024 | 10,44 MiB | 747 ms |
| `Bash` público real, CJS, fixture físico | 4.096 | 40,41 MiB | 2.198 ms |
| **Control:** Fleet, `new Minimatch` directo, fuera de la caché | 4.095 | **0 MiB** | 35 ms |
| **Control:** MM10.2.4 de la base | 1.023 | **0 MiB** | 1.274 ms |

Lectura de los datos:

- La retención crece de forma lineal: unos 10 bytes por fila y carácter (41 MiB / (1024 × 4095)).
- La causa es la caché, no la expansión: la misma cadena por Fleet no retiene nada.
- Ambos totales se ven en una sola llamada, sin OOM. El proceso nunca se acercó al límite de 256 MiB.

### Impacto extrapolado, no ejecutado

- **Unos 29 patrones de 4 KB (116 KB de texto)** bastarían para llegar a los 1.024 MiB de heap de `docker-compose.yml`, aunque la línea base de Kibana fuera cero. M1 estimaba también 29 patrones, pero de solo 10 caracteres.
- **Por la ruta de Agent Builder**, con 10 campos de 1.024 caracteres, serían unos 96 MiB por llamada.
- **Con la caché llena de patrones cortos**, serían unos 77 MiB (0,30 MiB × 256). Dejé escrito `cachefull.cjs`, pero **no lo ejecuté** tras activarse la parada.

### Alcanzabilidad

Sin cambios respecto a M1, y estática:

- **Puertas:** las mismas. No hay imagen ni servicio hoy; Agent Builder exige licencia `enterprise`; el puerto solo escucha en loopback; Significant Events necesita sus privilegios y funciones.
- **Matiz sobre M1 (Significant Events):** la query llega con `MAX_TEXT_LENGTH`, pero una petición GET queda sujeta al límite de cabeceras HTTP. No encontré ajuste de tamaño de cabecera en `@kbn/server-http-tools` ni en `@kbn/core-http-server-internal`, y `config/node.options` no lo cambia. Si aplica el valor por defecto de Node (16 KiB, conocimiento general, no verificado aquí), caben unos 3–4 patrones por petición.
- **Por qué ese matiz no lo frena:** la caché persiste entre peticiones. Además, `PUT` de ajustes acepta el mismo campo por cuerpo, y `classify_streams` lo consume si se guarda. No ejecuté ninguna ruta HTTP ni arranqué Kibana.
- **`just-bash`:** `ls` retiene por la misma vía, confirmada en físico.

### Por qué no es alta

Igual que en M1: afecta a disponibilidad y no a datos, exige una función o licencia que el despliegue por defecto no activa, y solo se expone en loopback.

### Por qué la prueba del padre no lo detecta

`test-mm11-migration.cjs:236-246` y `:279` solo miden patrones cortos: `{1..N}` y `{1..N}/*`. Bastaría con añadir esta forma: el primer patrón de 1.023 caracteres (9,57 MiB) ya superaría la parada de 8 MiB de la línea 241.

### Opciones (decisión del coordinador)

1. **Recomendada: sacar los consumidores de la caché.** Sustituir `minimatch(x, p, opts)` por `new Minimatch(p, opts).match(x)`, conservando `braceExpandMax: 1024`.
   - Fleet ya lo hace y midió 0 MiB. Los 90 ficheros oficiales no cambian.
   - Por lectura de `index.js:9-16`, `minimatch()` solo añade la validación y el atajo de comentarios, que el constructor también trata. No lo he probado en los 7 sitios restantes.
   - Coste: recompila en cada llamada. Conviene compilar antes del bucle donde sea posible. Los 3 bundles necesitan además tocar su `import`/`require`.
2. **Tope de longitud en cada consumidor.** Rechazar o no coincidir por encima de N caracteres, y bajar la cota de filas. Para unos 64 MiB con la caché llena harían falta unas 25.000 filas × caracteres (por ejemplo, 64 filas y 384 caracteres; extrapolado). Reduce mucho el dominio y no lo recomiendo como única medida.
3. **Aceptar explícitamente el residuo.** Sería una decisión nueva, porque contradice la del padre.

En los casos 1 y 2, añadir la forma `{1..1024}/a/a/…` con 1.023 y 4.095 caracteres a la prueba de retención, y cambiar `INTEGRATION_CANDIDATES` para que no se lea M1 como cerrado.

### Reproducción

Salidas en `/home/tears/.cache/cnc-claude-mm11-retention-recheck-20261105/out/`:

```sh
S=/home/tears/.cache/cnc-claude-mm11-retention-recheck-20261105
I=sha256:2348c612a3096532bb96ed81909dd7200532aacad2dc55f7170ac64f90ca39ef
$S/run.sh $I longrow --expose-gc /mine/longrow.cjs   # tabla por funciones reales; para en 96 MiB
$S/run.sh $I oneshot --expose-gc /mine/oneshot.cjs   # Fleet y Bash físico
```

---

## 3. Hallazgo bajo nuevo

### N1. Un patrón negado por encima de la cota invierte el resultado

**Medido** sobre `isPathAllowed` real:

| Llamada | Candidato | MM10 |
|---|---|---|
| `allowed('1500', [{ path: '!{1..2000}' }])` | **`true`** | `false` |
| `allowed('500', [{ path: '!{1..2000}' }])` (dentro de la cota) | `false` | no medido |

La alternativa 1500 se descarta, deja de coincidir, y la negación convierte eso en un acierto.

**Por qué importa:** `MM11_MIGRATION_20261105.md:231-234` dice que el presupuesto puede excluir una coincidencia válida o impedir que coincida una exclusión. No dice que un patrón negado **pueda empezar a permitir**. En una lista de permitidos, eso es fallar abierto.

**Alcance:**

- Exige una entrada `!` con más de 1024 alternativas.
- Las 9 rutas por defecto, verificadas contra `telemetry/configuration.js`, no usan `!` ni llaves.
- No leí la configuración remota de la lista.
- Fleet usa `nonegate`, así que no le afecta.
- Por el código, `isTaskTypeExcluded` y `matchesExcludePatterns` se comportarían igual; solo medí `isPathAllowed`.

**Corrección:** una frase en el documento. La opción de rechazar `!` con llaves en `isPathAllowed` queda a criterio del coordinador.

---

## 4. Estado de B1–B5

| ID | Resultado | Comprobación |
|---|---|---|
| **B1** | Documentado en `MM11_MIGRATION:253`. `{1..99999}*` y `{a,b}`×14 seguido de `*` ya no lanzan: devuelven `false` | Medido. **Matiz:** el texto habla de entradas «very large», pero `{1..1024}` + 64 `x` + `*` tiene **74 caracteres** y lanza `pattern is too long` en `matchesExcludePatterns`, `isTaskTypeExcluded`, `isPathAllowed` y `resolveInputToConcreteFields`. Falla cerrado. Fleet devuelve `[]`. Lo «very large» es la expansión, no la entrada. Basta con precisar la frase |
| **B2** | Las clases 15/3/1 están declaradas (`MM11_MIGRATION:5-6,249`) y hay un control representativo por clase (`test-mm11-migration.cjs:164-169`) | Repetido, pasa. Los controles fijan una muestra, no los 19 casos, y el documento lo dice así |
| **B3** | `DEL_MIGRATION:189` lo describe y lo declara aceptado por el coordinador. Coincide con los registros originales | Lectura. Los llamadores reales de plugin siguen sin probar, como el documento reconoce |
| **B4** | Corregidos `DEL_MIGRATION:5,34,93,183`, `kibana.Dockerfile:36` y el comentario de `test-glob-migration.js`. La búsqueda no encuentra más texto obsoleto | **Medido:** `globSync('**', …)` devuelve `['.', 'a', 'a/b']` tanto en Glob 10.5.0 (base) como en Glob 14.0.3 (fixture), así que el comentario nuevo es cierto. `test-del-migration.cjs:44` comprueba MM 11.0.4 |
| **B5** | `MM11_MIGRATION` y `DEL_MIGRATION` están en `active_source_sha256` | 61 entradas recalculadas, sin discrepancias |

---

## 5. Lo verificado

| Requisito | Resultado | Método |
|---|---|---|
| Fase `consumers` | **Reproducida** con `rc=0`. Solo cambia `retainedBytes` (7.233.840 frente a 7.239.936, ruido de GC) | Mi checkout, imagen `2348c6…`, artefactos del padre |
| 8 ubicaciones con cota | **Confirmado** | Diff byte a byte frente a la base: solo se añade la opción (y la adaptación de Fleet). Hashes de entrada correctos. Comprobé las importaciones de los 3 bundles y las llamadas de los 5 `@kbn` |
| 6 forks honestos | **Confirmado** | Solo cambian `version`, `dependencies` y `cncGuardMinimatchMigration`; versión `+cncguard.mm11.2` |
| 90 oficiales y 105 de salida | **Confirmado** | Recalculados, sin discrepancias ni ficheros de más o de menos |
| Sin compilador viejo, `fakeRegExp` ni excepciones | **Confirmado** | Diff; ningún fichero de política de escáner o workflow cambiado |
| Patrón rojo | **Coherente** | `red.stderr` muestra `real Fleet expansion budget missing`, con hash registrado. Ver el apunte de abajo |
| Prueba del padre | **Confirmado:** 223 artefactos y 19 fuentes, todos con hash correcto | Recalculados. Las 19 fuentes coinciden con `080b6f9` |
| Límite exacto | **Medido:** la alternativa 1024 coincide y la 1025 no, tanto en rango como en lista con comas | Función real |
| Dominios ordinarios | **Sin rotura:** 36.000/216, 9.000/0 y 252/0 repetidos; 5 patrones de llaves ordinarios iguales que en MM10; 7 casos en cada una de las 3 variantes de `Bash` | Reproducción y sonda propia |
| 9 rutas de seguridad del test | **Iguales** a las de `configuration.js` | Lectura en la imagen |
| Guarda final | **Pasa en modo humo** sobre `/probe/prepared`, con 6 declaraciones | **No es una imagen final.** El guard sigue sin haber corrido sobre una imagen real |
| Fixture de componentes | **Confirmado:** 451 ficheros iguales a `SHA256.json`, UID 1000, Glob 14.0.3, Rimraf 6.1.4, MM raíz 10.2.4 | Recalculado dentro de la imagen. La comparación con los tarballs oficiales es del padre (`base-pull`, `component-build`); no la repetí |
| Fidelidad de registros | **Confirmado:** `image_built=false`, `runtime_approved=false`, `services_started=false`, `new_scan_executed=false`, `human_review=pending`; el proof histórico sigue apuntando a `cnc-mm11-parent-20261105-02`; manifiesto con 488 entradas sin discrepancias | Recalculado. Los recuentos de CI son los registrados, no los verifiqué en GitHub |

**Apunte sobre el rojo (informativo):** la pila de `red.stderr` apunta a la línea 172 del test, y en el test final ese código está en la 189. El log corresponde a una revisión anterior del test y no enlaza con el hash de esa revisión. No cambia la conclusión, pero conviene no presentarlo como una ejecución de la fuente final.

**Lo que sí mejoró en CPU:** el mismo patrón de 1.023 caracteres tarda 198 ms frente a 1.274 ms en MM10. No propongo volver atrás.

---

## 6. Límites de esta revisión

- **Sin ejecutar:** imagen de servicio, escaneo, Kibana, Elasticsearch, navegador, rutas HTTP ni OOM. No hice pull ni build, no usé red ni la imagen `34a89…`, ni Node 26. Tampoco ejecuté `npm ci` ni `prepare`: reutilicé los artefactos del padre con hashes recalculados.
- **Sin nativos antiguos ni borrado de raíces.** Solo un patrón JavaScript en MM10.
- **Serie detenida a propósito:** parada de 96 MiB en `longrow`. Después solo hice 2 patrones más en `Bash` y controles puntuales. El peor caso puede ser mayor: `{1..1024}/a/a…` es la forma peor que encontré, no un máximo demostrado.
- **`Bash` físico solo en CJS.** El mecanismo es común y los otros dos bundles tienen la misma llamada, pero no medí su retención larga.
- **Extrapolaciones:** todas las cifras de agotamiento y de caché llena están extrapoladas, y así se indican.

**Recursos y estado:** bloqueo común con espera de 30 s, fases de 140 s como máximo, 1 CPU, contenedor de 384 MiB con swap igual, heap de 256 MiB, 64 PIDs, tmpfs de 64 MiB, core 0, sin red, solo lectura, UID 1000, `cap-drop ALL`, `no-new-privileges`. Solo las imágenes `2348c6…` y `46b0a3…` con `--pull never`. Las 9 fases terminaron con `rc=0`, sin contención ni contenedores residuales. El checkout sigue limpio en `080b6f9`, y no toqué el padre.

**Salidas:** `/home/tears/.cache/cnc-claude-mm11-retention-recheck-20261105/` (`run.sh`, `probes/`, `out/`).

---

## 7. Pendiente

| Asunto | Quién |
|---|---|
| **Decidir M1-R:** corregir (opción 1 recomendada) o aceptarlo con una decisión nueva | Coordinador |
| Añadir la forma larga a la prueba de retención y actualizar `INTEGRATION_CANDIDATES` (`independent_recheck` sigue `pending`) | Padre |
| Declarar N1 y precisar la frase de B1 | Padre |
| Imagen de servicio Kibana/NiFi y escaneos frescos | Pendiente |
| NarClassLoader, CG32, SMB, modelo y revisión humana | Pendiente; nada de esto se infiere de este informe |
