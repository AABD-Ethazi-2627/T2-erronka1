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

Publicación de rama/PR y comentarios de issues pendiente en este punto de cierre.
No hacer merge, desplegar ni modificar Project/fechas. Registrar URL del PR en T3.
Separar CI y revisión humana de estas comprobaciones locales.
