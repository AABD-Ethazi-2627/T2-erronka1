# Cierre trazable del feedback de Claude sobre v4

La v5 incorporó H1–H5 y una parte de H6/H7. Presentar el feedback como aplicado sin destacar esa diferencia fue un cierre incompleto. Esta v6 completa las correcciones de información e interfaz pendientes. La aprobación de Claude no se presupone: debe comprobar después esta versión.

| Hallazgo | Corrección verificable en el HTML | Situación |
| --- | --- | --- |
| H1, referencia de comparación | Modelos: RF@0,15 visible junto a RF de corte aprendido y selectores; ambos puntos se nombran y la fila fija no finge satisfacer cada restricción | Implementado; referencia histórica, no óptimo universal |
| H2, sesgo visual hacia la pareja | Costes en paralelo, colores neutrales, escala económica y sensibilidad de 839 €/1.000 por un FN→TP | Implementado |
| H3, etiquetas y signo | Coste del escenario; intervalos de mayor coste con dirección y advertencia; procedimiento separado de artefacto | Implementado |
| H4, restricción no activa | Capacidad explica igualdad base/sin mínimo/85 %, cambio de FP con presupuesto 50 y vínculo G45 | Implementado; sin causalidad o superioridad asumida |
| H5, lenguaje y economía | Glosario TP/FP/FN/TN, RF, AP, A/B/C; 4.700 € y equilibrio 23,5 FP/TP; hashes en Fuentes | Implementado |
| H6, candidato fijo y promoción | Ficha cuantitativa a 0,15 e intervalo propio de la configuración histórica, explícitamente post-selección; paquete refiteado separado; puerta concreta de datos nuevos/política/margen/recursos | Implementado como información; evaluación independiente pendiente de datos nuevos |
| H7, rúbrica | Estado documental y prioridad propuesta en 40 criterios; criterios por acuerdo; puertas prioritarias; media histórica en detalle y literal H5 pendiente A02 | Implementado; no acta ni aceptación nueva |

Opcionales incorporados: ampliación de mapa/fichas/capturas, nota de límites de AP agrupada, avisos de que escenarios/presupuestos carecen de intervalos propios, y ficha post-selección del candidato. Se comprueba también impresión y Acuerdos en navegador.

Trabajos de investigación y aceptación que NO se confunden con correcciones del informe:

- El bootstrap del candidato es sobre scores históricos fijos y no corrige su selección entre 2.340 parejas. No evalúa los nuevos bytes de ensemble.joblib.
- Validación cruzada repetida preespecificada sobre train, para estabilidad de configuraciones fijas: propuesta de experimento; no ejecutada ni presentada como nueva evaluación independiente.
- Latencia/memoria en el recorrido integrado y aceptación humana/docente: requieren sus ensayos y actos propios; no se fabrican aquí.
- Datos nuevos autorizados sin solapamiento: no constan disponibles para cerrar ahora la evaluación independiente. No se descarga ni admite por inferencia el resto del AI4I público.
- No se asumen las estimaciones de potencia o tamaños muestrales de la review como cifras verificadas. La mejora externa bajo una restricción puede reflejar regularización/variabilidad; no prueba por sí sola ruido puro ni mejora garantizada.

El feedback original de Claude sobre v4 permanece íntegro en CLAUDE_SOBRE_V4.md. El estado de esta tabla describe correcciones del coordinador y debe contrastarse con la verificación y la posterior respuesta de Claude.

Comprobación del coordinador: 80 controles de Chromium en escritorio/móvil, ficha histórica con corte y conteos comprobados contra la fuente, 40 estados/prioridades, zoom, intervalos con dirección correcta, descargas e impresión. Capturas de la ficha, rúbrica, zoom y Acuerdos incluidas. No es una auditoría WCAG completa. Revisión de cierre por Claude pendiente.
