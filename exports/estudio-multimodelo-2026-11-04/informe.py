"""Build a transparent development-only report from the verified extension."""
from pathlib import Path
import base64
import hashlib
import html
import json
import shutil
import zipfile

import numpy as np
import pandas as pd

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
R=P/'run-01'
df=pd.read_csv(R/'procedimientos-anidados.csv')
lb=pd.read_csv(R/'todas-combinaciones.csv')
manifest=json.loads((ROOT/'docs/evidence/CG34_20261023/manifest.json').read_text())
train=pd.read_csv(ROOT/'data/ai4i2020_train.csv',float_precision='round_trip').loc[manifest['membership']['train']]
base=pd.read_csv(R/'single-rf_reference-B-oof.csv',float_precision='round_trip').set_index('source_row_index').sort_index()
candidate=pd.read_csv(R/'selector-pair-B-oof.csv',float_precision='round_trip').set_index('source_row_index').sort_index()
assert base.index.equals(candidate.index) and base.label.equals(candidate.label)
y=base.label.to_numpy();a=base.prediction.to_numpy().astype(bool);b=candidate.prediction.to_numpy().astype(bool)
positives=np.flatnonzero(y);negatives=np.flatnonzero(y==0)
rng=np.random.default_rng(20261104);delta=[]
for _ in range(2000):
 ix=np.r_[rng.choice(positives,len(positives)),rng.choice(negatives,len(negatives))]
 yi,pa,pb=y[ix],a[ix],b[ix]
 ca=5000*np.sum((yi==1)&~pa)+200*np.sum((yi==0)&pa)+300*np.sum((yi==1)&pa)
 cb=5000*np.sum((yi==1)&~pb)+200*np.sum((yi==0)&pb)+300*np.sum((yi==1)&pb)
 delta.append((cb-ca)*1000/len(ix))
ci=np.quantile(delta,[.025,.975]).tolist()
uncertainty={'method':'paired stratified bootstrap, 2000 resamples, fixed OOF predictions, seed20261104; conditional/descriptive only, dependent folds and search multiplicity not covered','challenger_minus_rf_cost_per_1000_95':ci,'improvement_percent':100*(173000-166700)/173000,'rf_missed_recovered':int(np.sum((y==1)&~a&b)),'rf_hits_lost':int(np.sum((y==1)&a&~b)),'false_alarms_removed':int(np.sum((y==0)&a&~b)),'false_alarms_added':int(np.sum((y==0)&~a&b)),'disagreements':int(np.sum(a!=b))}
(R/'incertidumbre.json').write_text(json.dumps(uncertainty,indent=2))
groups=[]
tt=train.loc[base.index]
def segment(name,mask):
 yy,aa,bb=y[mask],a[mask],b[mask]
 groups.append(dict(segment=name,n=int(mask.sum()),positives=int(yy.sum()),rf_fn=int(np.sum((yy==1)&~aa)),pair_fn=int(np.sum((yy==1)&~bb)),rf_fp=int(np.sum((yy==0)&aa)),pair_fp=int(np.sum((yy==0)&bb))))
for typ in sorted(tt.machine_type.unique()): segment('tipo '+typ,(tt.machine_type==typ).to_numpy())
subtypes=[c for c in tt if c.startswith('failure_')]
for col in subtypes: segment(col+' = 1',(tt[col]==1).to_numpy())
segment('positivo sin subtipo marcado',((tt.machine_failure==1)&(tt[subtypes].sum(axis=1)==0)).to_numpy())
segment('positivo con desgaste >= 200',((tt.machine_failure==1)&(tt.tool_wear_min>=200)).to_numpy())
pd.DataFrame(groups).to_csv(R/'errores-por-segmento.csv',index=False)
quality=json.loads((R/'calidad-datos.json').read_text())
quality['distinct_machine_id']=int(train.machine_id.nunique())
quality['target_subtypes_inconsistency_counts']={'negative_with_any_subtype':int(((train.machine_failure==0)&(train[subtypes].sum(axis=1)>0)).sum()),'positive_without_subtype':int(((train.machine_failure==1)&(train[subtypes].sum(axis=1)==0)).sum())}
(R/'calidad-datos.json').write_text(json.dumps(quality,indent=2))
historical=json.loads((ROOT/'docs/evidence/CG34_20261023/business-summary.json').read_text())
for n in ['CG34_EXPLORACION_20261023.md','CG08_ALTERNATIVAS.md','CG34_CLOSEOUT_AUDIT_20261028.json','CG08_smotenc.json']:
 (P/'fuentes').mkdir(exist_ok=True)
 shutil.copy2(ROOT/'docs/evidence'/n,P/'fuentes'/n)
