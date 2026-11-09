# Revisión independiente del informe v4 de CNC Guard

## 1. Veredicto

**Necesita cambios, aunque son acotados y no requieren entrenar nada.** Mejora a v3 como herramienta de reunión, pero no en todo, y no la considero todavía la mejor versión posible.

- **Dónde mejora:** capacidad TP+FP, intervalos propios de A, casos, ablaciones, identidades separadas y archivo único offline.
- **Dónde retrocede:** pierde la explicación económica (23,5 FP por TP) y el glosario de FP/FN. La tabla de siete procedimientos y el contexto de 0,15/0,70 quedan ocultos en modo breve.
- **Lo que está bien:** la aritmética es correcta y la contención epistémica es buena.
- **El problema principal:** el marco de comparación usa RF A como referencia, no la política 0,15 documentada. Eso cambia lo que entenderá quien lea el informe.

## 2. Hallazgos priorizados

### Defectos

**H1. La referencia no es la política documentada (alta).**
- **Dónde:** `plantilla.html`, secciones `#leadUncertainty`, «política principal A» y acuerdo 1.
- **Evidencia:** B solo aparece dentro de `.technical`, y las aclaraciones y G61 conservan 0,15/0,70. Recalculado con los OOF de `run-01/`:

| Procedimiento | TP/FN/FP | €/1.000 | Δ frente a RF@0,15 |
|---|---|---|---|
| RF@0,15 | 168/22/63 | 30.893 | referencia |
| RF A | 168/22/95 | 32.036 | +1.143, IC [679; 1.643] |
| Pareja A | 170/20/135 | 31.786 | +893 |
| Tres familias A (la mejor de A) | 172/18/169 | 31.321 | +429 |

- **Impacto:** «mejora el coste observado frente a RF» es cierto solo frente a RF A. Ningún procedimiento A supera en coste observado a RF@0,15. El acuerdo 1 dice «mantener RF» sin decir con qué corte.
- **Cautela:** no verifiqué si 0,15 se fijó sin ver estas filas, así que esto no demuestra que 0,15 sea superior. El servicio vivo tampoco se consultó.
- **Cambio:** mostrar RF@0,15 en modo breve como fila de contraste, y nombrar el corte en el acuerdo 1.

**H2. La pareja recibe protagonismo sin justificación (alta).**
- **Dónde:** KPI de `#scenarioMetrics`, barra teal fija (`i===2`) y texto inicial.
- **Evidencia:**
  - La mejor fila A es tres familias (31.321), no la pareja, y el pool completo queda peor que RF (+643).
  - En el presupuesto 50, que es la vista por defecto de capacidad, RF gana a la pareja (30.429 frente a 30.518), pero la barra destacada sigue siendo la pareja.
  - La diferencia base de −250 €/1.000 equivale a 1.400 € en total. **Un solo fallo pasado de FN a TP mueve 839 €/1.000.**
  - La pareja cambia 3 TP ganados y 1 perdido por 90 FP añadidos y 50 retirados.
- **Impacto:** las barras casi iguales y el color sugieren un ganador que los datos no sostienen.
- **Cambio:**
  - Usar RF como KPI, o mostrar RF y pareja juntas.
  - Quitar el color fijo.
  - Añadir topes de escala: perfecto 10.179, sin avisos 169.643 y marcar todo 203.393 €/1.000.
  - Añadir la frase del 839 €.

**H3. Tres errores de etiqueta o semántica (media-alta, fáciles de corregir).**
- **Etiqueta de coste:** el KPI dice siempre «Coste del ejercicio», pero en escenarios hipotéticos es el coste de ese escenario. En `fn_alto` muestra 37.196, y con la matriz real esas decisiones cuestan 30.946.
- **Color del intervalo:** un IC que no cruza cero sale en verde (`positive`) aunque el candidato sea **peor**. Ocurre con «Elegir individual» [357; 3.339] y «Elegir comité» [286; 4.804]. El texto tampoco indica la dirección.
- **Nombre mezclado:** la tabla de estabilidad llama «candidato» a un selector variable, justo lo que «Identidades que no deben mezclarse» prohíbe. Además conviven «Selector de parejas», «Elegir pareja» y «Pareja A».

