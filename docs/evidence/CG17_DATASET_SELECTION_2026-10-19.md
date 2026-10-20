# Selección de dataset para degradación y propuestas temporales

> Alcance retirado de la entrega por confirmación20Oct: usar solo AI4I reducido y
> clasificación del estado actual. Documento histórico; no activar pronóstico temporal
> ni sustituir el dataset. Véase [alcance vigente](CG17_CURRENT_STATE_SCOPE.md).

Fecha de investigación:19Oct2026. Decisión: **XJTU-SY para la ampliación temporal**,
con AI4I separado para la entrega obligatoria. Recomendación por adecuación del
objetivo, no resultado de entrenamiento ni garantía de precisión. No se cambia la
API, el dataset activo ni el enunciado con este informe.

## Condición académica

`ENUNTZIATUA.md`, sección Datua, exige entrenar solo con `ai4i2020_train.csv` y
no mezclar los datos del simulador/test. La rúbrica G10/G45/G60/G61/G62 pide comparar
modelos, justificar desbalance/costes, feature engineering e historia por máquina;
G41/G49/G71/G100/G105 añade integración/series/alertas/dashboard. Cambiar dataset
no elimina esos entregables ni convierte sus umbrales probabilísticos en umbrales RUL.

La conformidad del tutor para clasificación del estado no demuestra autorización
para sustituir AI4I en la entrega. Por eso la arquitectura propuesta mantiene dos
experimentos/contratos y presenta XJTU-SY como extensión temporal; una sustitución
obligatoria necesita aceptación docente explícita, no se da por obtenida.

## Comparación basada en fuentes primarias

| Dataset | Evidencia útil | Limitación decisiva | Elección |
|---|---|---|---|
| XJTU-SY |15rodamientos con vida completa,3regímenes,2vibraciones y adquisición cada1min;25.6kHz durante1.28s por adquisición | Banco acelerado, pocos activos, no máquina CNC completa ni calendario/estaciones | **Principal para RUL en minutos y adaptación** |
| FEMTO/PRONOSTIA | Ensayos reales acelerados, vibración/temperatura y reto de RUL | Paquete/particiones deben auditarse; más procesamiento de señal; sigue siendo componente | Segunda opción para contraste externo |
| PHM2010 CNC |6herramientas,3entrenamiento con desgaste por corte,7canales a50kHz; fresado CNC real | Pocas vidas etiquetadas; orden por corte no prueba duración entre cortes/fecha de fallo de máquina | Mejor si se prioriza desgaste de herramienta y RUL por cortes |
| NASA Milling Wear | Fresado experimental con desgaste VB y distintas condiciones | Desgaste de herramienta no acredita por sí mismo fallo completo o etiqueta de horizonte5min; inspeccionar tiempo/NaN/finales por ensayo | Complemento de dominio CNC |
| NASA C-MAPSS | Simulación de degradación de motores, trayectorias y benchmark RUL | Dominio aeronáutico; ciclos no son minutos ni estaciones; no sustituir C-MAPSS por PHM08 sin etiquetas RUL públicas | Benchmark metodológico alternativo |
| GE/UTK servomotor-ballscrew | CSV simulados con torque, velocidad, corrientes, tiempo y niveles de degradación |21.3GB; niveles de degradación muestreados no acreditan trayectoria run-to-failure | No elegir para resolver ETA física |

Criterios eliminatorios para ETA: identidad del componente, orden/escala temporal
justificables, final de vida o censura interpretable y etiquetas disponibles. Después
priorizar tiempo en minutos, número de vidas independientes, cambio de condiciones,
encaje mecánico, acceso y coste de preparación. No se inventan puntuaciones de precisión.

## Por qué XJTU-SY

La documentación de los autores identifica15vidas completas en3regímenes (5por régimen).
Cada archivo CSV representa una adquisición de dos ejes,32768muestras/eje, cada minuto.
Esto resuelve el problema que AI4I no resuelve: vincular mediciones sucesivas a una
vida de componente con una escala temporal y un final observado en el experimento.
No requiere un timestamp de calendario original para aprender duración: se utilizará
tiempo transcurrido según la cadencia documentada. Un ancla de reproducción, si se
necesita para Kafka/Kibana, irá separada y marcada como sintética.

Se puede definir offline RUL_min=N-i para el archivo i de una vida completa de N
archivos, verificando continuidad de índices y el criterio final del ensayo. Es tiempo
hasta el endpoint experimental, no prueba de avería de una fábrica. N/último instante
solo construyen etiquetas; jamás son predictores ni se exponen al modelo online.

