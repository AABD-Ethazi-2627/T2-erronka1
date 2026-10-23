# CG34–CG40: exploración ML ejecutada en Kalista

**Recomendación: conservar Random Forest y los niveles actuales 0,15/0,70.**
La regla preregistrada inicial elige RF en los tres outer, tanto entre los diez modelos
del núcleo como entre las 40 configuraciones supervisadas. La selección interna
sobre las 5.600 filas también elige RF como paquete fijo. En esta cohorte, RF
obtiene el menor coste primario entre las 40 configuraciones, con umbral aprendido
y con AVISO fijo. Hay alternativas más precisas, sencillas o rápidas, pero sus
intercambios de errores no justifican sustituirlo bajo el criterio inicial.
La matriz docente facilitada durante esta ejecución también mantiene RF como
especificación fija elegida en train y como menor coste entre los 40 con AVISO
fijo. Su selector nested del pool completo elige AdaBoost/RF/RF; no se atribuye
su resultado a un modelo fijo. El análisis adicional se detalla a continuación.

Es evidencia de desarrollo sobre AI4I ya explorado. No confirma superioridad
universal, capacidad temporal o adecuación industrial. El paquete de investigación
y su umbral no sustituyen el modelo servido ni una decisión PM.

## Ejecución y procedencia

- Base remota comprobada: `41cb66f0f3a967bcc4e72c6e251586898edceee9`.
  Worktree T3 aislado: `kali/ml-alternatives-kalista-study`; no cambios ajenos al iniciar.
- Código de ajuste sellado: `e644737`. Manifiesto SHA-256:
  `d881aa24d43a1f44e98956c37a4e88cacb21989a1fe0c205ed9e8d67aa72187b`.
  El archivo reproducible conserva sus fuentes originales en `sealed-code/`.
- Screening: **150/150 unidades completas**, 50 configuraciones × 3 folds.
- Auditoría: **600/600 unidades completas**, 50 configuraciones ×
  (9 ajustes inner + 3 refits outer). El núcleo de diez terminó antes de ampliar.
- Piloto CPU/CUDA: ocho unidades completas; [medidas y decisión](CG34_PILOTO_20261023.md).
- Calibración: 72 unidades completas. Finalistas por outer: RF/AdaBoost depth1,
  RF/GB depth3 y RF/CART depth5, respectivamente. No se eligieron por ranking global.
- Un refit final RF sobre las 5.600 train. Total: **831 unidades de entrenamiento**;
  los ajustes internos de calibración están incluidos en su tiempo de proceso.

Única fuente de ajuste: CSV reducido de 8.000 filas, SHA-256
`1cce2859f4833b63dbf0992868884e5deac6f79e4d74a245abbc484d34e396ce`.
Se verifica la pertenencia original 5.600/1.200/1.200 contra CG04. Train contiene
190 positivos. **No se puntúan la validación reutilizada ni el test excluido.**
La lectura íntegra para hash, duplicados y pertenencia no incorpora esas filas al ajuste.

Representación supervisada: cinco sensores, tipo y tres derivadas. `temp_diff`
es el nombre del repositorio para la diferencia en K; `power_W` incluye `2π/60`;
`wear_torque`, en min·Nm, es un proxy y no desgaste físico demostrado.
Las dos ablaciones RF/GB omiten las derivadas. Imputación, escala, codificación,
pesos, early stopping y umbral se ajustan dentro del entrenamiento correspondiente.
CatBoost usa categoría nativa. La etiqueta sirve como supervisión o filtro de normales.

## Matriz docente facilitada durante la ejecución

Fuente: texto del foro aportado por el usuario, atribuido a Aitor Aretxaga Agirre,
22/10/2026 18:52. Se toma como parámetro oficial del ejercicio. No se han verificado
cuentas industriales de ARAKAIN ni se afirma que AI4I mida ahorros industriales.
Se recibió después de terminar el análisis inicial; su
[configuración adicional](CG34_20261023/business-costs.json) y
[sello](CG34_20261023/business-seal.json) se guardaron antes del nuevo cálculo.
El preregistro original permanece intacto. No se entrenó de nuevo ni se consultó
validación o test: se reutilizan los scores guardados de inner y outer.

