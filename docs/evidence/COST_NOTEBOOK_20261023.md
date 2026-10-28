# Notebook económico de compañía: ejecución y límites

Fecha de ejecución: **23/10/2026, 17:22:54 UTC**. Base verificada:
`review/pending-20261023`, HEAD `55cfd63d71c848acbd7647eab7b69bec768b646d`.

Entregable: [02_business_costs_evidence.ipynb](../../notebooks/02_business_costs_evidence.ipynb),
**ejecutado de arriba abajo**, con 24 celdas, 10 de código numeradas 1–10,
cero errores y dos figuras PNG embebidas. Es un complemento para fase 2 y la
defensa; conserva la función de `02_training_TEMPLATE.ipynb` y no la sustituye.

## Resultado que se puede defender

La matriz del ejercicio es FN 5.000 €, FP 200 €, TP 300 €, TN 0 €:

`C = 5.000·FN + 200·FP + 300·TP = 300·P + 4.700·FN + 200·FP`.

Pasar un FN a TP ahorra 4.700 €. El equilibrio marginal es 23,5 FP adicionales;
23 dejan 100 € de ahorro y 24 añaden 100 € de gasto. La razón bruta 25 omite el
coste del TP. La figura 1 representa este escenario analítico hipotético.

La figura 2 descompone costes de políticas ya archivadas sobre **la misma cohorte
de desarrollo: 5.600 registros únicos / 190 positivos**, una vez por política.

| Política | TP | FN | FP | TN | Coste del ejercicio (€) | €/1.000 registros |
|---|---:|---:|---:|---:|---:|---:|
| RF A: corte económico inner archivado | 168 | 22 | 95 | 5.315 | 179.400 | 32.035,71 |
| RF B: fijo 0,15 | 168 | 22 | 63 | 5.347 | 173.000 | 30.892,86 |
| RF C: fijo 0,70 | 136 | 54 | 0 | 5.410 | 310.800 | 55.500,00 |
| always0: ninguna alerta | 0 | 190 | 0 | 5.410 | 950.000 | 169.642,86 |
| always1: alertar siempre | 190 | 0 | 5.410 | 0 | 1.139.000 | 203.392,86 |

La diferencia RF B frente a `always0` es **777.000 € hipotéticos (81,79 %)**.
No se anualiza, no se declara ahorro industrial y no se elige un modelo o corte
por el mínimo outer. La precision de `always0` se muestra como no definida;
el resumen de origen usa la convención numérica cero.

## Fuentes y diseño

- Matriz docente según el cuerpo del foro aportado por el usuario, atribuido a
  **Aitor Aretxaga Agirre, 22/10/2026, 18:52**, sin zona horaria indicada.
  Copia local: `outputs/academic-inputs-20261023/forum-costs.txt`, SHA-256
  `f292e1ff07785552ace80eaefaf0b7b2fd25ecfcb94aa45886c73affdbbaca32`.
  Se leyó la transcripción autorizada para contrastar los cuatro costes; el
  notebook no depende de que esa copia local esté disponible. No se consultó
  Moodle. Son parámetros oficiales del ejercicio según esa copia, sin auditoría
  de las finanzas reales que afirma el mensaje.
- Entradas computacionales: JSON y ZIP versionados de `docs/evidence/CG34_20261023/`.
  El notebook fija y verifica SHA-256 completos de `business-costs.json`,
  `business-summary.json`, `business-evidence.zip`, `business-archive.json`,
  `business-seal.json` y `manifest.json`. Los hashes quedan visibles en una tabla.
- Dentro del ZIP solo se consumen `index.json`, `analysis/business-summary.json`
  y los tres CSV `analysis/{rf_reference,always0,always1}-outer.csv`; se verifican
  CRC y hashes de esos miembros. No se extrae ni ejecuta código del archivo.
- El manifiesto permite contrastar train y las particiones. Los tres held-out
  outer son disjuntos: 1.867/63, 1.867/64 y 1.866/63 filas/positivos. Cubren train
  exactamente una vez. Cada outer-train tiene tres folds inner. Sus tamaños OOF
  son 3.733, 3.733 y 3.734; estos conjuntos se solapan y no se suman.