## Diseño de evaluación y cambios necesarios

1. Auditar archivos originales, hashes, condiciones de acceso/citación, número de vidas,
   orden, faltantes, unidades y definición del final. Los autores permiten uso para
   validar algoritmos y solicitan citar su artículo; no se etiqueta CC BY/CC0 sin verificar.
2. Extraer por adquisición RMS, dispersión, pico, curtosis, factor de cresta y bandas
   espectrales por eje; incorporar rpm/carga documentados. Historial/normalización
   exclusivamente causales. No introducir vida total, porcentaje real consumido ni RUL
   como feature, ni normalizar con el futuro de la misma vida.
3. Adaptar el contrato actual a `elapsed_minutes` con procedencia de cadencia; hoy
   espera fecha ISO con zona. No falsear una fecha física para satisfacer el parser.
   Los modelos API AI4I conservan su contrato; vibración no se renombra como torque.
4. División por rodamientos enteros, fijada antes de mirar resultados: por cada régimen,
   3vidas para desarrollo,1calibración/validación,1test final (9/3/3 en total). Dentro de
   desarrollo, validación agrupada y temporal. Conservar test intacto hasta congelar
   selección; complementar con prueba de cambio de régimen, sin reutilizar test para elegir.
5. Comparar persistencia/edad como referencias, RF/boosting para RUL y modelos incrementales
   sobre features causales. Evaluar si las mejoras persisten por vida, no solo por fila.
   La mejora en MAE de sensores del prototipo no demuestra mejora de RUL.
6. Objetivos separados: RUL en minutos y probabilidad de endpoint dentro de5/15/30min;
   calibración con vidas de validación, incertidumbre/cobertura por horizonte y abstención.
   Medir error RUL, anticipación por evento, fallos omitidos y falsas alarmas por hora-activo.
7. Para aprendizaje continuo, sensores futuros permiten actualizar pronóstico de sensores;
   etiquetas RUL/fallo de una vida no están disponibles hasta el final. Retrasar esa
   supervisión o usar tratamiento explícito de censura. Nunca entrenar con etiquetas
   obtenidas del futuro de la vida de prueba durante su reproducción.
8. Ventanas de revisión derivadas de RUL/distribución y capacidad/costes declarados;
   no aprender el beneficio óptimo de intervenir sin registros de intervención/resultados.

Cinco minutos es un horizonte de evaluación posible, no un anticipo garantizado. No hay
50CNC, H/M/L original, historial de estaciones ni reparaciones reales en XJTU-SY: no se
fabrican. Las15vidas aceleradas limitan la generalización y la validación estadística.

## Acceso comprobado y alcance de la revisión

Se verificaron página y README originales de XJTU-SY, y enlaces de descarga publicados
por los autores. El visor web no pudo abrir el contenido de la carpeta Drive: no se
ha descargado ni auditado el archivo completo de XJTU-SY en esta tarea. Por tanto es
selección fundamentada en documentación primaria, pendiente del control de adquisición.

Se comprobaron HEAD de los archivos publicados por el espejo reconocido por NASA:
Milling14,731,306bytes; C-MAPSS12,429,152bytes; FEMTO1,157,035,288bytes. Se leyeron los
ZIP externos de Milling/C-MAPSS y sus nombres internos; esto no constituye un análisis
de calidad completo ni evaluación de modelos. No se descargó FEMTO completo.

Hashes observados de ZIP externos:
- Milling: `bdba8d52ec1a1baab24c2be58480e6ac62508c8cc1f8219f47ebde8fc9ebc474`
- C-MAPSS: `c9c5dec12a945a82e8bb4446589d7fb3cc057b5e5d81fa1a12e25ee9912ad3b2`

## Fuentes primarias consultadas

- Autores XJTU-SY: https://biaowang.tech/xjtu-sy-bearing-datasets/
- Repositorio de autores: https://github.com/WangBiaoXJTU/xjtu-sy-bearing-datasets
- PHM2010 organizador: https://phmsociety.org/phm_competition/2010-phm-society-conference-data-challenge/
- NASA repositorio: https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/
- Espejo enlazado por NASA: https://data.phmsociety.org/nasa/
- Paper autores PRONOSTIA: https://publiweb.femto-st.fr/tntnet/entries/1528/documents/author/data
- NASA Milling catálogo: https://catalog.data.gov/dataset/milling-wear
- GE/UTK publicador: https://data.phmsociety.org/servomotor_dataset/
