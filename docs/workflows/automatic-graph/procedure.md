# Procedimiento del grafo automático

Usar [el protocolo operativo](../../CG14_AUTOMATIC_GRAPH.md). No ejecutar los
labs históricos que creaban temporales en capas ni tocar recursos previos.
Registrar base/head/tree, inventario anterior/posterior y namespace/grupo/IDs.

1. Revisar contrato API, recibos CG15 y configuración ES integrada.
2. Regenerar export a fichero nuevo y cotejar con fuente. Ejecutar regresiones
   focales con temporales/cachés bajo el taskroot propio.
3. Laboratorio propio con imágenes locales `--pull=never`, puertos aleatorios
   loopback y binds D: para datos, metadata y runtime. No driver que confirme
   offsets. Conservar journals, configs, exports, logs e inventario.
4. Ensayar entrega Filebeat, errores/retry automáticos, reinicio y contabilidad;
   separar controles simulados HTTP de respuestas generadas por el API real.
5. Ruff0.17.1, formato, CG02, CG25, layout, lock y audit; actionlint si aplica.
6. Revisar diff/compatibilidad, integrar main normalmente, push normal y draft
   nueva contra main; enlazar a T3. PR42 ya está integrada y cerrada.
   No merge/comments/CI manual/watch/poll. Revisión del padre pendiente.