- A conserva los cortes inner archivados `0.1751190476190476`,
  `0.15759879606653798`, `0.07041666666666667`, con recall inner mínimo 0,76.
  No se recalculan cortes ni curvas outer. Los empates archivados se resuelven
  por coste, menos FN y corte más alto. B/C mantienen 0,15/0,70.
- El sello económico es anterior al cálculo suplementario (09:43:34 UTC del
  23/10), pero declara conocidos los resultados primarios. Es un escenario
  posterior al experimento original, no un preregistro prospectivo de este.

## Entorno y comandos ejecutados

Todo el entorno, las cachés, los logs y las exportaciones de esta tarea están en
`D:/github/_local/t2-review-20261023/economic-notebook/`.
No se instalaron paquetes en el intérprete padre ni se modificaron locks.

Se creó un venv propio con el intérprete padre autorizado y se instalaron allí
`nbformat nbclient ipykernel nbconvert matplotlib`. Las versiones efectivas son:

| Componente | Versión |
|---|---|
| Python | 3.11.9 |
| nbformat / nbclient | 5.11.1 / 0.11.0 |
| ipykernel / jupyter-client | 7.4.0 / 8.10.0 |
| nbconvert | 7.17.2 |
| Matplotlib / NumPy | 3.11.2 / 2.4.6 |
| IPython / Pillow | 9.17.1 / 13.0.0 |

Comando de ejecución final, en PowerShell **sin perfil** (`login=false`):

```powershell
$work = 'D:/github/_local/t2-review-20261023/economic-notebook'
$py = Join-Path $work 'venv/Scripts/python.exe'
& $py (Join-Path $work 'execute_notebook.py') *> (Join-Path $work 'execution.log')
```

El ejecutor usa `nbformat` y `NotebookClient.execute()`, con `allow_errors=False`,
timeout de 180 s y directorio de trabajo `notebooks/`. Declara un kernelspec
privado dentro de `$work/kernels`, vinculado al Python del venv; no registra
kernels de usuario. Configura en D: `TEMP`, `TMP`, `MPLCONFIGDIR`, `IPYTHONDIR`,
`JUPYTER_DATA_DIR`, `JUPYTER_RUNTIME_DIR` y `COST_NOTEBOOK_OUTPUT_DIR`. Exige
CurveZMQ en el transporte temporal del kernel y lo cierra explícitamente al
terminar. El proceso final devolvió **exit code 0**, sin avisos en `execution.log`.
La ejecución de las celdas duró **2,046 s**, sin contar exportación y revisión.

El código auxiliar de esta sesión queda en `$work/build_notebook.py` y
`$work/execute_notebook.py`; sus logs, versiones completas y resultado están en
`install.log`, `packages.txt`, `execution.log` y `execution-report.json`.
Son auxiliares locales, no nuevas dependencias del repositorio.

En otra máquina, abrir el notebook desde el repositorio con un kernel que tenga
las dependencias indicadas y ejecutar todas las celdas. `ROOT` se deriva del
directorio actual; el notebook no contiene rutas D: ni necesita el entorno
padre. `COST_NOTEBOOK_OUTPUT_DIR` es opcional: al definirlo, copia los dos PNG
a ese directorio; sin él mantiene únicamente las figuras embebidas. Las celdas
no instalan paquetes, no descargan datos y no necesitan modelos ni credenciales.

## Validación ejecutada y revisión visual

- `nbformat.validate()` antes y después de ejecutar; secuencia de ejecuciones
  exactamente 1–10, cero salidas de tipo `error`, dos salidas `image/png`.
- Reconciliación por evento, cuatro celdas de confusión, fórmula con P fijo y
  resumen archivado. Comparación exacta de identificadores, etiquetas y fold
  entre las tres fuentes; comprobación de pertenencia a train y de separación
  fit/held tanto outer como inner. Son comprobaciones offline, no tests del app.
- Identidad byte a byte entre cada PNG exportado y su correspondiente salida
  nativa embebida; verificación de decodificación PNG con Pillow.