| Resultado | Coste docente |
|---|---:|
| FN: fallo omitido | 5.000 € |
| FP: inspección innecesaria | 200 € |
| TP: mantenimiento preventivo | 300 € |
| TN: funcionamiento sin alerta | 0 € |

`C = 5.000 FN + 200 FP + 300 TP`. Como `TP + FN = P`, minimizarlo equivale a
minimizar `4.700 FN + 200 FP`, más la constante `300 P`. Omitir el coste de TP
sobrestimaría el beneficio de elevar recall. Un fallo adicional detectado vale
4.700 € netos y compensa **23,5 FP adicionales**: con 23 compensa; con 24 deja
de compensar, manteniendo todo lo demás constante. Para cambios múltiples,
conviene elevar recall si `4.700 × ΔTP > 200 × ΔFP`. El cociente bruto FN/FP es
25, pero no es el punto marginal correcto al incluir mantenimiento preventivo.

Si el score fuese una probabilidad posterior bien calibrada y estas dos acciones
describiesen todos los costes, el umbral económico teórico sería
`200 / (5.000 − 300 + 200) = 0,040816`. No se aplica a RF sin demostrar esa
calibración ni sustituye los niveles docentes 0,15/0,70. Los umbrales empíricos
se aprenden exclusivamente en OOF inner, conservando recall ≥ 76% y desempates.

| Procedimiento/configuración | Política | TP | FN | FP | Recall | €/1.000 |
|---|---|---:|---:|---:|---:|---:|
| RF | A: nuevo coste, umbral inner | 168 | 22 | 95 | 88,42% | 32.035,71 |
| XGBoost depth3 sin pesos | A: nuevo coste, umbral inner | 173 | 17 | 165 | 91,05% | 30.339,29 |
| GB depth3 | A: nuevo coste, umbral inner | 168 | 22 | 115 | 88,42% | 32.750,00 |
| CART depth5 | A: nuevo coste, umbral inner | 167 | 23 | 94 | 87,89% | 32.839,29 |
| Selector núcleo10, RF/RF/RF | A | 168 | 22 | 95 | 88,42% | 32.035,71 |
| Selector pool40, AdaBoost/RF/RF | A | 167 | 23 | 112 | 87,89% | 33.482,14 |
| RF | B: AVISO 0,15 | 168 | 22 | 63 | 88,42% | 30.892,86 |
| XGBoost depth3 sin pesos | B: AVISO 0,15 | 165 | 25 | 48 | 86,84% | 32.875,00 |
| GB depth3 | B: AVISO 0,15 | 162 | 28 | 19 | 85,26% | 34.357,14 |
| CART depth5 | B: AVISO 0,15 | 164 | 26 | 28 | 86,32% | 33.000,00 |

RF B cuesta 173.000 € en estos 5.600 eventos; la referencia sin alertas cuesta
950.000 €. La diferencia de 777.000 € es un cálculo hipotético sobre etiquetas
sintéticas contemporáneas: no demuestra que una intervención evite una avería.
CRITICA RF cuesta 55.500 €/1.000, pero no es una política que sustituya AVISO:
los avisos entre 0,15 y 0,70 también requieren su tratamiento.

XGBoost sin pesos mejora A frente a RF A un 5,30%, pero solo un 1,79% frente a
RF B y empeora un 6,42% frente a RF B al conservar el contrato 0,15. Es un
candidato exploratorio observado en outer, no el elegido por el selector interno.
La regla aplicada sobre las 5.600 train vuelve a elegir RF, con umbral de
investigación `0.11899870801033592`; sus métricas OOF de ajuste no se presentan
como evaluación final. No se refitea ni se aplica un nuevo paquete por este añadido.

La calibración restringida ya entrenada elige sigmoid RF en 3/3 outer:
A FN24/FP67, 32.714,29 €/1.000; B FN30/FP22, 36.142,86 €/1.000. Sus finalistas
proceden de los costes iniciales, por lo que no constituye una búsqueda de
calibración completa para la nueva matriz. Tampoco respalda promoción.

Con estos costes, la unión hipotética RF+PCA(2) ahorraría 6.300 € en 5.600
eventos (3 × 4.700 − 39 × 200), un 3,64% frente a RF B. Sigue siendo diagnóstico
posterior sin verdad independiente de anomalías; no selecciona ni activa el detector.

