"""Build a self-contained meeting report; embedded reviewed data, no network."""
from pathlib import Path
import json,csv,base64,hashlib,shutil
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
OLD=ROOT/'exports/sincronizacion-2026-11-04-v3'
ST=ROOT/'exports/estudio-multimodelo-2026-11-04'
def read(p):return json.loads(p.read_text())
def records(p):return pd.read_csv(p).to_dict('records')
def asset(name):return 'data:image/png;base64,'+base64.b64encode((OLD/'imagenes'/name).read_bytes()).decode()
services=[
['01-smb','SMB y captura','El buzón de archivos','Sistemas','CSV compartido → copia local completa.','Preservar el origen y su procedencia; la aceptación de un lote nuevo desde SMB sigue separada de las pruebas locales.','S04'],
['02-filebeat','Filebeat','El mensajero','Sistemas','CSV local → Kafka; registry recuerda la lectura.','Un ACK del productor acredita recepción por Kafka, no scoring ni archivo terminado.','S04'],
['03-kafka','Kafka','La sala de espera','Sistemas + dev','Cola de eventos → consumidor; offsets identifican la posición.','Amortigua diferencias de ritmo. Mononodo no aporta alta disponibilidad.','S05'],
['04-nifi','NiFi','El coordinador de ciclos','Sistemas','Trigger periódico → ejecución del worker y diagnóstico.','La vía documentada usa ExecuteStreamCommand; no afirmar ConsumeKafka/InvokeHTTP nativos ejecutados.','S05'],
['05-worker','Worker durable','El repartidor con recibos','Dev + sistemas','Consume → valida → scoring → destinos → commit del offset.','Exige recibos antes de confirmar. Replay idempotente no equivale a exactly-once distribuido.','S05'],
['06-modelo','RF y modelos de rareza','El clasificador y el detector de casos raros','ML/LLM + dev','Cinco sensores y tipo → score de estado actual; rareza separada.','El LLM apoya el trabajo del equipo; no es el modelo que puntúa las observaciones.','S14'],
['07-api','FastAPI','La ventanilla común','Dev','POST valida y conserva respuesta canónica; GET opcional consulta.','409 conflicto, 422 entrada inválida, 503 indisponibilidad. Esta página no consulta el servicio vivo.','S12'],
['08-archivo','CG15, SQLite, Parquet y DuckDB','El archivo y su catálogo','Dev + sistemas','Recibos y objetos comprometidos → histórico verificable.','GET no repara archivos; la migración del índice antiguo es explícita y offline.','S12'],
['09-es','Elasticsearch','El índice de consulta','Sistemas + dev','Eventos canónicos → búsquedas y agregaciones con ámbito.','Separar fuentes/modelos/políticas; una caída se comunica como degradación.','S12'],
['10-kibana','Kibana','El panel de análisis','Dashboard + sistemas','Consultas ES → filtros y visualizaciones CG19.','Sus evidencias históricas conservan su identidad; Laneki no sustituye automáticamente estos entregables.','S02'],
['11-laneki','Laneki / Streamlit','El panel para comunicar el estado','Dashboard + dev','GET canónicos → observación, detalle, histórico, cobertura y avisos.','Demo, API demo e integración canónica tienen evidencia distinta. No crear series o máquinas por ID.','S10'],
['12-entorno','Docker y acceso','Las cajas y las llaves','Sistemas','Imágenes fijadas, montajes, límites y acceso local/LAN.','Build, escaneo, ejecución local, integración completa y aceptación humana son estados separados.','S19']]
svc=[]
for slug,name,analogy,owner,flow,limit,source in services:svc.append(dict(name=name,analogy=analogy,owner=owner,flow=flow,limit=limit,source=source,image=asset(slug+'.png')))
captures=[dict(name='Laneki: detalle',image=asset('laneki-detalle.png'),caption='03/11, imagen local, CSV sintético y modelo de prueba; caso visible documentado en S10.'),dict(name='Laneki: escritorio',image=asset('laneki-escritorio.png'),caption='03/11, procedencia e identidad del evento en el ensayo local de imagen. No pantalla de máquinas industriales. S10.'),dict(name='Laneki: histórico',image=asset('laneki-historico.png'),caption='Seleccionar seis meses no prueba seis meses de cobertura. Ensayo local, S10.'),dict(name='Laneki: móvil',image=asset('laneki-movil.png'),caption='Ensayo local 390 × 844. No prueba acceso SMB ni aceptación humana. S10.'),dict(name='Kibana: histórico',image=asset('kibana-historico.png'),caption='CG20, 22/10, recorrido histórico con RiskDouble/AnomalyDouble. No es RF industrial ni captura nueva. S02.')]
base=pd.read_csv(ST/'run-01/single-rf_reference-A-oof.csv',float_precision='round_trip').set_index('source_row_index').sort_index()
pair=pd.read_csv(ST/'run-01/selector-pair-A-oof.csv',float_precision='round_trip').set_index('source_row_index').sort_index()
train=pd.read_csv(ROOT/'data/ai4i2020_train.csv',float_precision='round_trip').loc[base.index]
cases=[]
for title,mask in [('Fallo omitido por ambos',(base.label==1)&(base.prediction==0)&(pair.prediction==0)),('Recuperado por la pareja',(base.label==1)&(base.prediction==0)&(pair.prediction==1)),('Lo detecta RF y lo omite la pareja',(base.label==1)&(base.prediction==1)&(pair.prediction==0)),('Aviso innecesario de la pareja',(base.label==0)&(pair.prediction==1))]:
 if not mask.any():continue
 idx=int(base.index[mask][0]);x=train.loc[idx];a=base.loc[idx];b=pair.loc[idx]
 cases.append(dict(title=title,row=idx,fold=int(a.fold)+1,label=int(a.label),rf_score=float(a.score),rf_cut=float(a.threshold),rf_prediction=int(a.prediction),pair_score=float(b.score),pair_cut=float(b.threshold),pair_prediction=int(b.prediction),sensors={c:str(x[c]) for c in ['machine_type','air_temp_K','process_temp_K','rpm','torque_Nm','tool_wear_min']},subtypes=[c.removeprefix('failure_') for c in train.columns if c.startswith('failure_') and x[c]==1]))
