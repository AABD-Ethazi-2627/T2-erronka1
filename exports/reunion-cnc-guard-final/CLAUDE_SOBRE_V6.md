# Revisión de cierre de la v6: el feedback está aplicado en pantalla, salvo fallos en la impresión

**Veredicto: la v6 se puede usar en reunión en pantalla. Antes de repartirla en PDF o en papel necesita un arreglo.**

H1–H7 están aplicados en el HTML, con residuos menores en H1, H3 y H4. El defecto real es que **al imprimir se pierden el glosario y la escala económica** (H2 y H5). Por eso «cierre completo» es excesivo como título de `LEEME.md`. No encontré cifras erróneas en la muestra contrastada.

No puedo saber por qué la v5 dejó el feedback a medias. `CIERRE_FEEDBACK.md` lo reconoce, y el código confirma que la ficha de H6 y los estados de H7 existen ahora.

## H1–H7

| H | Estado | Evidencia propia | Residuo |
|---|---|---|---|
| **H1** Referencia | **Aplicado** | RF@0,15 aparece en KPI y tabla en modo breve; el acuerdo 1 nombra 0,15/0,70; A no queda limitada. | «Para decidir» no dice que, con la matriz base, ninguna A baja de RF@0,15 (mejor A 31.321 frente a 30.893). |
| **H2** Protagonismo | **Pantalla: aplicado. Impresión: parcial** | Tres KPI en paralelo, barras sin color fijo, 839 €/1.000 y topes de escala correctos. | La escala queda plegada y **no sale en el PDF**. |
| **H3** Etiquetas | **Aplicado, con residuo** | «Coste de este escenario»; solo un intervalo con límite superior negativo sale en verde; el texto indica la dirección; la tabla ya usa «procedimiento». | Quedan nombres mezclados (detalle abajo). |
| **H4** Restricción | **Aplicado** | Base, sin mínimo y 85 % dan conteos idénticos; RF pasa de 179.400 a 170.400 € con −45 FP; corte de la partición 3: 0,0704→0,1708; G45 contiene «%76+» y 1.200 €/h. | El acuerdo 2 sigue pidiendo «una restricción justificada» sin avisar de que 76 % y 85 % no cambian nada. |
| **H5** Claridad | **Pantalla: aplicado. Impresión: parcial** | Glosario completo, 4.700 € y 23,5 FP/TP; sin hashes en la primera vista. | El glosario y el 23,5 **no salen en el PDF**. |
| **H6** Candidato y puerta | **Aplicado** | Ficha con identidad, corte, conteos e intervalo propio; reservas justo debajo; el acuerdo 3 dice que con los datos actuales no se puede hacer una evaluación independiente. | El margen sigue «por confirmar», y es correcto: lo decide el equipo. Falta declarar una fuente (detalle abajo). |
| **H7** Rúbrica | **Aplicado, con prioridad poco útil** | 40 filas con estado y prioridad; criterios por acuerdo; puertas prioritarias; 8/10 solo en detalle; «15%%» remitido a A02. | La prioridad no añade información (detalle abajo). |

**Opcionales del feedback:**

| Opcional | Estado |
|---|---|
| Zoom de imágenes | Aplicado; capturas revisadas |
| Nota sobre AP agrupada | Aplicada |
| Aviso de que escenarios y presupuestos no tienen intervalos | Aplicado, junto a los resultados |
| Fila post-selección | Aplicada |
| Formato uniforme de números | **No aplicado** (5370 frente a 5.600, -1321 frente a 30.893); cosmético |

## Hallazgos que el cierre no recoge

1. **La impresión pierde contenido.**
   - **Evidencia:** en el texto de `impresion-prueba.pdf` (23 páginas), «839», «23,5», «4.700» y «positivo detectado» aparecen 0 veces. «Diccionario» y «Escala económica» solo salen como título.
   - **Causa:** los `<details>` plegados siguen plegados al imprimir.
   - **Por qué no se detectó:** el check «Print output generated with all report sections» solo exige `pdf.data.length>10000` (`verificar-navegador.mjs:55`).
2. **Nombres mezclados (`plantilla.html:39`).**
   - **El más confuso:** el simulador, visible en modo breve, llama «RF referencia» a RF A (32.036), mientras «RF@0,15» es otra fila (30.893).
   - **Otros:** Capacidad usa «RF» sin indicar el corte, y conviven «Elegir tres familias», «Selección de pareja» y «selector de parejas».
3. **Procedencia incompleta de la ficha fija.**
   - `calcular-fijo.py` no lee solo `analysis-v1`: también lee `run-01/single-rf_reference-B-oof.csv`, y `sources` no lo declara.
   - **No afecta a las cifras:** comparé con `analysis-v1/rf_reference-outer.csv` y coinciden scores (Δ máx. 0,0), predicciones y particiones.
4. **La prioridad de la rúbrica repite el estado (`construir.py:45-57`).**
   - Es una lista manual: Media equivale a «Evidencia disponible» y todo lo demás es Alta (28 Alta y 12 Media).
   - G19 («cierre de imágenes pendiente») queda como evidencia disponible y Media, mientras G80, con puertas de imágenes parecidas, queda como Alta.
   - La reserva original se muestra al lado y la guía real son las puertas prioritarias, así que no engaña.
5. **Texto de proceso caducado en «Acuerdos y fuentes».** «El coordinador verificará…» y «Claude debe comprobar después» ya no son ciertos tras esta revisión. `REVISION.md` y `fallo-navegador.txt` también siguen hablando de la v4.

## Cifras contrastadas