[JSON completo](CG34_20261023/business-summary.json),
[tablas de 40 configuraciones](CG34_20261023/business-tables.md) y
[curvas exportables](CG34_20261023/business-cost-curves.png).
Las curvas muestran ajuste OOF train y mínimos internos, no un mínimo escogido
en outer ni evidencia independiente de generalización. Los CSV de cada curva
quedan en el archivo adicional.

## Resultados comparables del criterio inicial preregistrado

Mismas 5.600 filas outer y 190 positivos para cada configuración. Coste hipotético:
FP = 100 €; FN = una hora × 1.200 €/h. La regla minimiza coste OOF inner sujeto
a recall ≥ 76%, con desempates prefijados. Cada fila se evalúa una vez por modelo.

### A. Umbral aprendido en inner

| Configuración | FN | FP | Recall | Precision | F1 | F2 | AP agrupada | €/1.000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RF | 24 | 44 | 87,37% | 79,05% | 0,8300 | 0,8557 | 0,9057 | 5.928,57 |
| GB depth3 | 29 | 21 | 84,74% | 88,46% | 0,8656 | 0,8546 | 0,9094 | 6.589,29 |
| CART depth5 | 26 | 28 | 86,32% | 85,42% | 0,8586 | 0,8613 | 0,8823 | 6.071,43 |
| CatBoost nativo depth4 | 23 | 151 | 87,89% | 52,52% | 0,6575 | 0,7746 | 0,8538 | 7.625,00 |
| XGBoost depth3 ponderado | 31 | 45 | 83,68% | 77,94% | 0,8071 | 0,8247 | 0,8801 | 7.446,43 |
| LightGBM 15 hojas | 16 | 181 | 91,58% | 49,01% | 0,6385 | 0,7803 | 0,8940 | 6.660,71 |
| EBM sin interacciones | 35 | 175 | 81,58% | 46,97% | 0,5962 | 0,7110 | 0,6199 | 10.625,00 |
| MLP (32) | 20 | 3.331 | 89,47% | 4,86% | 0,0921 | 0,1995 | 0,1610 | 63.767,86 |

GB mejora AP, precision y F1, pero omite cinco fallos más que RF. Sus 23 falsas
alarmas menos no compensan esos fallos bajo el coste primario: suma 3.700 € en
esta cohorte. LightGBM detecta más fallos en A a cambio de muchas más inspecciones.
Son intercambios medidos de estas configuraciones, no juicios universales de familia.

### B. AVISO fijo desde 0,15

| Configuración | FN | FP | Recall | Precision | €/1.000 |
|---|---:|---:|---:|---:|---:|
| RF | 22 | 63 | 88,42% | 72,73% | 5.839,29 |
| GB depth3 | 28 | 19 | 85,26% | 89,50% | 6.339,29 |
| CART depth5 | 26 | 28 | 86,32% | 85,42% | 6.071,43 |
| CatBoost nativo depth4 | 28 | 63 | 85,26% | 72,00% | 7.125,00 |
| XGBoost depth3 ponderado | 15 | 338 | 92,11% | 34,11% | 9.250,00 |
| LightGBM 15 hojas | 30 | 23 | 84,21% | 87,43% | 6.839,29 |
| EBM sin interacciones | 44 | 125 | 76,84% | 53,57% | 11.660,71 |
| MLP (32) | 81 | 1.651 | 57,37% | 6,19% | 46.839,29 |

Ganar A no basta para mejorar B. La promoción conservando contrato exige recall
desde AVISO ≥ 76% y coste no peor que RF 0,15, además de la materialidad propuesta:
≥ 5% de coste o ≥ 25% de latencia/tamaño con errores no peores. Ninguna de las
40 configuraciones reduce el coste primario de RF en A o B. Las mejoras de
rapidez de GB/CART vienen acompañadas de más fallos omitidos.

**CRITICA ≥ 0,70:** RF registra TP136/FN54/FP0/TN5410, recall 71,58% y precision
100%. Se informa aparte; no se exige a CRITICA recuperar todos los fallos.
Se conservan OK < 0,15, AVISO ≥ 0,15 y < 0,70, CRITICA ≥ 0,70.

