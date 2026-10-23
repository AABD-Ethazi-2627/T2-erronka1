# Continuidad CNC Guard: estudio ejecutado

Estado al 23/10/2026: no hay experimento activo. Trabajo en worktree T3
`kali/ml-alternatives-kalista-study`, base remota verificada
`41cb66f0f3a967bcc4e72c6e251586898edceee9`. No usar el checkout Linux antiguo.

Raíz local: `D:/cnc-guard-research/study-20261023-v2`.
Entorno: `D:/cnc-guard-research/venv-20261023/Scripts/python.exe`.
Fuentes de fit selladas en `e644737` y conservadas en `sealed-code/`.
Manifiesto: `d881aa24d43a1f44e98956c37a4e88cacb21989a1fe0c205ed9e8d67aa72187b`.

Completados: piloto8, screening150, nested600, calibración72, refit1: 831 unidades.
Sin puntuar validación reutilizada ni test excluido. Sin cambio del modelo servido.
Consumo acumulado 1,427684 CPU-h y 0,038558 GPU-h. No hay necesidad de más fits.

Análisis inicial en `analysis-v2`; matriz docente recibida después en
`analysis-business-v1`. No reemplazar uno con otro. Ambos eligen RF como
especificación fija; la matriz docente cambia el selector pool40 a AdaBoost/RF/RF.
Recomendación final: conservar RF y 0,15/0,70. Ver informe CG34 y registro de ejecución.

Archivos originales de evidencia y añadido docente tienen hashes/CRC completos.
173 artefactos CPU recargados con diferencia cero. Pruebas16 y smoke50 pasan;
lint/formato, estructura, CG25, catálogo y lock comprobados localmente.
El runner actual incorpora correcciones de serialización/estilo posteriores;
no permite reanudar el sello histórico con bytes diferentes. No repetir unidades.

Rama publicada y [PR #90](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/90)
abierto, revisable y enlazado a este hilo T3. Commit de implementación/evidencia:
`ddb0386ab907256712c2dbc32429c164697073e1`.
Las tres CI pasan en ese commit: ML research smoke, Repository layout y Validate
CNC Guard. El último commit documental tiene su estado propio en el PR.
#83 actualizado con ejecución, GPU y matriz docente; comentarios #84–#89 y
#80–#82 publicados y verificados. Referencias en `CG34_20261023/feedback.json`.
No se cerraron issues ni se cambiaron responsables/fechas del Project.
No hacer merge o desplegar. Revisión humana, integración, HTTP/E2E y aceptación
permanecen pendientes; no se necesitan más fits para reproducir la recomendación.

Última instrucción: probar ZIP adjunto sin columnas de error en X. Ejecutado en
`D:/cnc-guard-research/batch-eval-20261023-v1`: 507 CSV, 5.070 eventos/2.000 únicos,
sin coincidencias exactas con las 8.000 anteriores. RF final: TP58/FN10/FP20 en
únicos al corte0,15; recall85,29%, precision74,36%. Inferencia de151artefactos
terminada sin avisos, sin ajustes. 22pruebas y auditor aritmético pasan.
Datos/etiquetas/predicciones locales; solo código/agregados para PR90.
Ver `runs/20261023-batch.md`; no repetir `run` sobre esa salida exclusiva.