**H4. El hallazgo más útil para decidir no se cuenta (alta).**
- **Dónde:** `#capacity` y el acuerdo 2.
- **Evidencia:**
  - El mínimo de 76 % no es activo: `base`, `sin_minimo` y `recall85` dan filas idénticas.
  - Con presupuesto 50, RF **baja** de 179.400 a 170.400 €, sin perder ningún TP. Solo cambia el corte de la partición 3 (0,0704 → 0,1708), que retira 45 FP.
  - Pasa algo parecido con recall ≥90 %: la pareja baja a 30.268 con la misma matriz, por debajo de su caso sin restricción.
  - Es decir, la inestabilidad del corte pesa más que la elección de modelo.
  - El 76 % tampoco se vincula con su origen, el literal de G45.
- **Impacto:** «una restricción de detección justificada» queda vacío, y el grupo podría debatir un límite que no cambia nada.
- **Cambio:** añadir un recuadro breve con estos tres hechos y la cita de G45. Aclarar que G45 cita 1.200 €/h y que la matriz vigente es la del post docente.

**H5. Regresión de claridad para el público no técnico (media-alta).**
- **Dónde:** `<details>` «Diccionario» en `#briefing`.
- **Evidencia:**
  - Faltan TP/FP/FN/TN, RF, AP y A/B/C.
  - La definición de A solo aparece en un `<option>` dentro de `.technical`, invisible en modo breve. Aun así, «RF A» y «política principal A» se usan en modo breve.
  - La primera pantalla incluye `c34cabe`, `d7cfa18` y `REVIEW_REQUIRED`.
  - La explicación de v3 (FN→TP evita 4.700 €, frente a 200 € por FP, es decir, 23,5 FP/TP) ha desaparecido.
- **Cambio:** recuperarla y ampliar el glosario. Mover los hashes al detalle o a fuentes.

**H6. El candidato fijo y el acuerdo 3 no son operativos (media).**
- **Evidencia:**
  - El candidato no aparece con cifras ni con su corte, aunque se seleccionó y se define con 0,15 (`seleccionar_candidato.py`, `manifest.json`). Por eso **los intervalos de A no le aplican**.
  - «No elegido en outer» es formalmente cierto, porque las particiones difieren. Pero sus predicciones screening y outer a 0,15 coinciden en un 99,39 % y dan los mismos 168/22/40. Es prácticamente la misma evidencia.
  - Su Δ frente a RF@0,15 es −821 €/1.000, ya contaminado por la selección entre 2.340 pares.
  - El acuerdo 3 pide «evaluación adecuada», pero no dice con qué datos, si la validación y el test quedan excluidos.
- **Cambio:** añadir una fila «post-selección, no independiente». Sustituir la frase por una puerta concreta: qué dato nuevo, qué métrica y qué margen. Si no hay dato nuevo, decir expresamente: «con los datos actuales esta prueba no se puede hacer».

**H7. La relación con la rúbrica es un listado, no una guía (media).**
- **Evidencia:**
  - Las 40 filas no llevan estado ni prioridad.
  - Los tres acuerdos no se enlazan con G14, G39, G45, G60, G61 o G62.
  - «8/10; banda 7–8,5» aparece sin derivación visible.
  - «15%%» se muestra sin explicar que es un literal raro de la celda H5, aún sin aclarar en A02.
- **Cambio:** añadir «criterios que toca» en cada acuerdo y una lista corta de puertas abiertas (por ejemplo G49, G62 y G92). Considerar eliminar la banda del titular.

### Cobertura no comprobada (no son defectos demostrados)

