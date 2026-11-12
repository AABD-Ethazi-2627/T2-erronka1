# Ajustes tras la revisión de Claude de la v6

El veredicto de Claude corresponde exclusivamente a la v6: utilizable en pantalla, con arreglo necesario antes de imprimir. Esta entrega aplica los cambios concretos restantes; su comprobación posterior corresponde al coordinador, sin atribuir una nueva aprobación a Claude.

| Hallazgo | Cambio |
| --- | --- |
| Impresión omite los desplegables | beforeprint y el cambio de medio de impresión abren todos los details; afterprint restaura el estado previo. El verificador extrae texto del PDF y comprueba 839, 23,5, 4.700 y positivo detectado, además de la restauración de todos los desplegables. |
| Referencia no explícita en la introducción | Para decidir declara que ningún procedimiento A de la matriz base baja de RF@0,15; advierte que eso no demuestra superioridad universal del corte. |
| Nombres mezclados | El simulador identifica RF A y Capacidad identifica RF con corte aprendido según presupuesto; se unifican los nombres de los procedimientos de selección. |
| Procedencia incompleta | calcular-fijo.py declara el CSV de RF de run-01 con hash y copia incluida; sus conteos y el intervalo se recalculan sin entrenar. |
| Proceso caducado | Se incorpora la revisión íntegra de v6 y se distingue del ajuste final local. Los documentos y fallos de v4 se conservan bajo historico/. El constructor ya no sobrescribe LEEME con instrucciones de v4. |
| Opcionales útiles | Escala económica abierta inicialmente; ficha con 23 FP netos menos (38 retirados, 15 añadidos y cero cambios en positivos), derivados de las predicciones; acuerdo 2 avisa de la igualdad base/76/85; G19 pasa a revalidación del alcance por sus imágenes pendientes. |

La prioridad de la rúbrica sigue siendo una propuesta de facilitación por tipo de puerta, no una clasificación cuantitativa del riesgo. La evidencia y reserva original permanecen junto a cada criterio.

Las investigaciones pendientes siguen visibles: datos nuevos autorizados para evaluación independiente, validación cruzada repetida preespecificada para estabilidad, recursos en integración y capacidad real con tasa de llegada y agrupación de episodios. Los actos humanos/docentes siguen pendientes cuando no existe su evidencia.

La verificación local y sus límites se recogen en VERIFICACION.json y verificacion/navegador.json. No acredita servicios vivos, revisión completa de los criterios contra las fuentes, WCAG ni aceptación humana.