Las [tablas completas](CG34_20261023/tables.md) contienen las 40 configuraciones,
TP/FN/FP/TN, F1/F2/AP, las tres políticas, tiempos, memoria, tamaño y nueve
escenarios. El [JSON](CG34_20261023/summary.json) añade AP por fold y su media,
umbrales, decisiones, curvas de fiabilidad y bootstrap. La AP agrupada mezcla
escalas entre modelos ajustados en folds distintos.

## Selector, paquete fijo e incertidumbre

Los dos selectores primarios eligen RF en 3/3 outer. Sus umbrales son
0,28845238 / 0,15759880 / 0,17083333. El refit fijo se elige mediante la misma
regla interna sobre train y guarda `0.1599255350951087`; **no se aplica ese corte
al servicio**. El procedimiento nested y el modelo fijo entrenado después son
objetos distintos. El paquete no hereda un test final independiente.

Para GB frente a RF en A, el bootstrap pareado condicional del coste diferencia
GB−RF da aproximadamente [−411,16; 1.875,45] €/1.000; el de recall,
[−5,79; 0] puntos porcentuales. Son 2.000 remuestreos estratificados de scores
OOF fijos, semilla 42. No corrigen búsqueda, reutilización previa ni dominio
sintético. La regla histórica AP+F2 se reconstruye dentro de cada outer-train:
elige GB/RF/RF y registra FN26/FP17; no sustituye la regla primaria por ese resultado.

Los nueve escenarios mantienen inspección 25/100/300 € y parada 0,5/1/4 horas.
Cada escenario aprende su umbral en inner. No se escoge después el coste que
favorezca a un candidato; no se afirman pérdidas o ahorros industriales reales.

## Calibración y rareza

En cada fit secundario, el estimador usa su 75% y el calibrador el 25% reservado,
semilla 43. Raw75 usa el mismo 75%. Ningún held ajusta el modelo o calibrador.
Los finalistas fueron RF/AdaBoost, RF/GB y RF/CART según sus respectivos inner.
Se elige sigmoid/raw75/sigmoid, todos sobre RF. Son variantes de un procedimiento,
no un único paquete calibrado evaluado independientemente.

El selector secundario obtiene en A FN24/FP29: 5.660,71 €/1.000, un 4,52% menos
que RF A. Reduce falsas alarmas conservando los fallos detectados en esta cohorte;
su intervalo bootstrap condicional de coste es [−428,57; −125] €/1.000.
La mejora puntual queda bajo el 5% propuesto. En B pasa a FN27/FP32,
6.357,14 €/1.000: peor coste y recall que RF 0,15. El cambio de semántica del score
exige revisión del manifiesto; no se recomienda promoverlo conservando el contrato.
Reliability de cinco bins, soportes, Brier y logloss están en el JSON. Brier no
mide únicamente calibración; el soporte positivo de la reserva es reducido.

Rareza se ajusta sobre los cinco sensores originales escalados desde normales
de train; tipo solo como contexto. IF/LOF son referencias adaptadas, no el IF
servido. Umbral común: cuantil 0,99 de normales OOF inner, método `higher`.
El 1% se fija en esa cohorte; no garantiza exactamente un 1% tras el refit outer.
Failure=0 es proxy de normalidad y no existe ground truth independiente de anomalías.

PCA(2) recupera 3 de los 22 FN de RF 0,15 y añade 39 FP: el coste primario de una
unión hipotética aumenta 300 € en 5.600 eventos. AE(3) recupera 2 y añade 46 FP;
IF recupera 1 y añade 53; LOF20/50 no recuperan ninguno y añaden 26/34 FP.
Estos son diagnósticos posteriores, no una selección del detector mirando outer.
Ninguno suprime RF ni convierte rareza en probabilidad de fallo.

Stacking y abstención quedaron explícitamente fuera de esta ronda en el manifiesto:
anidamiento adicional y política/capacidad humana sin prefijar. No cuentan como
cobertura ejecutada. TabPFN/TabICL siguen fuera por preentrenamiento externo;
no se descargaron pesos. AutoML/Optuna y redes tabulares mayores quedan condicionados.
No se ejecutaron modelos temporales, ETA/RUL ni otras fuentes de ajuste.

