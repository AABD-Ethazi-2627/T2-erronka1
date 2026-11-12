# Revisión del informe v4

Compartible con reservas. Se corrigieron problemas de interpretación y uso mediante revisión metodológica independiente y revisión de preparación de reunión; el coordinador comprobó las fuentes y el resultado combinado.

| Hallazgo | Corrección verificable |
| --- | --- |
| El intervalo previo era para B, pero el informe principal comparaba A | Se calcularon intervalos A propios para seis comparadores, con costes y AP por partición. La HTML los liga a A y describe sus límites condicionales. |
| Capacidad nombrada sin presupuesto calculado | Se añadió selección interna con presupuestos 10/20/30/50/100 observaciones marcadas por 1.000 y recall interno mínimo 76 %. Se suprimen totales si falta una partición. |
| Volumen de FP no representa todo el trabajo | Se muestra TP+FP y se impide su interpretación como inspecciones/hora o máquinas únicas sin información adicional. |
| Candidato fijo podía heredar cifras de selectores variables | Se distinguen referencia documental, procedimientos variables, candidato ajustado y servicio vivo no consultado. |
| Variables y etiquetas quedaban ocultas | Se muestran ablaciones RF/GB, casos con seis entradas y las 8 negativas con subtipo / 6 positivas sin subtipo. |
| La nota con decimales dominaba sin pesos completos | Se priorizan las puertas de evidencia y una banda orientativa; la media histórica pasa al detalle. |
| Jerga y tablas dificultaban conducir la reunión | Tres acuerdos propuestos, glosario inicial, modo breve/detalle, fuentes junto a cifras y borrador descargable. |

Verificación: restricciones y cuatro costes recalculados; navegador real Chromium headless en 1440×1000 y 390×844. 66 comprobaciones, cero excepciones JavaScript y cero peticiones HTTP externas en la sesión. Se inspeccionaron capturas de inicio, modelos y móvil; no se realizó una auditoría WCAG completa ni aceptación humana.

Incidencias conservadas: preview rechazó file://; agent-browser intentó abrir una pantalla gráfica ausente. Se verificó con instancia headless aislada y se cerró. El primer test del intervalo esperaba agrupación española de cuatro dígitos; se corrigió la expectativa contra la fuente y el formateador, sin modificar el valor mostrado. fallo-navegador.txt conserva ese intento.

No hay datos industriales nuevos, validación/test adicional, despliegue ni sustitución del modelo. Los intervalos bootstrap no incorporan toda la variabilidad de búsqueda/ajuste. La selección de presupuestos es una hipótesis de ingeniería posterior a los estudios previos.