| Cifra | Resultado |
|---|---|
| Plantilla + payload = HTML; payload = `datos-revisados.json` | Exacto; 18 imágenes |
| SHA del HTML, `SHA256SUMS`, ZIP y su copia del HTML | Correctos |
| 21 filas de métodos (coste recalculado) | 0 errores |
| Ficha: 168/22/40/5370, 168.400 €, 30.071, Δ −821 | Reproducido desde el ZIP con hash 640d… |
| Intervalo [−1321,43; −321,43] | **Reproducido exacto** con mi propio script, semilla 42 |
| Pesos 75/25 | Correctos; invertidos darían 172/18/137. También coinciden con el manifest y el ganador del screening |
| 839, 10.179, 169.643, 203.393, 25,8, 47,0/54,5 | Correctos |
| Pareja frente a RF A por partición: +3.589, +2.142, −6.484 | Confirma «una de tres» |

**Reservas junto a los resultados:** están en la ficha fija, en los intervalos de A y en el panel de escenarios y presupuestos. El intervalo de la ficha excluye el cero, pero no se presenta como ventaja: lleva advertencia y no sale en verde.

**Un dato útil que falta en la ficha:** toda la diferencia son **23 FP netos** (38 retirados, 15 añadidos) y ninguno en positivos. Es menos que un solo cambio FN→TP (−821 frente a 839 €/1.000), y el segundo del ranking está a solo 300 € en total.

## Reservas del coordinador: son correctas

- **Potencia:** hace bien en no adoptarla como prueba. Mis cifras eran una aproximación con Δ y varianza supuestas estables y sin corregir la selección. La idea cualitativa se sostiene sin ellas, con la escala de 839 € y el ranking casi empatado.
- **Restricción y ruido:** mi frase («señal clara de ruido de selección») fue demasiado fuerte.
  - Solo vale en el límite de datos infinitos. Con muestra finita, restringir puede mejorar de verdad el procedimiento al reducir la varianza de la selección.
  - Además, aquí el efecto viene de un único corte en una partición, y eso no permite separar ambas explicaciones. El texto del informe («compatible con regularización y variabilidad») es la lectura correcta.
  - El «ruido puro» de `CIERRE_FEEDBACK.md` no es literal mío, pero la corrección de fondo es justa.

## Qué impide usar el informe y qué es otro trabajo

**Impedimentos reales**
- **En pantalla:** ninguno.
- **En PDF o papel:** el hallazgo 1.

**No son defectos del informe; requieren datos o actos propios**
- Evaluación independiente con datos nuevos autorizados.
- Validación cruzada repetida y preespecificada de estabilidad. Hoy solo consta en `CIERRE_FEEDBACK.md`, no en el HTML.
- Latencia y memoria del candidato en integración.
- Capacidad real con tasa de llegada y agrupación de episodios.
- Respuestas docentes (A02 y las demás consultas pendientes), ensayo y defensa humanos.

## Cambios pendientes

Son pocos y no requieren entrenar nada. Al reconstruir, el hash cambiará.

**Antes de repartir en PDF o papel**
1. Abrir todos los `<details>` en `beforeprint` y restaurarlos en `afterprint`. Cambiar además el check para que busque «839», «23,5» y «positivo detectado» en el PDF.

**Conviene hacerlos ya (una línea cada uno)**
2. Añadir en «Para decidir»: «Con la matriz base, ninguna A baja de RF@0,15; esto no demuestra que 0,15 sea superior». Debe decir «base», porque con presupuesto 50 RF A (30.429) y pareja (30.518), y con recall ≥90 la pareja (30.268), sí quedan por debajo de 30.893.
3. Nombrar la fila del simulador «RF A» y unificar los nombres de los selectores.
4. Actualizar el texto de proceso en «Acuerdos y fuentes» y el título de `LEEME.md`.
5. Añadir el CSV de `run-01` y su hash a `sources`.

**Opcionales**
- Abrir por defecto la escala económica.
- Añadir a la ficha la frase de los 23 FP netos.
- Añadir al acuerdo 2 un aviso de que 76 % y 85 % no cambian las decisiones.
- Revisar G19.

No propongo más ciclos después de esto.

## Cobertura y límites

- **Inspeccionado:** las capturas de ficha fija, modelos, rúbrica, acuerdos, zoom y móvil-modelos. El PDF lo revisé por extracción de texto, no por imagen de página.
- **Modo breve:** no relancé el navegador. La captura de modelos está en modo detalle, y deduje el modo breve del código: solo dos elementos llevan `.technical`.
- **Interactividad:** los 80 checks son del coordinador (`navegador.json`). Leí parte del verificador, no todo.
- **No auditado:** los 40 criterios frente a las fuentes S01–S20, servicios vivos, estado de PR119, las demás capturas móviles y WCAG.
- **Sin cambios:** no modifiqué nada del proyecto, no entrené ni lancé procesos de navegador. Mis scripts y el texto del PDF están en `/tmp/claude-1000/-home-tears-bigdata-01-Erronka1-CNC-Guard-B-taldea/45ef2bc5-9061-46c2-9133-6679b1eb7aac/scratchpad/rev`.
- **Alcance del veredicto:** es una revisión técnica; no es nota docente ni aceptación humana.

`★ Insight ─────────────────────────────────────`
- Un check valida solo lo que comprueba: «all report sections» medía el tamaño del PDF, y por eso la pérdida de contenido pasó inadvertida en los 80 controles.
- Un intervalo que excluye el cero no es por eso una ventaja: es condicional a una configuración ya elegida y aquí equivale a 23 FP netos, menos que un solo fallo detectado.
`─────────────────────────────────────────────────`