## Interpretabilidad, recursos y precisión

CART incluye reglas y rutas locales TP/FN/FP en unidades originales. EBM exporta
efectos y contribuciones log-odds que suman al score; GAM exporta sus bases spline,
efectos y contribuciones locales con la misma verificación. Los casos ausentes
se indican. [Explicaciones](CG34_20261023/explanations.json). Describen el modelo,
no causalidad; los efectos intrínsecos GAM no son intervenciones físicas sobre
sensores acoplados. Las derivadas conservan sus unidades y límites.

En refits outer, RF necesita aproximadamente 0,35–0,38 s de fit; GB, 0,95–0,97 s;
CART5, 0,008–0,009 s. El máximo p95 warm observado por fold es 4,88/3,61/3,34 ms,
respectivamente. Los artefactos rondan 878–923/239–251/6,1 kB. El tamaño excluye
bibliotecas. Son 50 repeticiones de una fila en proceso; no p95 HTTP/E2E,
batch32 o concurrencia del grafo. #81 conserva esas mediciones pendientes.

Kalista: Ryzen 5 7600X, 32 GiB RAM, RTX 5070 Ti de 16 GiB, driver 630.20.
Un experimento y un hilo por biblioteca. Límites: RSS2 GiB dejando 4 GiB al host;
incremento VRAM4 GiB dejando 6 GiB libres; evidencia2 GiB y disco libre10 GiB.
RSS máximo observado: 817,3 MiB. Las cargas del escritorio se preservaron.
El [piloto](CG34_PILOTO_20261023.md) no justificó GPU para el pool principal.

Contabilidad final: aproximadamente **1,43 CPU-h / 14** y **0,0386 GPU-h / 2**.
Las etapas conservan sus techos 3/8/2/1 CPU-h. CPU suma medidas de procesos e
incluye márgenes y reservas explícitas: 600 s de preparación, 120 de orquestación
y 60 de cierre inicial, más 120 de cierre del añadido docente y sus 7,54 s de
análisis medidos. GPU carga toda la vida de los procesos CUDA. No es tiempo de
calendario presentado como CPU. [Contabilidad](CG34_20261023/final-accounting.json).

Research aislado en D:, Python3.12.10, sklearn1.5.0, NumPy1.26.4, pandas2.2.2,
CatBoost1.2.10, XGBoost3.1.3, LightGBM4.6.0 e interpret-core0.6.10.
Interpret0.7.4 exigía sklearn≥1.6 y no se instaló. Lock research separado;
`pyproject.toml`, `uv.lock` y dependencias de la API permanecen intactos.
Licencias Apache2/MIT comprobadas en metadata; versiones y 79 binarios nativos
tienen registro. No se modificaron drivers, firewall, credenciales o administración.

Se conservan 27 avisos: 24 de colinealidad QDA, dos del movimiento CPU/CUDA de
XGBoost y uno de falta de convergencia en AE2, outer2, al alcanzar 1.000 iteraciones.
Son diagnósticos visibles de candidatos acotados; completo significa que terminó
el procedimiento, no que todas las optimizaciones convergieran. No se retocaron
configuraciones o tolerancias después de observarlos.

CSV se lee `round_trip`. Los originales XGBoost son float32: decodificar primero
ese dtype recupera exactamente sus valores. **173 artefactos CPU** recargados
reproducen los scores almacenados con diferencia máxima cero. La selección y sus
conteos se verifican invariantes. Se corrigió además el worker para que futuros
CSV guarden float64 promovido y registren el dtype nativo; la regresión reproduce
antes el error `0.7 != 0.699999988079071` y pasa después. El código sellado y sus
bytes originales se conservan. No se reentrenó para corregir esa representación.

## Artefactos y revisión

- [Revisión de la entrega y verificaciones](CG34_REVIEW_20261023.md).
- [Resumen](CG34_20261023/summary.json), [tablas](CG34_20261023/tables.md) y
  [comparación interactiva](CG34_20261023/comparison.html).
