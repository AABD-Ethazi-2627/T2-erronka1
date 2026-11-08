# Cierre integrado local — 8 de noviembre de 2026

El candidato `5176fe8` completa el recorrido real Filebeat → Kafka → NiFi → API
→ archivo canónico/Elasticsearch → GET → dashboard. Esta prueba local no
acredita producción, SMB físico, aceptación industrial del modelo ni CI final.

## Resultado medido

Proyecto propio `cg32-bbf35ca8`, run `closeout-final-r1-3b2291`. Preflight
6 GiB RAM y 20 GiB disco respetado. Se reutilizan las siete imágenes finales
con identidad de contenido comprobada en
[IMAGE_TRANSFER_20261108.json](IMAGE_TRANSFER_20261108.json), sin reconstruir
ni cambiar sus dependencias. Bundle entrenado localmente, identidad explícita
`rebuilt_candidate`, sin descargar pickle de terceros.

Se ofrecieron seis eventos a 1/s: seis registros Kafka, seis trabajos guardados,
seis documentos ES, cero duplicados, pérdidas, pendientes, rechazados o trabajos
sin correspondencia. Las seis peticiones HTTP respondieron 200; lag final cero.
NiFi completó tres ciclos con salida 0. No hubo errores de observador,
controlador ni limpieza, ni parada por presupuesto. Latencia HTTP p95 42,86 ms;
E2E p95 15,88 s, incluyendo scheduling y drenaje. Este lote pequeño no prueba
capacidad sostenida ni un SLA.

El evento seleccionado
`a416cdc2a853cb9a6b328051af51e16e87b6af117b1d515abf7f663973a4f481`
de `CNC-009` es idéntico en almacenamiento canónico, recibo Parquet, ES,
snapshot GET e histórico. SHA256 canónico
`5a5ca7c0059ee48d9f83ba7f1d3805a96f9c232fc843495ff235822ea6d545dc`.

## Navegador y preservación

Tras parar la ingestión, otro preflight pasó antes de iniciar únicamente ES,
API y dashboard propios. Se comprobó la identidad exacta de sus imágenes y
los imports dentro de las imágenes, incluido Streamlit 1.66.1. Se usó el
overlay mantenido de `IntegrationLab`, con bundle/manifest y montajes de archivo
de solo lectura verificados; no se construyeron imágenes durante esta fase.

Edge/Chromium mediante Playwright CLI: pausa de actualización desde su etiqueta
visible, navegación Hasiera → Datuak → Sei hilabete y origen expandido. El DOM
contiene el evento exacto, máquina, timestamp, valores y procedencia del mismo
run. El rango inicial de un día estaba vacío correctamente: los fixtures son
del 23 de octubre, no observaciones actuales. No se falsearon timestamps para
rellenar el histórico. En 1440×1000 y 390×844 se capturaron snapshots e imágenes;
en móvil, documento y viewport miden 390 px, sin desbordamiento horizontal.
Consola: cero errores y warnings. Se mantuvieron visibles los límites de
prototipo/AI4I, sin presentarlo como CNC físico.

Dos intentos de automatización no son defectos del producto: clicar el input
interno de Streamlit falló por la capa visual; su etiqueta visible funcionó.
Un ref anterior al cambio de viewport quedó obsoleto; se renovó el snapshot
y se usó el control actual. No se aplicó force-click ni se alteró el DOM.

Navegador cerrado y todos los contenedores del proyecto parados; no se borraron
volúmenes, datos, ledgers, offsets ni archivos. El laboratorio sigue bajo
`/home/Fedora/.cache/cnc-closeout-20261108/e2e-final-20261108`.
Crudos seleccionados copiados a `outputs/closeout-e2e/`; capturas en
`output/playwright/`. El [JSON compacto](INTEGRATION_CLOSEOUT_20261108.json)
fija sus hashes y el recibo del run original, sin editar ese recibo para
atribuirle retroactivamente la comprobación de navegador.

## Revisiones y gates restantes

Muse NiFi v6: cero findings sobre `691b61c`/`eaee9ad`/`5176fe8`, con rehash de
los scans, todas las pruebas compactas y suite AWS 1445/0/0/0. El padre ejecutó
la regresión conjunta: 1382 tests y 497 subtests, 5 skips, dos warnings esperados
de fixtures ZIP negativos. Muse también cerró sin findings ES/Kibana, Filebeat
y control LAN; sus alcances no equivalen a aprobación GitHub.

Pendientes para integrar: corrección oficial del gateway HAProxy/zlib y fallos
auxiliares, revisión del delta que corresponda y CI sobre el SHA final publicado.
No se ha fusionado ni desplegado el PR119. No hay nuevas excepciones del gate.
