# CG10: conciliación de precisión CSV, métricas y costes

Registro del 22/10/2026 sobre `main`
`3b79c927c909bb0c87fe3f344c2b4bd152f31c61`, árbol
`2e7f81c7a09839378e44cccca215b84d516ded8d`. Repositorio educativo, no MKDL.
Responde al [pendiente PM de #10](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/10#issuecomment-6342069707).
#10/#11 permanecen abiertos hasta revisión del arreglo y merge. Este registro
acredita comprobaciones locales; no acredita revisión independiente ni merge.

## Causa, alcance y propagación

`scripts/report_thresholds.py` leía `validation.csv` con el parser predeterminado
de pandas. Para el positivo `source_row_index=7763`, el token
`0.19082281465428477` se convertía en `0.1908228146542847`, inferior al umbral
original `0.19082281465428477`. La comparación `>=` perdía un TP y añadía un FN.
La corrección usa `float_precision="round_trip"`, como el
[diagnóstico CG24](CG24_2026-10-21.md#corrección-de-precisión-csv-tras-revisión-independiente).
No cambia el umbral ni añade tolerancias.

El error afectaba a precision/recall/F1/F2, nueve escenarios de coste F2 y el
bootstrap condicional. Las otras dos políticas, ROC AUC y AP no cambian en estas
entradas. Además, la figura copiaba la matriz del informe del experimento,
mientras el JSON publicaba la recalculada: ahora ambos usan `policies`.

Se actualizan [JSON](CG10_results.json), [figura](CG10_diagnostics.png),
[informe activo](CG10.md), seguimiento [CG11](CG11.md) y la referencia en
[memoria](../memoria/README.md). Sus hashes actuales se mantienen en
[manifest.json](../memoria/manifest.json). Los conteos de las tablas de CG24,
memoria y rúbrica ya eran TP32/FN9/FP9/TN1150 y no necesitan cambiar sus valores.

## Entradas conservadas y procedimiento acotado

Se reutilizan los archivos de `cg24-evidence-1045/outputs/cg24-rf/`, identificados
por [CG24_current_state_types.json](CG24_current_state_types.json). Solo se copian
`validation.csv` y `report.json` a un directorio nuevo de reproducción; no se
carga ningún pickle. Se verifican los hashes antes y después de leerlos:

| Entrada | SHA-256 |
| --- | --- |
| `validation.csv` | `a63c3b54fb58fd39ddf34084b9a8898e5f6b400dc4c692fb7d1174d7f94bfd1b` |
| `report.json` | `14ce085fb4af2507b9014466aa60c6c16ab422933a34a7b11da1f35690ad7902` |

Las 1200 filas, sin índices repetidos, coinciden con la membresía de validación
guardada y no se solapan con los índices del test excluido. Son 41 positivos y
1159 negativos. Se conservan las predicciones, el umbral y los escenarios ya
definidos. No se entrena, infiere, selecciona otro umbral, recalcula score ni
bundle, ni se evalúa el test final. No hay servicios, infraestructura, ledgers
ni migración real en esta ejecución.

Para repetir únicamente el informe, preparar en un directorio nuevo
`outputs/cg08/{validation.csv,report.json}` con esos bytes y `docs/evidence/`.
Desde ese directorio, con `PYTHONPATH` apuntando al checkout corregido y el
entorno del lock, ejecutar dos veces `python -m scripts.report_thresholds`.
Comparar bytes y hashes de ambas salidas. No ejecutar `scripts.experiment_rf`
ni empaquetar modelos para obtener entradas nuevas.

El auditor local `reproduce.py` lee con `csv.DictReader` y `float`, sin pandas
ni `evaluate` para sus conteos de referencia:

```python
matrix = [[0, 0], [0, 0]]
for row in rows:
    matrix[int(row["label"])][int(float(row["rf_score"]) >= threshold)] += 1
```

Contrasta las tres matrices, precision/recall y los 27 costes con el JSON;
comprueba también igualdad de todas las métricas F2 con CG08 y de los conteos
con CG24. El [resultado independiente](CG10_PRECISION_20261022/independent-audit.json)
incluye hashes y cambios de coste. Los scripts ejecutados y logs completos
quedan en `D:/github/_local/t2-babysit-20261021/cg10-precision-20261022/`.

## Resultados activos

| Umbral / decisión | TP | FN | FP | TN |
| --- | ---: | ---: | ---: | ---: |
| AVISO, `>=0.15` | 32 | 9 | 12 | 1147 |
| CRITICA, `>=0.70` | 27 | 14 | 0 | 1159 |
| F2 original, `>=0.19082281465428477` | 32 | 9 | 9 | 1150 |

Al umbral F2, precision/recall/F1/F2 = `0.7804878048780488` (32/41).
ROC AUC = `0.9637197752477956`; AP = `0.817191481534734`.
Bootstrap condicional de recall 95%: `[0.6341463414634146, 0.9024390243902439]`,
antes `[0.6097560975609756, 0.8780487804878049]`. Se mantiene seed 42 y 2000
remuestreos sobre predicciones fijas; no corrige sesgo de selección ni de dominio.

Coste hipotético = `FP × inspección + FN × horas × 1200 €/h`. Se conservan
inspección 25/100/300 € y duración 0.5/1/4 h. Los nueve costes F2 corregidos son:

| Inspección (€) | 0.5 h (€) | 1 h (€) | 4 h (€) |
| ---: | ---: | ---: | ---: |
| 25 | 5625 | 11025 | 43425 |
| 100 | 6300 | 11700 | 44100 |
| 300 | 8100 | 13500 | 45900 |

Cada coste F2 baja exactamente `horas × 1200` respecto al JSON anterior;
los otros 18 costes se conservan. No son costes medidos ni ahorros acreditados.
La política de aula y la decisión binaria exploratoria siguen siendo distintas.

Dos ejecuciones consecutivas producen exactamente los mismos bytes:

| Salida activa | SHA-256 |
| --- | --- |
| `CG10_results.json` | `40be1d3f3e8b1bc9f9cdacb2e1a8750aac1db30a5e8861a048070e977bd9ab59` |
| `CG10_diagnostics.png` | `d4e4eb378d70b84e88f8205d2fe73ee3dd5a7e373d96eb3d52581bc2dd259654` |

## Regresión y comprobaciones ejecutadas

FedoraLinux-43, Python 3.12.15, pandas 2.2.2, NumPy 1.26.4, scikit-learn 1.5.0.
Se reutiliza el intérprete existente del entorno bloqueado; no se modifica.
Temporales, cachés y evidencia nueva están bajo la carpeta local de esta tarea,
en D:. Para Git de Linux se fijan `GIT_DIR` y `GIT_WORK_TREE` al worktree manual:
el `.git` creado por Windows contiene una ruta Windows y no se reescribe.

- [Rojo previo](CG10_PRECISION_20261022/regression-red.log): una prueba con tres
  subcasos falla, exit 1 esperado. Los subcasos usan el umbral exacto y los
  flotantes contiguos de `np.nextafter`; incluyen scores inferior/igual/superior,
  positivos y negativos. Detectan pérdida de igualdad y matriz gráfica obsoleta.
- [Verde posterior](CG10_PRECISION_20261022/regression-green.log): la misma prueba
  pasa los tres subcasos. Comprueba CSV → JSON/figura, límites sin tolerancias,
  los 27 costes y JSON idéntico entre repeticiones.
- [CG24](CG10_PRECISION_20261022/type-diagnostics.log): 12 pruebas, warnings como
  errores; [política](CG10_PRECISION_20261022/policy.log): 2 pruebas, warnings como
  errores. Total focal: 15 pruebas, sin repetir la suite ML.
- Ruff **0.17.1**, global sobre 163 archivos Python: default y
  `--select E,F,I,PLW1510`, ambos con `--ignore-noqa`; formato global: 163 archivos
  ya formateados. Sin nuevos ignores ni cambios de configuración.
- CG02, layout (solo configuración Compose, sin iniciar servicios),
  `uv lock --check --offline` y `git diff --check`: exit 0.
- `uv audit --locked --output-format json`: 57 paquetes, cero vulnerabilidades
  y cero estados adversos; conserva dos avisos de interfaz experimental de uv.
  CG25 se ejecuta al final, tras actualizar exclusivamente hashes actuales.

CG25: [exit 0](CG10_PRECISION_20261022/CG25.log), 40 criterios, 89 enlaces/anclas,
190 hashes actuales y 18 históricos. El log rojo publicado solo elimina un
espacio final emitido por unittest para satisfacer `git diff --check`; el raw
local queda intacto, SHA-256
`3d6cd1cc5f14b524eeb9f6e197282b4e7a13f01f1915f632fa6aad0a68bffde7`.

Logs y comandos: [carpeta de evidencia](CG10_PRECISION_20261022/).
La figura se ha inspeccionado visualmente: matriz 1150/9/9/32, textos legibles
y aviso de ausencia de test independiente.

## Historial conservado y límites de entrega

El [JSON de la base](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/3b79c927c909bb0c87fe3f344c2b4bd152f31c61/docs/evidence/CG10_results.json)
con TP31/FN10 queda sustituido para uso activo por el JSON de este arreglo.
La [figura anterior](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/3b79c927c909bb0c87fe3f344c2b4bd152f31c61/docs/evidence/CG10_diagnostics.png)
y el [manifiesto anterior](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/3b79c927c909bb0c87fe3f344c2b4bd152f31c61/docs/memoria/manifest.json)
siguen disponibles en el commit fijado. No se edita ningún log, snapshot histórico
ni registro sellado anterior; `historical_snapshot` del manifiesto permanece
idéntico. Se añaden evidencias nuevas y se renuevan hashes de archivos activos.

Esta corrección no aporta generalización independiente ni valida costes reales.
No altera decisiones PM ya aceptadas. La publicación será un PR borrador contra
`main`, con push normal; su revisión y merge quedan pendientes. La CI automática
puede ejecutar el workflow existente (incluye entrenamiento): no se despacha
manualmente ni se vigila. El handoff local conservará SHA/tree publicados y una
sola captura CI, separada de los checks ejecutados aquí.
