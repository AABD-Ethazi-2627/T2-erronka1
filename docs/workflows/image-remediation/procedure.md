# Procedimiento de remediación de imágenes

1. Descargar los artefactos JSON de Trivy del último commit de CI.
2. Clasificar cada diagnóstico por imagen, paquete, versión instalada y versión corregida.
3. Cambiar únicamente a referencias oficiales inmutables o reconstrucciones reproducibles.
4. Mantener el escaneo de todas las severidades y de vulnerabilidades sin corrección.
5. Ejecutar inventario, pruebas focalizadas, suite completa y escaneos nuevos.
6. No aceptar ni fusionar mientras quede un diagnóstico sin resolver.