primary=records(ST/'run-01/procedimientos-anidados.csv')
for r in primary:r['marked_per_1000']=(r['tp']+r['fp'])*1000/r['n']
rub=records(OLD/'valoracion-40-criterios.csv')
areas={'ML':['G5','G10','G14','G23','G24','G31','G32','G36','G38','G39','G45','G60','G61','G62'], 'Sistemas':['G19','G41','G46','G49','G68','G77','G80','G85','G90','G92','G95','G96'],'Dashboard':['G65','G66','G71','G72','G87','G100','G101','G104','G105'],'PM':['G16','G17','G20','G52','G55']}
for r in rub:r['area']=next((k for k,v in areas.items() if r['celda'] in v),'Compartido')
summary=read(ST/'fuentes/summary.json')['models']
data=dict(methods=primary,scenarios=read(ST/'sensibilidad/protocolo.json')['scenarios'],sensitivity=records(ST/'sensibilidad/resultados.csv'),selections=read(ST/'sensibilidad/selecciones.json'),budget=read(ST/'capacidad/resultados.json'),uncertainty=read(ST/'capacidad/incertidumbre-A.json'),quality=read(ST/'run-01/calidad-datos.json'),rubric=rub,originalRubric=read(OLD/'fuentes/S01-fuente.json'),services=svc,captures=captures,architecture=asset('00-arquitectura.png'),cases=cases,source_status=read(OUT/'fuentes/pr119-corte.json'),artifact=read(ST/'candidato/manifest.json'),ablation=[dict(model=n,with_features=summary[a]['optimized']['average_precision'],without_features=summary[b]['optimized']['average_precision']) for n,a,b in [('RF','rf_reference','rf_no_derived'),('GradientBoosting','gb_depth3','gb_no_derived')]])

# Facilitation statuses derived from the documentary limits, not human acceptance.
for r in data['rubric']:
    if r['celda'] in ['G49','G62','G92']:
        r['documentary_status']='Interpretación docente pendiente'
        r['priority']='Alta'
    elif r['celda'] in ['G5','G10','G14','G23','G24','G31','G32','G39','G45','G60','G61','G65','G71','G72','G85','G87','G104','G105']:
        r['documentary_status']='Explicación o ensayo humano pendiente'
        r['priority']='Alta'
    elif r['celda'] in ['G41','G46','G66','G77','G80','G90','G96']:
        r['documentary_status']='Revalidar alcance para la versión del ensayo'
        r['priority']='Alta'
    else:
        r['documentary_status']='Evidencia documental disponible; sin cierre humano nuevo'
        r['priority']='Media'
data['fixed_postselection']=read(OUT/'fuentes/fijo-postseleccion.json')

template=(OUT/'plantilla.html').read_text()
payload=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
(OUT/'reunion.html').write_text(template.replace('/*__DATA__*/',payload))
(OUT/'datos-revisados.json').write_text(json.dumps({k:v for k,v in data.items() if k not in ['services','captures','architecture']},ensure_ascii=False,indent=2))
copy=[ST/'capacidad/protocolo.json',ST/'capacidad/resultados.json',ST/'capacidad/incertidumbre-A.json',ST/'capacidad/VERIFICACION.json',ST/'capacidad/ejecucion.json',ST/'capacidad.py']
for f in copy:shutil.copy2(f,OUT/'fuentes'/('capacidad-'+f.name))
for f in [ST/'sensibilidad/protocolo.json',ST/'sensibilidad/resultados.csv',ST/'sensibilidad/selecciones.json']:shutil.copy2(f,OUT/'fuentes'/('sensibilidad-'+f.name))
for f in [ST/'run-01/procedimientos-anidados.csv',ST/'run-01/calidad-datos.json',OLD/'valoracion-40-criterios.csv',OLD/'fuentes/S01-fuente.json',ST/'candidato/manifest.json']:shutil.copy2(f,OUT/'fuentes'/f.name)
(OUT/'LEEME.md').write_text('''# Reunión CNC Guard v4

Abrir reunion.html. Es un único HTML offline, con datos, imágenes y código embebidos; no consulta servicios, no envía datos y no necesita servidor ni librerías externas. Los controles exploran resultados ejecutados. El simulador de costes revalora decisiones congeladas: no reentrena ni vuelve a optimizar.

Modo breve para conducir la reunión; detalle para modelos, escenarios, capacidad, variables, casos y rúbrica. Exportar acuerdos descarga un borrador que rellena la persona; no prueba asistencia ni aprobación.

datos-revisados.json y fuentes/ conservan números y procedencia. El dataset y el ZIP histórico de 49 MiB se requieren desde el repositorio para repetir el análisis original. La HTML muestra exactamente qué está disponible y qué no. El presupuesto se mide en observaciones marcadas por 1.000, no inspecciones por hora.

No hay nueva evaluación en las 1.200 filas de validación reutilizada ni en las 1.200 excluidas, ni despliegue o cambios de API. El análisis de capacidad y los intervalos A añaden información; no demuestran un mejor modelo industrial. La estimación académica es orientativa y secundaria.
''')
print('Built standalone HTML', (OUT/'reunion.html').stat().st_size, 'bytes')
