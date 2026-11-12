# Comparativa y candidato multimodelo de CNC Guard

Abrir COMPARATIVA.html. Resume los resultados previos y la ampliación ejecutada, con métricas, selección, incertidumbre, datos y límites.

El paquete es investigación local, no un despliegue ni un modelo industrial aprobado. Incluye un candidato CART/LightGBM ajustado para puntuar seis entradas, con ejemplo y manifest. Sus scores no son probabilidades futuras calibradas. La API del proyecto permanece intacta.

Los scripts se ejecutan desde el checkout del repositorio, con este directorio bajo exports/estudio-multimodelo-2026-11-04. El bundle de resultados no incluye los 49 MiB del archivo histórico original; se requiere docs/evidence/CG34_20261023/raw-evidence.zip del repositorio, fijado por hash. No mueve, puntúa o entrena con las 1.200 filas de validación reutilizada ni las 1.200 del test excluido.

estudio.py ejecuta los 2.998 candidatos/procedimientos; verificar.py recalcula conteos y mínimos de selección por otra vía; seleccionar_candidato.py reproduce el ranking screening para el candidato fijo; candidato.py ofrece fit/predict; informe.py conserva el generador del cuerpo analítico previo a la adenda final. Las adendas y el gráfico son documentación adicional, no resultados distintos de la misma ejecución.

El comando local de inferencia ejecutado utiliza PYTHONPATH=/home/tears/.cache/cnc-ml-candidate-20261104/lightgbm con .venv/bin/python candidato.py predict (rutas desde la raíz del repositorio). La alternativa portátil documentada en COMPARATIVA.md prepara un entorno uv separado con requirements-candidato.txt y no se ha ejecutado en esta revisión.

Solo cargar el propio ensemble.joblib tras verificar el manifiesto; joblib no es un formato seguro para archivos de terceros. Conservar el código original de scoring/preparation.py, scoring/scope.py y scripts/ml_study_models.py: el candidato rechaza cambios de sus hashes o versiones científicas.

Los scripts no publican, despliegan ni envían datos. Los outputs son locales y rechazan sobrescritura. Para repetir estudio.py, elegir --output nuevo. Los originales y la API no se modifican.
