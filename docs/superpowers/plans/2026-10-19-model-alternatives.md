# CG08 — alternativas, protocolo fijado antes de ejecución

Objetivo: contrastar RF con familias tabulares y comprobar si combinar señales
aporta detecciones frente a falsas alarmas. Rama feat/8-rf-controlled-evaluation,
base bddd29b. No se modifica API, bundle ni thresholds de producción/laboratorio.

Se conservan 5600 train, 1200 validación reutilizada, 1200 test antiguo excluido,
con folds originales de CG08 y guard de firmas duplicadas. Preprocesamiento se
ajusta dentro de cada fold. Dependencias de investigación separadas en uv.

1. Comparar candidatos prefijados: dummy/logística, RF referencia/profundo,
   ExtraTrees, HistGradientBoosting, GradientBoosting, CatBoost, SVM, bosque
   balanceado. Presupuesto pequeño declarado; no igualdad exacta de cómputo.
2. Guardar scores OOF por fila, AP como selección primaria, F2/recall/precisión
   como diagnóstico, thresholds definidos por OOF y frontera recall/FP.
3. Comparar soft voting equiponderado entre RF y mejor candidato no-RF elegido
   por AP OOF, y combinación de los tres mejores individuos. No stacking entrenado
   sobre predicciones in-sample. La elección de miembros añade optimismo de búsqueda.
4. Congelar ganador por AP OOF antes de consultar validación. Ajustar solo en train;
   validar modelo elegido y referencias con threshold OOF. Reportar también umbral
   RF anterior como referencia histórica, sin reinterpretarlo como nueva selección.
5. Anomalías separadas: IF referencia y LOF novelty; ambos ajustados solo con train
   etiquetado normal; threshold cuantil .99 de scores normales OOF (no validación).
   Evaluar complemento OR diagnóstico, sin confundir failure con verdad de anomalía.
6. Guardar hashes/folds/versiones, tiempos, recarga idéntica y scores CSV round-trip.
   Bootstrap pareado AP sobre OOF: incertidumbre descriptiva, no IC de algoritmo
   libre de sesgo (selección, folds solapados, dataset sintético).

La búsqueda completa y umbrales OOF siguen sesgados por selección; no es nested CV
ni evaluación final independiente. Una semilla/fuente no garantiza generalización.
No se entrenan modelos temporales con fechas inventadas ni se usan failure_* o IDs.
Resultados no justifican automáticamente añadir complejidad ni cambiar la API.

Extensión metodológica antes de seleccionar finalistas: nested CV 3 outer ×3 inner
con shortlist fija por cobertura de familias, no por ranking observado:
rf_reference, extra_leaf1, hist_leaf15_None, cat_depth6_None, balanced_rf.
En cada outer se calculan OOF inner, miembro no-RF de mayor AP y mezcla 50/50
con RF; se selecciona entre cinco individuos y mezcla por AP inner y threshold F2
inner. Solo después se predice outer-held. Guardar scores y predicciones con
threshold por outer. Esta auditoría evalúa ese shortlist/procedimiento concreto,
no convierte retrospectivamente toda la búsqueda amplia en nested CV.

Ampliación final del protocolo nested: se incluye TODO el pool prefijado de la
búsqueda amplia, no solo las cinco familias inicialmente propuestas, y las dos
reglas de voting se reconstruyen dentro de cada outer-train. Así la auditoría
incluye GradientBoosting clásico y todas las alternativas, con el coste adicional
de 3 outer ×3 inner por candidato. No se ajustan nuevas configuraciones al ver
resultados outer. Se mantiene el límite: evaluación de desarrollo, no test nuevo.
