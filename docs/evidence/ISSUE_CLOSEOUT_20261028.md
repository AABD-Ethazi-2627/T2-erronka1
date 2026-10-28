# Reconciliación técnica de issues · 28/10/2026

El propietario solicita terminar las issues sucesivamente. Se contrasta la
entrega técnica publicada, sin atribuir revisión, firmas o participación a los
integrantes del equipo. No se promueve un modelo ni se cambia la política servida.

## CG36 / #85: referencias y clasificadores sencillos

La ejecución de #90 está integrada en main desde `5005ccde81f16cd2deac6ee3b30085d773e0fc88`.
El [informe](CG34_EXPLORACION_20261023.md), las [tablas](CG34_20261023/tables.md),
el [manifiesto](CG34_20261023/manifest.json) y las
[explicaciones CART](CG34_20261023/explanations.json) aportan parámetros,
versiones, folds, estados, predicciones, costes, tiempos y rutas TP/FN/FP.
El archivo sellado conserva scores por fila y fold; las constantes ilustran los
límites de accuracy/recall. Los adaptadores nested incluyen las ablaciones y el
pool prefijado, sin selección a partir de outer-held. La interpretación de
FN/FP y complejidad está publicada; no es una explicación oral atribuida al equipo.

## CG38 / #87: EBM y GAM

La misma entrega incluye dos EBM y dos GAM, versiones research aisladas,
splines/interacciones ajustados dentro de fold y comparación común con RF/GB.
`explanations.json` contiene efectos y contribuciones locales/globales, unidades,
casos disponibles y reconstrucción del score; no se limita a importancias.
La conclusión conserva RF: claridad, coste y errores se interpretan sin atribuir
causalidad a las contribuciones. No se modifica la API ni se impone monotonía.

## CG39 / #88: MLP y rareza

El inventario ejecutado incluye MLP y los diez detectores de rareza; escalado y
ajuste se restringen al train pertinente. Rareza usa cinco sensores y tipo como
contexto, sin tratar H/M/L como número ordinal. Cuantil 0,99 OOF sobre normales
proxy; los diagnósticos informan FN recuperados y FP añadidos sin suprimir RF.
TabPFN/TabICL quedan excluidos por preentrenamiento; AutoML/Optuna y redes mayores
quedan como alternativas condicionadas, sin descargar pesos ni fingir ejecución.
Estados, fallos, avisos y recursos constan en manifiesto, tablas e informe.

## Validación de este corte

Se verificó SHA-256 `640d75114324df4d8bafa20461cccf20da3850552c3bd6fa48080b9584e97896`
del archivo `raw-evidence.zip`, CRC y rutas de sus 5.350 entradas antes de extraer
en un directorio nuevo; sin cargar pickles ni ejecutar fuentes archivadas.
Se repitió `scripts.audit_ml_study.audit` sobre el summary sellado: PASS,
40 modelos supervisados contrastados, 5.163 hashes y contabilidad verificados.
[Resultado reproducido](CG34_CLOSEOUT_AUDIT_20261028.json).
Se conserva la discrepancia histórica de tamaño descomprimido documentada en
[CG40](CG40_EXECUTION_AUDIT_20261026.md); no se vuelve a sellar el original.

Revisión SELF_REVIEW / NOT_INDEPENDENT por el agente principal. No se declara
un experimento nuevo, test independiente, eficacia industrial, aceptación docente,
ensayo, defensa o entrega. Las issues #37/#26/#27/#82 mantienen sus puertas humanas.
#89 mantiene la reconciliación de recomendación y paquete; #81 mantiene campaña
real, ahora sobre un candidato reconstruido autorizado con identidad separada.
