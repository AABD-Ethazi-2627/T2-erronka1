# Interpretación y propuesta de decisión ML: 23/10/2026

**Propuesta para revisión: conservar el Random Forest servido y el contrato
0,15/0,70.** La evidencia disponible permite completar la interpretación técnica
de #83, #85, #87, #88 y #89 sin nuevos ajustes ni inferencias. No registra una
aprobación PM/docente, participación individual, aceptación de la defensa o cierre
de esas issues. Las cinco seguían abiertas en la consulta GitHub de esta revisión.

Base examinada: `5005ccde81f16cd2deac6ee3b30085d773e0fc88`, rama
`review/pending-20261023`, checkout `D:/github/AABD-Ethazi-2627/B-taldea`.
En el cierre, el checkout compartido avanzó concurrentemente a
`c122a675a245c8a70ac4b5c43cd6ec6acf77478a`; los 44 archivos históricos
examinados conservaron sus hashes. Ese avance no amplía esta revisión a los
cambios de código/pruebas de otros agentes.
[PR #90](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/90) ya está **MERGED**:
head `3a5c3cf4d318ba254b8d461b9a03a8242bb32bd3`, merge `5005ccde…`,
23/10/2026 a las 11:45:09 UTC. La integración Git de #90 está resuelta;
sus comentarios y documentos históricos conservan el corte anterior al merge.
La integración de otro paquete en la API y la aceptación humana son decisiones
distintas. No se modifican aquellos documentos históricos.

## Fuentes, poblaciones y método de revisión

Se consultaron los cuerpos y todos los comentarios de las cinco issues mediante
`gh issue view --json number,title,state,body,comments,url`, y el estado/head/merge
de #90 mediante `gh pr view`. Las copias de lectura y el auditor de esta ronda
quedan en `D:/github/_local/t2-review-20261023/ml-decision/`.

Las afirmaciones de ejecución anteriores se contrastan con los siguientes
artefactos conservados en la base indicada; no se presentan como pruebas
repetidas en esta ronda:

- [Manifiesto](CG34_20261023/manifest.json) y [sello](CG34_20261023/seal.json):
  catálogo, particiones, reglas y presupuesto. SHA-256 del manifiesto
  `d881aa24d43a1f44e98956c37a4e88cacb21989a1fe0c205ed9e8d67aa72187b`.
  Código de fit `e644737`, conservado dentro de
  [raw-evidence.zip](CG34_20261023/raw-evidence.zip).
- [Resumen inicial](CG34_20261023/summary.json), [tablas](CG34_20261023/tables.md)
  y [suplemento](CG34_20261023/supplement.json): métricas, folds, selectores,
  recursos, rareza y calibración. Se cita la clave JSON junto a las conclusiones.
- [Costes docentes](CG34_20261023/business-costs.json),
  [sello adicional](CG34_20261023/business-seal.json),
  [resumen docente](CG34_20261023/business-summary.json) y
  [tablas docentes](CG34_20261023/business-tables.md): añadido posterior al
  análisis inicial, sobre scores ya guardados; no es el preregistro original.
- [Explicaciones](CG34_20261023/explanations.json): árbol, efectos y casos locales
  TP/FN/FP de cinco modelos ajustados solo con outer0-train.
- [Paquete](CG34_20261023/packages.json),
  [recargas históricas](CG34_20261023/native-score-verification.json),
  [revisión histórica](CG34_REVIEW_20261023.md) y
  [contabilidad final](CG34_20261023/final-accounting.json).
- [Lote adicional](CG34_BATCH_20261023.md),
  [protocolo](CG34_BATCH_20261023/protocol.json),
  [sello](CG34_BATCH_20261023/seal.json),
  [métricas](CG34_BATCH_20261023/metrics.json) y
  [tablas del lote](CG34_BATCH_20261023/tables.md).

**Desarrollo/CV:** la única fuente de ajuste fue el CSV reducido de 8.000 filas,
SHA-256 `1cce2859f4833b63dbf0992868884e5deac6f79e4d74a245abbc484d34e396ce`.
Las comparaciones outer reúnen una predicción por configuración y fila de las
**5.600 train originales, con 190 positivos**. Las 1.200 de validación ya se
habían reutilizado; el test antiguo de 1.200 ya había sido inspeccionado y quedó
excluido. CG34 no los puntúa ni los usa para elegir. El anidamiento no convierte
un dataset explorado en test final independiente. Fuente: `manifest.membership`,
`manifest.outer` y [informe del estudio](CG34_EXPLORACION_20261023.md).

**Lote adicional:** 507 CSV contienen 5.070 emisiones, **2.000 vectores únicos y
68 positivos únicos**; las emisiones positivas son 175. El protocolo registra
cero coincidencias exactas de las seis entradas con cualquiera de las 8.000 filas.
Es separación de valores, sin prueba de independencia de generación, origen
industrial o cronología física. Los duplicados no multiplican la muestra. El
RF fijo entrenado con 5.600 filas y los tres refits outer de cada configuración,
entrenados con 3.733/3.734, se informan por separado. Fuente:
`protocol.cohorts`, `protocol.model_comparison`, `metrics.counts` y `metrics.scope`.

**Verificado en esta ronda:** lectura y aritmética stdlib de JSON/ZIP; sin cargar
estimadores, ajustar modelos, calcular nuevas predicciones, modificar umbrales
o contactar servicios de laboratorio. No se inspeccionó ni alteró el laboratorio
CG32 del padre. Las cifras monetarias siguientes son costes hipotéticos de
clasificación; no son pérdidas, intervenciones eficaces o ahorros industriales.

## #85 / CG36: referencias, ablaciones y CART

[Requisito y comentario de ejecución](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/85#issuecomment-6362289983).
Las 21 configuraciones de este grupo tienen 63 unidades de screening y 252 de
nested: tres screening, nueve inner y tres outer por configuración. En
`summary.coverage` todas esas unidades constan completas. Los modelos sencillos
no requieren repetir entrenamiento para explicar sus resultados.

Para interpretar los números se separan A, umbral aprendido en inner, y B,
AVISO fijo desde 0,15. El criterio inicial es `1.200 FN + 100 FP`:

- RF A: TP166/FN24/FP44, recall 87,37%, precision 79,05%,
  **5.928,57 €/1.000**. GB depth3 A: TP161/FN29/FP21, recall 84,74%, precision
  88,46%, **6.589,29 €/1.000**. GB reduce 23 FP y añade cinco FN: el coste total
  aumenta `5×1.200 − 23×100 = 3.700 €`. Su AP agrupada 0,9094 supera 0,9057 de
  RF, pero esa ventaja no es la función de decisión primaria.
- CART5 A: TP164/FN26/FP28, **6.071,43 €/1.000**. Frente a RF A ahorra 16 FP y
  añade dos FN: aumenta 800 € en 5.600 filas. CART8 A, FN25/FP37, cuesta
  6.017,86 €/1.000. CART3 B omite 85/190 fallos; su A casi siempre alerta
  (FN1/FP5.406). Poca profundidad no garantiza una política de alertas útil.
- En B, RF da FN22/FP63, **5.839,29 €/1.000**; GB FN28/FP19, 6.339,29;
  CART5 FN26/FP28, 6.071,43. Con la matriz docente y el mismo B, los costes son
  **30.892,86 / 34.357,14 / 33.000 €/1.000**, respectivamente. CART5 ahorra
  35 FP pero añade cuatro FN frente a RF B: `4×4.700 − 35×200 = 11.800 €`
  más en esa cohorte.

Fuentes: `summary.models.{rf_reference,gb_depth3,cart_depth3,cart_depth5,cart_depth8}`
y `business-summary.models.{rf_reference,gb_depth3,cart_depth5}.{A,B}`.

Las constantes muestran por qué accuracy y recall aislados engañan: siempre 0
acierta 5.410/5.600 filas (96,61%) omitiendo los 190 fallos; siempre 1 logra recall
100% con 5.410 falsas alarmas. Sus costes iniciales son 40.714,29 y 96.607,14
€/1.000. HistGB A cuesta 7.517,86; logística A 18.982,14, y su B consigue recall
96,84% a cambio de 2.332 FP. GaussianNB A registra FN48/FP533 en ambas variantes;
LDA FN47/FP686; QDA FN46/FP360 y FN47/FP467. Los kNN A cuestan de 11.321,43 a
96.607,14 €/1.000. AdaBoost depth1/depth2 A cuestan 6.482,14/6.357,14, pero a
0,15 ambos alertan todas las filas. Son resultados de estas configuraciones y
escalas, sin inferir que la familia completa sea incapaz. Fuente: las claves de
esos nombres en `summary.models`; las 21 filas permanecen en las tablas completas.

Las ablaciones aumentan coste en este protocolo: RF sin derivadas A conserva
FN24 pero eleva FP44→261; GB sin derivadas A reduce FN29→24 y eleva FP21→235.
En B, RF sin derivadas da FN28/FP190 y GB sin derivadas FN38/FP99. La comparación
respalda conservar la representación aumentada aquí; no demuestra causalidad
física ni obliga a usar estas derivadas en otros dominios. Fuente:
`summary.models.{rf_no_derived,gb_no_derived}` y `manifest.catalog`.

CART sí aporta una simplificación medida: fit mediano 0,00822 s frente a 0,36220 s
de RF; modelo mediano 6.068 frente a 898.859 bytes; máximo p95 warm por fold
3,3395 frente a 4,8834 ms (reducciones calculadas de 99,32% en tamaño y 31,61%
en ese p95). Son 50 repeticiones de una fila en proceso y tamaños sin bibliotecas.
La mejora de recursos supera el 25% propuesto, pero **no cumple errores no
peores**. No acredita rendimiento HTTP/E2E. Fuente: `summary.models.*.folds[].resources`.

Lectura de reglas, `explanations.models.cart_depth5.cases`, usando sus cortes
inner de outer0, **no el contrato servido**:

- TP, fila 679: `wear_torque=10.106,2 ≤ 10.998,50 min·Nm` y
  `power_W=9.030,15 > 9.014,61 W`; llega a score 1 ≥ 1/6.
- FN, fila 464: sigue `wear_torque≤10.998,50`, potencia entre 3.490,67 y
  9.014,61 W, diferencia térmica >8,65 K y desgaste >202,50 min; score
  0,034884 < 1/6 aunque la etiqueta es 1. La ruta explica la omisión del árbol;
  no prueba que ese régimen sea físicamente seguro.
- FP, fila 6.543: `wear_torque=11.128 > 10.998,50`, tipo distinto de L y
  torque 52 ≤59,65 Nm; score exactamente 1/6. El comparador `≥` activa la
  alerta aunque la etiqueta es 0. No es un error de redondeo.

El árbol completo usa cortes estandarizados; estas rutas usan unidades originales.
`wear_torque` es un proxy min·Nm, no desgaste físico medido. Las diez condiciones
exportadas se recalcularon desde las entradas guardadas sin ejecutar el árbol.

**Conclusión técnica #85:** conservar RF; usar CART como explicación de un
intercambio coste/complejidad y como referencia compacta, sin promoverlo. Pendiente
humano: Angiecrizu contrasta las reglas y su explicación con los responsables;
la revisión documental no acredita esa participación ni aceptación.

## #87 / CG38: EBM, GAM y explicaciones

[Requisito y ejecución](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/87#issuecomment-6362291412).
Dos EBM y dos GAM completaron 12 screening y 48 nested. La evidencia del entorno
fija interpret-core 0.6.10 con sklearn 1.5.0; el informe registra que interpret
0.7.4 exigía sklearn≥1.6 y no se instaló. Esto describe la compatibilidad usada,
sin proponer actualizar la API. Fuentes: `manifest.environment`,
[admisión de paquetes](CG34_20261023/package-admission.json) e informe CG34.

Comparación inicial A/B, expresada como **FN/FP; €/1.000**:

- EBM sin interacciones: A **35/175; 10.625**, B **44/125; 11.660,71**.
- EBM hasta tres interacciones: A **28/176; 9.142,86**, B **42/108; 10.928,57**.
- GAM tres nudos: A **40/320; 14.285,71**, B **61/136; 15.500**.
- GAM cinco nudos: A **37/240; 12.214,29**, B **54/140; 14.071,43**.

Las interacciones mejoran EBM respecto a su variante aditiva, y cinco nudos
mejoran GAM respecto a tres, pero ninguna alcanza el coste de RF A o B. GAM B
queda además por debajo del recall de desarrollo 76%: 67,89%/71,58%. Con costes
docentes, EBM0/EBM3/GAM3/GAM5 B cuestan respectivamente
51.571,43/49.285,71/66.232,14/60.500 €/1.000 frente a 30.892,86 de RF.
Fuentes: `summary.models.{ebm_0,ebm_3,gam_3,gam_5}` y las mismas claves
en `business-summary.models.*.B`.

Las explicaciones disponibles permiten hablar de cómo decide el modelo:

- Cada uno de los cuatro modelos contiene TP/FN/FP; no hay tipos de caso
  ausentes. Son ejemplos descriptivos outer0-held, escogidos después de fijar
  la evaluación, y no utilizados para diseñar el modelo.
- EBM exporta efectos globales por intervalos en unidades originales. En el TP
  679 de EBM0, el intercepto −5,535892 y las contribuciones, entre ellas potencia
  +1,766838 y torque +1,023322, suman un logit cuya logística es 0,172610,
  superior a su corte inner 0,111703. En el FN 464 el desgaste aporta +1,042590,
  pero el conjunto queda en 0,006641, por debajo del corte. En el FP 7.653,
  rpm +1,835358, potencia +1,766838 y torque +1,023322 contribuyen a una alerta
  0,183146 sobre una etiqueta 0. Ningún término aislado explica toda la decisión.
- EBM3 conserva tres contribuciones de interacción: aire×rpm, rpm×diferencia
  térmica y rpm×`wear_torque`. En su TP 679 aportan −0,242526, −0,237902 y
  +0,300276 log-odds. Su FN 464 sigue en 0,015129 <0,082442; su FP 1.386 queda
  en 0,084269 ≥0,082442. La interacción añade contexto al modelo, sin eliminar
  estos errores. El JSON publica esas interacciones locales; sus efectos
  globales exportados son univariantes, no una superficie global de interacción.
- GAM publica ocho efectos globales numéricos con ejes en unidades originales y
  contribuciones de bases spline más categoría e intercepto. Para TP679/FN464/FP1386,
  GAM3 produce 0,567622/0,010204/0,141885 con corte 0,080520; GAM5,
  0,644126/0,007038/0,101396 con corte 0,089654. La auditoría reconstruye los
  doce scores EBM/GAM a partir de sus sumas guardadas. No se ha vuelto a inferir.

Fuente de cada caso, contribución y corte: `explanations.models.<nombre>.cases`;
los ejes y unidades están en `.global_effects`, y el alcance GAM en `.effect_scope`.
Las contribuciones son log-odds, no porcentajes de causalidad. Sensores y derivadas
están acoplados: fijar otras columnas de diseño para dibujar un efecto GAM no es
una intervención física realizable. Tipo H/M/L es categórico, sin orden continuo.

**Conclusión técnica #87:** conservar estas explicaciones para la memoria y
defensa; su trazabilidad no compensa el aumento medido de omisiones/coste para
promover EBM/GAM. Pendiente humano: revisión de Angiecrizu y responsables sobre
la explicación global/local y sus límites. No se atribuye una explicación oral
individual ni una aceptación docente por existir estos artefactos.

## #88 / CG39: MLP, rareza, avisos y alternativas condicionadas

[Requisito y ejecución](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/88#issuecomment-6362292200).
Tres MLP y diez detectores completaron 39 screening y 156 nested. MLP16 A da
FN42/FP3.853; MLP32 A FN20/FP3.331; MLP32×16 A FN36/FP3.634. MLP32 detecta
cuatro fallos más que RF A a cambio de 3.287 FP adicionales: su precision es
4,86% y coste 63.767,86 €/1.000 frente a 5.928,57. En B MLP32 omite 81/190,
recall 57,37%, con 1.651 FP. El menor tamaño o p95 en proceso de ese MLP no
compensa esos errores. No se extrapola este resultado a toda red neuronal.
Fuente: `summary.models.{mlp_16,mlp_32,mlp_32_16}` y `.folds[].resources`.

Rareza usa cinco sensores originales, escalados desde train normal-proxy; tipo
queda como contexto. Failure=0 es un filtro proxy, no verdad independiente de
normalidad. El cuantil 0,99 `higher` se fija en normales OOF inner: no garantiza
1% exacto de alertas después del refit ni es una probabilidad de avería. IF/LOF
son referencias adaptadas, distintas del IF servido. Fuente: manifiesto,
informe CG34 y `summary.anomalies`.

Diagnóstico posterior respecto a **los 22 FN de RF B**, sin escoger detector
mirando outer: IF recupera 1 y añade 53 FP; LOF20 0/26; LOF50 0/34; OCSVM
nu0,01 0/0; OCSVM nu0,05 0/1; covarianza robusta 1/48; PCA2 3/39; PCA4 0/42;
AE2 1/107; AE3 2/46. El segundo número siempre es FP añadido respecto a la
etiqueta de avería, entre los 5.347 negativos sin aviso RF, **no todos los
avisos del detector**. Por ejemplo PCA2 avisa 91/5.600 filas, 41 con etiqueta
de fallo; solo tres eran FN de RF. Fuente: `summary.anomalies.<detector>`.

Para la unión hipotética RF+PCA2, el coste inicial **aumentaría 300 €**:
`39×100 − 3×1.200`. Con la matriz docente **bajaría 6.300 €**, un **3,64%**:
`3×(5.000−300) − 39×200`. La unión tendría TP171/FN19/FP102/TN5308 en esta
cohorte, por suma de los recuentos guardados; no se ejecutó ni se seleccionó una
política nueva. Esa mejora es menor que el 5% de materialidad propuesto, depende
del coste y es diagnóstico posterior sin verdad de anomalías. Ningún detector
suprime una alerta RF. No respalda activarlo en el servicio.

Los avisos se verificaron directamente en los `units/*/result.json` del ZIP:
**24 de colinealidad QDA, dos de transferencia CPU/CUDA de XGBoost y uno de
convergencia AE2**, 27 en total. AE2 outer2,
`units/31374c047738f1ea75a00d1fdcbc4f54e276a42e2a2b6df3ac7a2c103c494119/result.json`,
terminó con `ConvergenceWarning` al techo de 1.000 iteraciones. Se conserva
como candidato acotado no convergido; no es timeout, excepción, unidad sin
resultado ni prueba fallida. Tampoco se afirma que convergiera. QDA conserva
su limitación numérica aunque terminó; el aviso CUDA explica el coste de mover
datos en el piloto. No se ajustaron tolerancias después de observar resultados.
Fuente: ZIP original y [revisión histórica](CG34_REVIEW_20261023.md).

Estado de lo no ejecutado, según [#83](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/83)
y `manifest.optional`:

- TabPFN/TabICL: fuera del pool por pesos preentrenados con datos externos al
  límite de ajuste aprobado; no se descargaron ni ejecutaron. Una autorización
  futura distinta sería otro alcance, sin resultado supuesto.
- AutoGluon/FLAML/Optuna: segunda búsqueda condicionada a hipótesis, whitelist,
  presupuesto y anidamiento nuevos; registrarlos no acredita cobertura.
- TabM/TabNet/FT-Transformer desde cero: backlog condicionado a pregunta y
  recursos explícitos; no necesarios para completar la ronda prefijada de 50.
- Stacking: no ejecutado por el anidamiento adicional fuera de esta ronda.
  Abstención: no ejecutada sin política/capacidad humana prefijada. No se cuentan
  como aciertos, ensambles medidos o cobertura completada.
- Modelos temporales, ETA/RUL y fuentes adicionales de ajuste: fuera del alcance
  contemporáneo aprobado; no se inventan secuencias a partir de IDs o fechas.

**Conclusión técnica #88:** no promover MLP o rareza con esta evidencia;
conservar diagnósticos, advertencias y descartes explícitos. Pendiente humano:
los responsables revisan el balance de alertas y recursos, sin convertir esa
revisión en permiso para repetir fits o activar una unión exploratoria.

## #89 / CG40: nested, calibración y contrato

[Ejecución](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/89#issuecomment-6362292961)
y [contraste de Niistal](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/89#issuecomment-6364629784).
La comprobación de pertenencias del grupo se recoge en
[revisión de integración](PENDING_INTEGRATION_20261023.md); esta ronda verificó
cobertura y aritmética, sin repetir su revisión completa de fuga o recargas.

El núcleo de diez completó primero 90 fits inner +30 refits outer; el catálogo
entero completó **600 nested**, 50×(9+3). El selector elige configuración/corte
con OOF inner y evalúa en outer-held; el paquete fijo se escoge después con la
regla interna sobre 5.600 train. Sus métricas OOF de ajuste no son las métricas
de evaluación de un modelo fijo independiente. Fuente: `manifest.core`,
`manifest.outer`, `summary.coverage`, `.selectors` y `.fixed_choice_from_5600_inner`.

Con el coste inicial, núcleo y pool40 eligen RF/RF/RF. Con el coste docente,
núcleo RF/RF/RF y pool40 **AdaBoost/RF/RF**: no se puede atribuir el resultado de
este último a RF fijo. La regla aplicada a las 5.600 train elige RF en ambos
análisis. El corte del paquete research inicial es **0,1599255350951087**; el
añadido docente calcula **0,11899870801033592** sobre scores guardados, sin nuevo
refit ni aplicación al servicio. Fuente: `summary.selectors`,
`business-summary.selectors` y `.fixed_specification_ranking[0]`.

La matriz docente procede del texto aportado por el usuario y atribuido al foro
de Aitor, 22/10 18:52; este revisor no verifica cuentas industriales ni inventa
una firma docente. Define `C=5.000 FN+200 FP+300 TP`.
Como `TP+FN=P`, equivale a `4.700 FN+200 FP+300 P`: detectar un fallo adicional
compensa **23,5 FP**, no 25, al incluir el mantenimiento de TP. El hipotético
corte económico 0,040816 requeriría probabilidades calibradas y ese modelo
completo de acciones/costes; no se traslada al score RF no calibrado.
Fuente: `business-costs.source`, `.cost_eur` y `business-summary`.

La comparación que podría inducir a una promoción incorrecta es XGBoost depth3
sin pesos: con coste docente A da TP173/FN17/FP165, **30.339,29 €/1.000**, un
5,30% menos que RF A (32.035,71). Frente al RF B ya disponible solo mejora 1,79%;
en su propio B da TP165/FN25/FP48, **32.875 €/1.000**, un **6,42% más** que
RF B (30.892,86). No fue el elegido por la regla fija interna y mejorar A no
satisface conservar contrato B. Fuente: `business-summary.models.{xgb_d3_False,rf_reference}`.

Calibración reservó 75% de cada train para estimador y 25% para calibrador;
raw75 usa el mismo 75%. Los finalistas se eligieron dentro de cada outer:
RF/AdaBoost, RF/GB, RF/CART. Las **72 unidades** terminaron. El selector inicial
elige RF sigmoid/raw75/sigmoid y obtiene A FN24/FP29, **5.660,71 €/1.000**,
4,52% mejor que RF A; en B pasa a FN27/FP32, **6.357,14**, peor que RF B.
El añadido docente restringido elige RF sigmoid en los tres outer: A FN24/FP67,
**32.714,29**; B FN30/FP22, **36.142,86**. Sus finalistas venían del coste
inicial: no es una búsqueda completa nueva para la matriz docente. Fuente:
`summary.calibration`, `supplement.calibration_selector` y
`business-summary.restricted_calibration`.

Reliability, Brier y logloss conservan cinco bins y soportes. Como ejemplo de
por qué no tratar el score raw como probabilidad calibrada: RF agrupa 56 filas
en [0,6;0,8), score medio 0,7297 y frecuencia etiquetada 53/56=0,9464; en [0,2;0,4)
solo hay 22 filas y siete positivos. No prueba calibración universal por su Brier
agrupado 0,007559. En outer2 isotonic RF tiene Brier 0,005975 frente a 0,006076
de sigmoid, pero logloss 0,094648 frente a 0,032791; menor Brier por sí solo no
determina la elección por coste. El refit outer reserva aproximadamente 32
positivos al calibrador. Fuente: `summary.models.rf_reference.reliability` y
`summary.calibration.*.variants[].{reliability,support}`.

El bootstrap pareado de 2.000 remuestreos estratificados, semilla 42, condiciona
a scores OOF fijos. Para GB−RF A, el intervalo de coste es aproximadamente
[−411,16;1.875,45] €/1.000; para la calibración inicial A, [−428,57;−125].
No elimina selección previa, reutilización del dataset o dominio sintético.
La mejora puntual calibrada queda bajo el 5% propuesto y pierde en B; ni ese
intervalo ni el ranking outer eligen un modelo nuevo. Los nueve escenarios de
sensibilidad conservan sus umbrales aprendidos en inner, sin escoger después
el escenario favorable. Fuente: `summary.models.gb_depth3.bootstrap_A`,
`supplement.calibration_selector.bootstrap_A` y `.models.*.sensitivity`.

El contrato sigue siendo **OK <0,15; AVISO ≥0,15 y <0,70; CRITICA ≥0,70**.
Las métricas B cuentan todos los scores ≥0,15, incluidos los críticos. RF
CRITICA tiene TP136/FN54/FP0/TN5410, recall 71,58%; no se le exige sustituir el
recall de AVISO ni se descartan los avisos intermedios. El paquete research
`34a14ab97a0e1facc4f4eff10b7ed9227516cc853d7400abd351ccef17cffe72` es
`exported_research_only`, con `uncalibrated_current_state_score` y
`operational_bundle_ready=false` en `packages.json`. No es el bundle CG26 de
entrega. Calibrar cambiaría la semántica y exigiría revisar manifiesto/contrato,
paquete propio y decisión PM; no basta sustituir un fichero o un corte.

**Conclusión técnica #89:** la cobertura nested y las comparaciones están
disponibles; recomendar conservar RF y los niveles actuales. La aprobación de
esa disposición por responsables/PM y la interpretación humana siguen pendientes.
Las mediciones HTTP/E2E de #81 se resuelven en su propio flujo; no se declaran
ausentes ni completadas a partir de este informe o del antiguo p95 en proceso.

## Lote adicional: qué añade a la decisión

El RF **research fijo** obtiene, sin ajustes posteriores, AVISO TP58/FN10/FP20/
TN1912 sobre 2.000 únicos: recall **85,29%**, precision **74,36%**, F1 0,7945,
F2 0,8286, AP 0,8938 y coste docente **71.400 € / 35.700 €/1.000**. CRITICA da
TP48/FN20/FP0/TN1932; no sustituye AVISO. Sobre 5.070 emisiones repetidas,
AVISO da TP152/FN23/FP47/TN4848 y 170.000 €; no es otra muestra independiente.
Fuente: `metrics.fixed.policies.{aviso,critica}.{unique,events}`.

El corte research docente, fijado antes del lote, da FN9/FP28 en únicos y
68.300 €, una reducción puntual del 4,34% respecto a 0,15; baja precision a
67,82%. No es permiso para elegir corte mirando el lote. Los tres refits RF
outer a 0,15 dan FN9–10/FP16–21 y media descriptiva 34.783,33 €/1.000; CART5
FN10–12/FP3–17 y 36.950; GB FN11–12/FP8–11 y 38.583,33. EBM/GAM/MLP y los
detectores siguen visibles en las tablas; no se selecciona un nuevo ganador a
partir de sus medias o extremos. Los rangos son de tres artefactos, no intervalos
de confianza ni un ensamble de 6.000 observaciones. Fuente:
`metrics.fixed.policies.research_business`, `.outer_models` y tablas del lote.

La evaluación previa de 151 artefactos terminó sin avisos; ese hecho no borra
los avisos de entrenamiento. Esta ronda verificó el recuento y las listas
`warnings` guardadas, sin repetir inferencia. El lote apoya describir el
comportamiento fuera de los valores de las 8.000 filas anteriores, con sus
etiquetas suministradas; no certifica el modelo servido, generalización
industrial, predicción futura, causalidad o equidad.

## #83 / CG34: disposición consolidada para responsables

[Plan, ejecución y lote](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/83).
El catálogo terminó 8 unidades piloto +150 screening +600 nested +72 calibración
+1 refit = **831 unidades**. El ZIP contiene 831 resultados completos; los
avisos se han preservado. La contabilidad final de entrenamiento/análisis fue
1,427684 CPU-h y 0,038558 GPU-h; incluido el lote previo y sus reservas,
1,464869 CPU-h y 0,038558 GPU-h, dentro de 14/2 h. La etapa nested empleó
0,793884 CPU-h de su techo 8 h. No se propone gastar el remanente: las cinco
issues necesitan revisión/interpretación/disposición, no repetir fits.
Fuentes: `summary.coverage`, ZIP, `final-accounting.json` y
[contabilidad acumulada](CG34_BATCH_20261023/cumulative-accounting.json).

El [piloto CPU/CUDA](CG34_PILOTO_20261023.md) no logró la mejora global del 25%
prefijada para ampliar GPU; el pool principal se ejecutó en CPU. No se confunde
CUDA disponible con aceleración medida, ni diferencia CPU/CUDA con fallo de
recarga del mismo artefacto. Las 173 recargas exactas y las 16/22 pruebas
estudio/lote son verificaciones **históricas documentadas**, no reejecutadas aquí.

**Propuesta técnica conjunta, sujeta a revisión:**

1. Conservar RF servido y los niveles 0,15/0,70; no promover otro modelo,
   calibrador, corte o unión de rareza con estos resultados.
2. Incorporar esta interpretación a la revisión de #85/#87/#88 y, después, a
   la disposición de #89/#83. Mantener visible el contraste ya aportado por
   Niistal; este texto no sustituye la revisión de los responsables ni acredita
   participación individual de Angiecrizu, petiteiker o cualquier otra persona.
3. Registrar la decisión humana efectiva y su alcance cuando exista; enlazar
   los resultados a #80/#37 y preparar la explicación/ensayo de #26 mediante
   sus responsables. No atribuir aprobación docente o PM por inferencia.
4. Seguir #81 con la identidad exacta del bundle de entrega y su evidencia
   propia; su trabajo concurrente no se altera. Integración Git de #90 resuelta
   no significa promoción de `rf_reference.joblib` ni despliegue.

**Pendientes reales:** contraste humano de reglas/explicaciones y recursos;
disposición PM de conservar RF o de abrir un alcance distinto; incorporación
humana a memoria/defensa y sus revisiones de aceptación. La revisión de capacidad
prevista para el 26/10 y las fechas objetivo de las issues no prueban compromiso
individual ni ejecución futura. No hay en las fuentes consultadas aprobación
que permita marcar estas cinco issues cerradas. Este informe no modifica sus
casillas, comentarios, estados, responsables o calendario.

## Validación ejecutada y límites residuales

Comando de esta revisión, desde el checkout indicado:

```powershell
py -3 D:/github/_local/t2-review-20261023/ml-decision/validate_decision.py
git diff --check -- docs/evidence/ML_DECISION_REVIEW_20261023.md docs/workflows/ml-alternatives/state.md
```

El auditor usa solo biblioteca estándar y agregados/JSON del ZIP. Resultado en
`D:/github/_local/t2-review-20261023/ml-decision/validation.json`:

- 1.801 matrices: sumas, soportes, recall, precision, F1/F2 y costes que constan
  en los objetos JSON; 40 agregaciones outer contrastadas con sus folds.
- Doce reconstrucciones logísticas EBM/GAM, diez condiciones de rutas CART y
  sus quince tipos de caso TP/FN/FP comprobados con entradas/contribuciones
  guardadas. Es aritmética descriptiva, sin ejecutar el predictor.
- Sellos de manifiesto, costes y protocolo del lote coinciden. SHA-256, número
  de archivos y CRC de los ZIP original/adicional: 5.350/64 entradas; 831
  `result.json` completos y distribución 24/2/1 de avisos contrastada.
- 44 archivos históricos de evidencia conservan los mismos SHA-256 durante la
  revisión. Se verifican también los enlaces locales de los dos documentos
  autorizados. La auditoría no recompone AP desde scores por fila ni vuelve a
  ejecutar las recargas históricas, suites ML, CI o laboratorio.

La precision indefinida del clasificador sin alertas se guarda como cero en el
estudio y como `null` en el lote: son convenciones explícitas de los agregados,
sin inventar aciertos o una precisión medible al no haber predicciones positivas.

**Hallazgos residuales de alcance:** no se ha identificado una discrepancia
aritmética en las comprobaciones ejecutadas. Se conservan como limitaciones los
27 avisos experimentales, la falta de test final independiente, las restricciones
del diagnóstico de rareza y de la calibración adicional, el estado research del
paquete y las revisiones humanas pendientes. Son motivos para mantener la
disposición propuesta y sus fronteras; no se convierten en fallos de pruebas,
criticidad inventada o aceptación operativa. La revisión propia y esta revisión
documental del subagente permanecen distintas de aprobación humana/CI/despliegue.