- [Auditoría aritmética](CG34_20261023/independent-arithmetic-audit.json) y
  [recargas](CG34_20261023/native-score-verification.json): hashes, filas, conteos,
  costes, AP con empates y presupuestos verificados. Es código independiente del
  cálculo principal, ejecutado por el mismo agente; no revisión humana independiente.
- [Paquete fijo](CG34_20261023/packages.json): RF de investigación, seis entradas,
  `predict_proba`, score no calibrado y conversión con diferencia cero. SHA-256:
  `6b33609caa275925ee0d23dcdacdb132308d924957d572af6cd3e0d5ebdd4444`.
  Entrenado sobre 5.600 filas; los 32 probes de recarga son train, no evaluación final.
- El [archivo de evidencia original](CG34_20261023/raw-evidence.zip) conserva scores por fila/fold, modelos propios, tareas,
  logs, contabilidad, fuente aprobada y código sellado. Su índice y SHA se publican
  junto a estos documentos. Los pickles se cargan solo tras verificar su procedencia/hash.
- El [añadido docente](CG34_20261023/business-evidence.zip) conserva sus scores,
  curvas, código, pruebas y contabilidad sin reescribir el archivo original.
  [Manifiesto original](CG34_20261023/archive.json) y
  [manifiesto adicional](CG34_20261023/business-archive.json): todos los hashes de
  entradas y CRC comprobados. El agregado final incluye ambos; el snapshot inicial
  permanece separado.
- Cinco copias JSON legibles y el SVG públicos normalizan finales de línea/espacios
  para Git. [Mapa de bytes](CG34_20261023/published-text-normalization.json).
  Los JSON conservan sus valores; los originales exactos siguen dentro de los ZIP.
  Manifiesto, sello de entrenamiento, scores, modelos y archivos ZIP no se alteran.
- Pruebas locales: 16 pasan; smoke sintético previo y de entrega: 50/50 sin avisos; Ruff0.17.1
  y formato, sin supresiones. Los logs rojos/verdes se conservan. La segunda versión
  del lector explicita el desempate de calibración por latencia inner; no cambia
  ninguna elección ni resultado primario de la primera versión.
- Comprobaciones locales adicionales: estructura/Compose sin iniciar servicios,
  CG25 (40 criterios, 90 enlaces, hashes actuales e históricos), `uv lock --check
  --offline` y paridad 50/50 del catálogo actual con el sellado. Los cambios de
  estilo y serialización del runner posterior no alteran fuentes ejecutadas.

La implementación, pruebas locales y evidencia están ejecutadas. La publicación,
CI, integración y aceptación se registran por separado en el PR. No se atribuyen
firmas, participación individual, ensayo, defensa, entrega o resultados industriales.
El servicio, SMB/OT, históricos y recursos compartidos no se han operado.

## Reproducción y fuentes

[Procedimiento](../workflows/ml-alternatives/procedure.md) y
[registro](../workflows/ml-alternatives/runs/20261023.md). Para analizar el archivo
conservado, usar el entorno research bloqueado y `scripts/finish_ml_study.ps1`,
con un `AnalysisName` nuevo; no reutilizar salidas.
Para reanudar el runner histórico, usar sus fuentes `sealed-code/`; el runner
actual rechaza reanudar un manifiesto de otro código. Una ejecución nueva requiere
otro sello antes de scores.

Plan y preregistro: [#83](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/83),
[#84](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/84#issuecomment-6360801042).
Los históricos [CG08](CG08_ALTERNATIVAS.md), [CG10](CG10_PRECISION_20261022.md) y
[CG17](CG17_CURRENT_STATE_SCOPE.md) conservan sus propias cohortes y versiones.
[Nested CV, sklearn1.5](https://scikit-learn.org/1.5/auto_examples/model_selection/plot_nested_cross_validation_iris.html),
[QDA, sklearn1.5](https://scikit-learn.org/1.5/modules/generated/sklearn.discriminant_analysis.QuadraticDiscriminantAnalysis.html),
[CatBoost GPU](https://catboost.ai/docs/en/features/training-on-gpu),
[XGBoost3.1 GPU](https://xgboost.readthedocs.io/en/release_3.1.0/gpu/index.html) y
[EBM](https://interpret.ml/docs/ebm.html) documentan los métodos y límites consultados.