- **Lectura humana:** no hay aceptación humana ni auditoría WCAG, y el informe lo declara.
- **Impresión y modo proyector:** no los probé.
- **Imágenes de servicios:** no inspeccioné una a una las 12 fichas ni las 5 capturas. La verificación del artefacto solo comprueba que cargan.
- **Móvil:** el mapa de arquitectura se ve muy pequeño a 390 px y no hay ampliación. Lo vi en captura, pero no probé el zoom.
- **PR119:** el estado es una instantánea de las 10:43. No lo reconsulté.

## 3. Puntuaciones orientativas (no son nota docente)

| Dimensión | Nota | Justificación |
|---|---|---|
| Rigor analítico | **7/10** | Cifras reproducibles, límites honestos y selección interna correcta en el código leído. Pierde por la referencia (H1), H6 y la falta de intervalos en escenarios y presupuestos. |
| Claridad no técnica | **6/10** | Buena estructura y buena pregunta inicial. Pierde por el glosario incompleto, la A no definida, la mezcla de nombres y los hashes en la primera pantalla. |
| Utilidad en reunión | **7/10** | Tres acuerdos, agenda, borrador exportable e imágenes. Pierde porque el acuerdo 3 no es accionable y el 2 no revela que el 76 % no es activo. |

## 4. ¿Mejoraría la evidencia buscar más modelos?

**No, de forma material.** Ampliar la búsqueda aumentaría la selección sobre las mismas 190 positivas, sin aportar información nueva.

- **El ranking está en nivel de ruido:** los cuatro primeros de 2.340 pares (`seleccion-fija-screening.json`) difieren en 700 € en total, menos que un solo FN→TP (4.700 €).
- **La potencia queda fuera de alcance.** Aproximación de 80 % de potencia, suponiendo Δ y varianza estables y sin corregir la selección:

| Comparación | Δ €/1.000 | Filas necesarias |
|---|---|---|
| Pareja A frente a RF A | −250 | ≈2,3 millones |
| Tres familias A frente a RF A | −714 | ≈265.000 |
| Pareja B frente a RF B | −1.125 | ≈78.000 |

- **Una señal que sí conviene mostrar con cautela:** la pareja cuesta menos o igual que RF en los 9 escenarios y en A/B/C. Destaca recall ≥95 % (mismos 183 TP, con 538 FP frente a 857). Pero son resultados dependientes, sobre las mismas filas, y ese signo se invierte con presupuesto 50. Es una hipótesis a probar, no una conclusión.

**Lo que más aportaría, por orden:**

