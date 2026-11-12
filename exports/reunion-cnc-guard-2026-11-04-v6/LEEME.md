# Reunión CNC Guard v6 — cierre completo y verificable del feedback

Abrir reunion.html. Datos, imágenes y controles funcionan offline. CLAUDE_SOBRE_V4.md conserva la revisión original; CIERRE_FEEDBACK.md relaciona cada hallazgo H1–H7 con su corrección y sus reservas. Claude no ha emitido todavía un veredicto de esta v6.

La v5 incorporó buena parte de los cambios, pero dejó incompleta la ficha del candidato fijo y el estado/prioridad de la rúbrica. Esta v6 añade ambos, zoom de imágenes, comprobación de impresión y trazabilidad de cierre.

La nueva ficha histórica usa scores OOF originales de CART/LightGBM 75/25 a 0,15 después de seleccionar su configuración entre 2.340 parejas. Su intervalo es condicional y post-selección; no evalúa el paquete refiteado ni prueba una ventaja independiente. El código y el JSON de procedencia están incluidos.

VERIFICACION.json recoge comprobaciones del coordinador. verificacion/ contiene el resultado del navegador y capturas; impresion-prueba.pdf es una prueba técnica de impresión, no una entrega oficial. Los ficheros descargados durante pruebas están marcados como prueba, no como acta.

Las versiones v4 y v5 quedan preservadas. No hay entrenamiento nuevo, cambios en la API/modelos, fuentes externas nuevas ni uso de validación/test excluidos. Los trabajos de investigación o aceptación que requieren datos/actos nuevos permanecen separados de las correcciones del informe.