for n in ['business-summary.json','manifest.json','archive.json','summary.json','explanations.json']:
 shutil.copy2(ROOT/'docs/evidence/CG34_20261023'/n,P/'fuentes'/n)
M=[];H=[]
def h(t):M.append('## '+t+'\n');H.append('<h2>'+html.escape(t)+'</h2>')
def p(t):M.append(t+'\n');H.append('<p>'+html.escape(t)+'</p>')
def table(headers,rows):
 M.append('| '+' | '.join(headers)+' |\n| '+' | '.join('---' for x in headers)+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n')
 H.append('<div class="scroll"><table><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in r)+'</tr>' for r in rows)+'</table></div>')
def link(label,target):M.append(f'[{label}]({target})\n');H.append(f'<p><a href="{target}">{html.escape(label)}</a></p>')
def fmt(v):return f'{v:,.2f}'.replace(',',' ').replace('.',',')
h('Comparativa ampliada de modelos · CNC Guard · 04/11/2026')
p('Conclusión: RF sigue siendo una referencia sólida, pero no podemos afirmar que sea la mejor opción en todas las métricas y políticas. La ampliación encuentra mejoras pequeñas con mezclas; todavía no justifica cambiar el modelo servido. El criterio principal combina fallos omitidos y falsas alarmas con los costes del ejercicio. Todo lo siguiente es clasificación del estado actual y evidencia de desarrollo.')
h('1. Qué había y qué faltaba en el material de reunión')
p('CG34 ya comparaba 40 configuraciones supervisadas y 10 de anomalías, con 831 unidades de entrenamiento y calibración. CG08 había probado 19 individuales y dos reglas de mezcla. El dossier de reunión citaba las decisiones, pero no ofrecía una tabla completa que permitiese cuestionar fácilmente RF. Esta adenda incorpora esa comparación y la búsqueda multimodelo que faltaba.')
table(['Cobertura previa','Familias / métodos'],[['CG34 supervisado','RF, GradientBoosting, HistGradientBoosting, logística, CART, Naive Bayes, LDA, QDA, kNN, AdaBoost, CatBoost, XGBoost, LightGBM, EBM, GAM/splines, MLP y constantes de referencia.'],['CG34 anomalías','Isolation Forest, LOF, One-Class SVM, covarianza robusta, PCA y autoencoder; 10 configuraciones. Sin verdad independiente de anomalía.'],['CG08 adicional','ExtraTrees, SVM RBF, BalancedRandomForest, RF calibrado y soft voting; condiciones y métricas distintas, no apiladas como una misma evaluación.'],['Desbalance y representación','Pesos de clase, SMOTENC en experimento separado, features físicas, ablaciones y calibración. Investigar una variante no acredita que esté en la API.']])
h('2. Nueva ejecución: 2.998 configuraciones/reglas por outer')
p('Se han verificado CRC y hash del archivo histórico, el manifiesto y 600 unidades originales inner/outer. Se reutilizan scores OOF auténticos: no se han cargado pickles ni vuelto a ajustar los modelos base. Se han entrenado 54 meta-modelos logísticos nuevos para evaluar stacking. Ejecución local serial, sin dependencias nuevas, sin cambios en API, modelos de entrega, contratos o umbrales operativos.')
table(['Bloque','Configuraciones por outer','Cómo se elige sin mirar sus filas outer-held'],[['Individuales','40','Configuración fija histórica.'],['Pares ponderados','2.340','Todos los pares entre 40; pesos del primer miembro 25/50/75 %.'],['Tres familias','560','Todas las ternas de 16 familias no constantes. Mejor configuración por familia elegida con inner A; mezcla equiponderada.'],['Comités','10','Top2/3/5/8/16 según inner A; pesos iguales o inversos al puesto.'],['Stacking','18','Top3/5/8 según inner A; logística C=0,1/1/10, con/sin balanceo.'],['RF + rareza','30','Diez detectores y colas 1/3/5 % aprendidas sobre negativos inner, como proxy de normalidad; solo diagnóstico.']])
p('Son 8.934 filas de configuración/política: A y B y C para 2.968 candidatos supervisados/ensembles; las 30 uniones de rareza solo tienen su regla binaria propia. El protocolo se guardó antes de calcular resultados, tras conocer los estudios previos. No es un preregistro anterior a toda exploración del dataset.')
p('A optimiza el umbral dentro de outer-train con recall interno mínimo 76 %. B conserva 0,15; C conserva 0,70 como contraste, no reemplaza AVISO. Coste = 5.000 FN + 200 FP + 300 TP. No sumar validación, test y train: esta comparación usa las mismas 5.600 filas de train, 190 positivas, con 3 outer × 3 inner.')
p('Stacking aprende de scores base OOF. Su umbral A se ajusta sobre las salidas del meta-modelo en su propio entrenamiento; la estimación interna puede ser optimista y la evaluación outer mide ese procedimiento. No se presenta como calibración meta-OOF independiente. Las 54 advertencias registradas son deprecaciones de opciones SciPy L-BFGS-B; no son avisos de convergencia. No se han ocultado.')
h('3. Comparación justa: procedimientos elegidos solo dentro de entrenamiento')
p('Cada selector puede escoger miembros distintos en cada outer. Estas filas evalúan procedimientos de selección, no un único ensemble fijo listo para desplegar. Las cifras globales usan 5.600 observaciones; los costes son escenarios del ejercicio, no ahorro observado.')
selected=df[df.policy=='B'].copy()
labels={'single:rf_reference':'RF referencia','selector:single':'Elegir un individual','selector:pair':'Elegir pareja ponderada','selector:triple':'Elegir tres familias','selector:committee':'Elegir comité','selector:stack':'Elegir stacking','selector:all':'Elegir en todo el pool'}
table(['Procedimiento · B (0,15)','TP','FN','FP','Recall','Precision','€/1.000'],[[labels[r['name']],r['tp'],r['fn'],r['fp'],fmt(100*r['recall'])+' %',fmt(100*r['precision'])+' %',fmt(r['cost_per_1000'])] for r in selected.to_dict('records')])
p('La pareja seleccionada reduce el coste de 173.000 a 166.700 € en 5.600 observaciones: 6.300 € hipotéticos, un 3,64 %. Detecta un positivo neto adicional y reduce ocho falsas alarmas. No tiene un 3,64 % más de precisión ni demuestra un 3,64 % de ahorro industrial.')
p(f'Bootstrap pareado condicional de predicciones fijas, 2.000 remuestras: diferencia pareja−RF de coste por 1.000, intervalo descriptivo 95 % [{fmt(ci[0])}, {fmt(ci[1])}] €. Incluye cero. No incorpora toda la variabilidad de entrenamiento, dependencia de folds ni miles de búsquedas; no demuestra superioridad estadística.')
p(f'En los casos concretos, la pareja recupera {uncertainty["rf_missed_recovered"]} positivos omitidos por RF y pierde {uncertainty["rf_hits_lost"]} que RF detectaba; elimina {uncertainty["false_alarms_removed"]} falsas alarmas y añade {uncertainty["false_alarms_added"]}. La diferencia neta no cuenta toda la historia.')
sel=json.loads((R/'seleccion-solo-inner.json').read_text())
table(['Outer','Pareja escogida dentro de ese train para B'],[[v['fold'],v['name']] for v in sel if v['pool']=='pair' and v['policy']=='B'])
p('La inestabilidad de miembros entre tres particiones y la pequeña mejora aconsejan conservar RF como referencia y retener ensembles como candidatos. El selector completo B reduce diez FP pero no FN; el stacking B aumenta tanto FN como FP. Más complejidad no mejora automáticamente el resultado.')
h('4. Cambiar el umbral cambia el ganador')
table(['Procedimiento · A (optimizado)','FN','FP','Recall','€/1.000'],[[labels[r['name']],r['fn'],r['fp'],fmt(100*r['recall'])+' %',fmt(r['cost_per_1000'])] for r in df[df.policy=='A'].to_dict('records')])
p('El selector de tres familias A omite 18 positivos, pero genera 169 falsas alarmas. Frente a RF A mejora algo el coste; frente a RF B genera muchas más revisiones y su coste es mayor. Debe compararse modelo y política conjuntamente. Tampoco se asume que 0,15/0,70 signifiquen probabilidades calibradas iguales para modelos distintos.')
h('5. Mejores filas observadas: diagnóstico, no selección independiente')
for policy in ('A','B'):
 table(['Top observado '+policy,'FN','FP','Recall','€/1.000'],[[r['name'],r['fn'],r['fp'],fmt(100*r['recall'])+' %',fmt(r['cost_per_1000'])] for r in lb[lb.policy==policy].head(5).to_dict('records')])
p('Estos rankings miran los resultados outer después de probar miles de candidatos. Son útiles para formular hipótesis, pero elegir el primero y publicar su cifra como rendimiento esperado introduciría sesgo de selección. No se convierte CART+XGBoost, ni otro ganador observado, en el nuevo modelo servido.')
h('6. Todos los individuales, con políticas comparables')
individual=lb[(lb.category=='single')&(lb.policy=='B')].sort_values(['cost','fn'])
table(['Configuración','FN','FP','Recall','€/1.000'],[[r['name'].removeprefix('single:'),r['fn'],r['fp'],fmt(100*r['recall'])+' %',fmt(r['cost_per_1000'])] for r in individual.to_dict('records')])
p('Para A/C y los detalles por fold, consultar los CSV completos. En el estudio previo, XGBoost depth3 sin pesos con su umbral A obtuvo 30.339 €/1.000 frente a RF A 32.036; con B, RF obtuvo 30.893 frente a XGBoost 32.875. La frase defendible es «RF es una buena elección bajo el contrato y los criterios examinados», no «RF siempre es el mejor».')
h('7. ¿Estamos aprovechando la información disponible?')
p(f'Perfil de las 5.600 filas permitidas: 190 positivos y 5.410 negativos; sin nulos, sin sensores no finitos y sin filas duplicadas en las seis entradas. Hay {quality["distinct_machine_id"]} IDs distintos. Ese identificador no proporciona una trayectoria física por máquina: no se usa para aprender ni para crear ventanas temporales ficticias.')
table(['Información','Tratamiento correcto'],[['Cinco sensores + tipo','Se conservan Kelvin, RPM, Nm y minutos; dashboard puede convertir K a °C sin cambiar el significado.'],['Diferencia térmica','process_temp_K − air_temp_K; misma diferencia numérica en K y °C.'],['Potencia mecánica aproximada','rpm × torque × 2π/60, en W. El factor de conversión importa.'],['Carga combinada','tool_wear_min × torque_Nm en min·Nm; proxy descriptivo, no porcentaje de desgaste.'],['Desbalance','190/5.600 = 3,39 %. Un clasificador siempre negativo tendría accuracy 96,61 % y recall 0 %.'],['Histórico de ingesta','Permite revisar lo observado y cobertura; no aporta por sí solo vida restante ni secuencia causal de degradación.'],['Tipos de fallo etiquetados','TWF/HDF/PWF/OSF/RNF se usan solo en diagnóstico posterior de errores. Son objetivos/resultados, no sensores disponibles para predecir machine_failure.'],['Datos desconocidos','No completar sensores, estados, flota o fechas con valores inventados; advertir fuera de rango y procedencia incompatible.']])
old_summary=json.loads((P/'fuentes/summary.json').read_text())
mods=old_summary['models']
table(['Ablación histórica','AP outer agrupada'],[['RF con derivadas',fmt(mods['rf_reference']['optimized']['average_precision'])],['RF sin derivadas',fmt(mods['rf_no_derived']['optimized']['average_precision'])],['GB con derivadas',fmt(mods['gb_depth3']['optimized']['average_precision'])],['GB sin derivadas',fmt(mods['gb_no_derived']['optimized']['average_precision'])]])
p('Las derivadas deterministas no crean información nueva respecto a los sensores originales, pero hacen más accesibles relaciones físicas para el modelo. La ablación respalda su utilidad en estas particiones. No demuestra causalidad ni que más variables siempre ayuden.')
table(['Segmento observado','Filas','Positivos','FN RF B','FN pareja B','FP RF B','FP pareja B'],[[g['segment'],g['n'],g['positives'],g['rf_fn'],g['pair_fn'],g['rf_fp'],g['pair_fp']] for g in groups])
p('Los modos de fallo pueden solaparse; sus filas no se suman para obtener el total. En segmentos pequeños (por ejemplo H, 13 positivos) las diferencias tienen gran incertidumbre. No se han usado esos diagnósticos para elegir ni cambiar modelos.')
p('El cuello de botella más claro está en TWF: RF omite 16 de 17 casos etiquetados y la pareja 14 de 17. Los seis positivos sin subtipo marcado se omiten con ambos. En contraste, HDF y OSF de esta cohorte se detectan completos. No significa que sepamos detectar siempre esos mecanismos fuera del dataset: identifica dónde hace falta más información o un estudio específico, sin utilizar el subtipo como entrada ni reparar etiquetas por inferencia.')
inc=quality['target_subtypes_inconsistency_counts']
p(f'Consistencia de etiquetas en el train: {inc["negative_with_any_subtype"]} filas negativas contienen algún subtipo marcado y {inc["positive_without_subtype"]} positivas no tienen subtipo marcado. Se preservan las etiquetas y se informa del desacuerdo; no se relabelan para mejorar métricas. RNF tiene un componente aleatorio según la documentación del generador, por lo que no podemos prometer reconstruirlo perfectamente a partir de sensores.')
h('8. Qué falta para predecir mejor con fundamento')
p('Con los datos actuales se puede ampliar representación, ajustar modelos, comparar reglas y mostrar desacuerdo, errores y cobertura. No se puede garantizar que se extrajo el máximo de información posible ni que se predice perfectamente el estado industrial de una máquina. Existe un límite de lo observado: faltan trayectorias físicas fiables, intervenciones y resultados posteriores, y etiquetas industriales independientes.')
table(['Siguiente paso','Qué resolvería','Estado'],[['Confirmar inventario y procedencia SMB','Saber si las filas reales tienen sensores/unidades/identidades compatibles con entrenamiento.','No acreditado por este estudio offline.'],['Histórico físico con identificación estable, contexto de carga y ciclos','Permitir validación temporal, por máquina y evaluación de generalización a nuevas máquinas.','No inventar a partir de row IDs; requiere datos reales nuevos.'],['Etiquetas de avería, mantenimiento y tiempo de operación','Evaluar errores reales y plantear horizonte futuro o RUL con otro objetivo supervisado.','Fuera del contrato actual; no acreditado.'],['Datos complementarios disponibles: vibración/corriente, herramientas, carga','Podrían explicar modos no observables con los seis inputs. Solo incorporar si se miden antes del resultado y están disponibles en inferencia.','Hipótesis de adquisición, no datos existentes ni mejora garantizada.'],['Calibrar y verificar ensemble fijo con datos nuevos','Separar mejora real de la elección entre miles de combinaciones en desarrollo.','No se abre de nuevo el test antiguo inspeccionado.'],['Medir latencia, memoria, serialización y contrato del candidato','Determinar si el pequeño beneficio compensa complejidad operativa.','Esta ejecución no produce ni despliega un paquete ensemble de servicio.']])
h('9. Recomendación y explicación para la reunión')
p('Mensaje para el equipo: «Sí comparamos alternativas y acabamos de ampliar las mezclas. RF no gana siempre. Con las mismas observaciones, elegir una pareja mejora un poco el balance entre errores, pero el margen es incierto y los miembros cambian entre particiones. Conservamos RF como referencia de servicio y documentamos los ensembles como candidatos; no cambiamos el contrato por un ranking de desarrollo».')
p('No se modifica la puntuación académica estimada automáticamente por tener más combinaciones. Esta evidencia fortalece la explicación de G10/G32/G38/G39/G45/G60/G62/G104, pero comprensión individual, interpretación docente, integración y ensayo siguen siendo puertas separadas.')
h('10. Fuentes, reproducción y verificaciones')
for label,target in [('Protocolo anterior a la nueva ejecución','protocol.json'),('Código de la ampliación','estudio.py'),('Auditoría por cálculo distinto','verificar.py'),('Resultados de verificación','run-01/VERIFICACION.json'),('Todos los candidatos y políticas','run-01/todas-combinaciones.csv'),('Procedimientos anidados','run-01/procedimientos-anidados.csv'),('Miembros escogidos solo con inner','run-01/seleccion-solo-inner.json'),('Perfil de datos','run-01/calidad-datos.json'),('Incertidumbre','run-01/incertidumbre.json'),('Estudio histórico CG34','fuentes/CG34_EXPLORACION_20261023.md'),('Estudio histórico CG08','fuentes/CG08_ALTERNATIVAS.md')]:link(label,target)
p('Repetir desde la raíz del repositorio, con el entorno existente: OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python exports/estudio-multimodelo-2026-11-04/estudio.py --output /ruta/nueva. La salida debe ser nueva; el input original permanece intacto. No se usa red al entrenar meta-modelos. El hash del archivo de evidencia es 640d75114324df4d8bafa20461cccf20da3850552c3bd6fa48080b9584e97896; base Git c34cabe.')
H.append('<p>Metodología: <a href="https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html">scikit-learn: stacking</a>; <a href="https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html">selección anidada</a>. Fuente del dataset: <a href="https://archive.ics.uci.edu/dataset/601/ai4i%2B2020%2Bpredictive%2Bmaintenance%2Bdataset">UCI AI4I</a>. No se descarga ni incorpora el dataset original completo.</p>')
M.append('Metodología: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html y https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html. Dataset: https://archive.ics.uci.edu/dataset/601/ai4i%2B2020%2Bpredictive%2Bmaintenance%2Bdataset\n')
(P/'COMPARATIVA.md').write_text('\n'.join(M))
css='body{font:17px/1.6 system-ui;color:#173047;background:#f3f7fb;margin:0}main{max-width:1120px;margin:auto;padding:35px}h2{border-top:3px solid #129c98;padding-top:15px;margin-top:45px}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{border:1px solid #cbd7e0;padding:10px;text-align:left;vertical-align:top}th{background:#193b52;color:white}.scroll{overflow-x:auto}a{color:#007b87}p{max-width:100ch}@media(max-width:600px){main{padding:16px}table{min-width:620px}}@media print{body{background:white;font-size:10pt}main{padding:0}table{font-size:8pt}tr{break-inside:avoid}h2{break-after:avoid}.scroll{overflow:visible}}'
(P/'COMPARATIVA.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CNC Guard: modelos y ensembles</title><style>'+css+'</style><main>'+''.join(H)+'</main></html>')
print(json.dumps(uncertainty));print(pd.DataFrame(groups).to_string(index=False))