1. **Información de decisión, antes del ensayo.** Respuesta docente a A04/A05, y una capacidad real de revisión con tasa de llegada y agrupación de episodios. Sin ello, el presupuesto seguirá siendo hipotético.
2. **Actos humanos pendientes** (#37, #26, #27). Para la rúbrica pesan más que cualquier modelo adicional.
3. **Estabilidad del corte con configuraciones fijas.** Validación cruzada repetida solo sobre train para RF@0,15, candidato@0,15 y la regla de corte por coste, todo preespecificado. El candidato se ajusta rápido (0,53 s incluida la recarga). Sigue siendo desarrollo y queda optimista para el candidato, pero mide la variabilidad de partición y ajuste que el bootstrap excluye.
4. **Latencia y memoria del candidato en recorrido integrado.** Sin esto, la alternativa del acuerdo 1 no se puede evaluar.
5. **Lectura única sobre datos nuevos, solo con un protocolo cerrado.**
   - El repositorio tiene 8.000 filas, y hasta donde sé el AI4I público tiene 10.000.
   - No verifiqué si las otras 2.000 están disponibles ni si su uso sería aceptable, así que habría que preguntarlo al docente.
   - Con unas 68 positivas esperables, solo detectarían fallos gruesos, no una ventaja pequeña.

## 5. Cambios imprescindibles y opcionales

**Imprescindibles antes de circular:**
- Añadir RF@0,15 en modo breve y aclarar el corte del acuerdo 1 (H1).
- Corregir las tres etiquetas de H3.
- Quitar el protagonismo fijo de la pareja y añadir la escala con la frase del 839 € (H2).
- Añadir el recuadro de H4.
- Recuperar el 23,5 FP/TP y ampliar el glosario (H5).
- Volver operativo el acuerdo 3 (H6).

**Opcionales:**
- Fila post-selección del candidato con IC propio a 0,15.
- Enlaces entre acuerdos y criterios de rúbrica, y estado por criterio (H7).
- Intervalos para escenarios y presupuestos, o un aviso explícito de que no los hay.
- Formato uniforme de números (5000/5.000, 298.8/0,906).
- Ampliación de imágenes en móvil.
- Nota de que la AP agrupada de las ablaciones usa la misma métrica que el propio informe advierte que puede mezclar escalas.

## Qué verifiqué y qué no

**Verificado:**
- **Integridad:** SHA-256 del HTML correcto. La plantilla más el payload reconstruyen exactamente el HTML, y el payload coincide con `datos-revisados.json` en todas las claves comunes. Hay 18 imágenes embebidas. No ejecuté `construir.py`, porque escribe archivos.
- **Aritmética:** recalculé las 21 filas de métodos (coste, recall y marcadas). También 263 y 305 marcadas, 47,0 y 54,5 por 1.000, 25,8 por 1.000 y 2.998 (2.340 + 560 + 10 + 18 + 30 + 40). A mano revisé cuatro costes de escenario y la suma ponderada por particiones hasta −250.
- **Incertidumbre:** reproduje exactamente los seis IC de A con semilla 42. El IC antiguo de B ([−4.411; 1.607]) es coherente con mi réplica ([−4.376; 1.643]) y con sus 51 discordancias. Los IC de RF A frente a RF B, y de A frente a RF@0,15, son cálculos míos y no están en los artefactos.
- **Premisas, leyendo el código:** selección solo interna en `capacidad.py` y `politicas.py`, y corte de stacking sobre las salidas del propio ajuste. La exclusión de las 1.200 + 1.200 filas consta en el código y el protocolo, pero no la audité por separado. Screening y outer son particiones distintas pero con predicciones casi idénticas.
- **Visual:** inspeccioné las 7 capturas entregadas. Además rendericé copias temporales en el scratchpad, con solo un `showView` añadido, e inspeccioné modelos, capacidad, datos y rúbrica en modo breve.

**No verificado:**
- La vista «Acuerdos» renderizada: se generó, pero no la inspeccioné.
- Los archivos de `SHA256SUMS`, salvo el HTML.
- La suite de 66 comprobaciones del navegador: no la repetí.
- Reentrenamientos y CG34 completo.
- Servicios vivos, y las fuentes S01–S20 más allá de lo citado.
- Los controles interactivos en navegador. El acceso `file://` de Playwright estaba bloqueado, así que solo leí su código.

No modifiqué ningún archivo del proyecto. Solo creé scripts y renders temporales en el scratchpad. Chromium en modo headless seguía activo en mi última comprobación, en el último render y con límite de 60 s, y no volví a comprobarlo.

`★ Insight ─────────────────────────────────────`
- Que una restricción mejore el objetivo que se optimiza (presupuesto 50 frente a sin límite) es una señal clara de ruido de selección: sin ruido, restringir nunca debería abaratar el resultado esperado.
- Traducir una diferencia a «unidades de una decisión» (839 €/1.000 por cada fallo) transmite mejor el tamaño del efecto a personas no técnicas que un intervalo.
- Un bootstrap sobre predicciones fijas informa de la variabilidad de las filas, no de la del procedimiento, y por eso repetir la partición aporta más que añadir modelos.
`─────────────────────────────────────────────────`