- Exportación con `nbconvert.HTMLExporter` de **las celdas ejecutadas**, con
  código y outputs, a `$work/html/02_business_costs_evidence.html`. Sus dos PNG
  auxiliares están en esa misma carpeta: conservar la carpeta completa al mover
  el HTML. No requiere scripts remotos.
- Inspección real de ambos PNG a resolución nativa y en escala de grises:
  títulos, signos, unidades, valores, etiquetas y tramas legibles; sin recortes
  ni anotaciones sobre el texto. Las tramas y etiquetas distinguen las partidas
  sin depender solo del color.
- Inspección con `html_preview` del HTML completo a 1.100 px y de sus secciones
  de lectura a 1.100/1.000 px; revisión adicional de políticas a 728 px. Se
  verificaron resumen, atribución, matriz, tabla de folds, dos figuras, tabla
  económica y límites. Se corrigieron una anotación de figura, el formato del
  umbral teórico y la partición visual de cifras en tablas estrechas. Las tablas
  conservan números completos y permiten desplazamiento horizontal. Para leer
  etiquetas de figuras en un visor estrecho se indica ampliar el PNG (diseño
  de lectura a unos 960 px). Las previsualizaciones no emitieron errores de consola.
- `git diff --exit-code` sobre los dos notebooks originales: sin diferencias.
  No se ejecutaron ni se presentan como repetidos los tests generales del app.

## Huellas de las salidas finales

| Archivo | Tamaño / dimensión | SHA-256 |
|---|---|---|
| `notebooks/02_business_costs_evidence.ipynb` | 267.101 bytes | `ff221989bfc0cd1fe2173aa08960836487282210f4cfded1356451ae3023277c` |
| `$work/figures/01_marginal_hypothetical.png` | 1.547 × 797 px | `1af2d4a0d5fc0db4d39ca9729d39f354086a8c9654d30b8e6d931c9633bce70f` |
| `$work/figures/02_archived_policy_costs.png` | 1.547 × 827 px | `bcf2f9c813b4bed279a366e4004998e8f53dcce5c0038900b174022a5bfd1e9e` |

El control previo al commit detectó CRLF en el archivo guardado por Windows. Se normalizó únicamente su serialización a UTF-8/LF: los objetos JSON antes y después son iguales, incluidas las diez celdas ejecutadas y sus salidas. Se volvió a validar con nbformat. El log de ejecución conserva el hash previo `9ab495b1552513d3df18537920dd355914eb829e9357f2e75bfca2f6e544aabc`; la tabla anterior recoge el archivo entregado. [Recibo de normalización](NOTEBOOK_SERIALIZATION_20261023.json).

Los hashes del notebook cambiarán al reejecutar por los tiempos guardados de
las celdas; los hashes de entradas siguen fijados y los resultados aritméticos
deben concordar. Los dos PNG quedan también dentro del `.ipynb`, por lo que
este conserva sus figuras al copiarlo sin la carpeta temporal.

## Límites de aceptación

Se preservan train 5.600/190, validación 1.200 reutilizada y test 1.200 excluido.
No se han abierto datos ni etiquetas del test, calculado inferencias, hecho fit,
calibrado ni ajustado umbrales. Los JSON y sus metadatos no equivalen a una nueva
auditoría de todo el experimento primario.

El valor teórico `200/(5.000−300+200) = 0,040816…` exige probabilidad calibrada,
acciones y costes completos. No es un umbral RF aprobado. Se mantiene el
contrato 0,15/0,70; `risk_threshold` para F2 es un criterio distinto. Precision
y recall se presentan como diagnóstico de desarrollo, sin promoción de modelo
por mínimo outer ni extrapolación financiera.

Solo se añaden el notebook y este documento. No se modifica la presentación;
quedan preparados sus gráficos y notas para incorporarlos. La integración en
diapositivas y la aceptación docente pertenecen al trabajo del agente padre.
No hubo servicios de aplicación, accesos OT/SMB, cambios externos, commit,
push, merge, PR, comentarios ni cierres desde esta tarea.
