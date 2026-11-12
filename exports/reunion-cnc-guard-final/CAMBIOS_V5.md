# Respuesta del coordinador al feedback de Claude sobre v4

Claude calificó la v4 como necesita cambios: rigor 7/10, claridad 6/10, utilidad de reunión 7/10. No ha evaluado ni aprobado esta v5. El feedback original está en CLAUDE_SOBRE_V4.md; el HTML v4 y su hash se conservan.

Cambios aplicados sin entrenar ni modificar datos, API o modelos:

- H1: RF@0,15 vuelve al modo breve como contraste histórico. La optimización de A conserva libertad para elegir corte; se nombran explícitamente ambas referencias. La fila fija se revalora con la matriz de cada escenario, sin fingir que se volvió a optimizar o cumple cada restricción.
- H2: se elimina el color preferente de la pareja. Los indicadores muestran costes de RF histórico, RF A y selección de pareja A en paralelo. Se añade la escala económica y que un cambio FN→TP mueve unos 839 €/1.000 frente a una diferencia media de 250 €/1.000 entre pareja A y RF A.
- H3: los costes hipotéticos se etiquetan como costes del escenario. Un intervalo de mayor coste usa advertencia y dirección explícita. En estabilidad se utiliza procedimiento/selección, separadamente del candidato fijo.
- H4: se explicita que base/sin mínimo/85 % dan las mismas decisiones y que RF con presupuesto 50 reduce 45 FP sin perder TP en estas particiones. Se vincula el 76 % al literal G45; los 1.200 €/h históricos no sustituyen la matriz docente vigente.
- H5: se recuperan TP/FP/FN/TN, RF, AP, A/B/C y el equilibrio marginal 23,5 FP por TP. Los hashes se desplazan a Fuentes.
- H6: el candidato fijo queda identificado con su referencia 0,15 y sus pruebas de funcionamiento. La puerta de promoción pide un modelo/política y margen acordados previamente, observaciones nuevas autorizadas y sin solapamiento, métrica de coste, volumen de marcas y recursos. Sin datos nuevos no hay evaluación independiente ejecutable ahora.
- H7 parcial: cada acuerdo indica criterios de rúbrica; se destacan G49/G62/G92 y las puertas de explicación humana. El literal H5 15%% sigue pendiente en A02. No se inventan estados cerrados ni nota docente.

Reservas que se mantienen:

- Los intervalos son condicionales sobre predicciones fijas. Escenarios y presupuestos no tienen intervalos propios y no heredan los de A.
- No se añaden estimaciones de tamaño muestral ni las 2.000 filas públicas como solución: las primeras requieren supuestos fuertes, y la disponibilidad/autorización/independencia de otras filas no se ha verificado.
- Que una restricción reduzca coste externo es compatible con variabilidad o regularización; no prueba por sí solo que toda la mejora sea ruido, ni que restringir siempre mejore. No se adopta esa afirmación absoluta del feedback.
- No se repite la búsqueda masiva. Validación cruzada repetida con configuraciones fijas y un protocolo previo sería desarrollo adicional útil para estudiar estabilidad, no test independiente ni aprobación industrial.

La verificación de v5 corresponde al coordinador. El veredicto y las puntuaciones de Claude siguen correspondiendo exclusivamente a v4.
