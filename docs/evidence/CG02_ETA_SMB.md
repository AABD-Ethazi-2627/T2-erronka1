# CG02 — ¿permiten los datos SMB estimar cuánto falta para fallar?

**Resultado: no permiten entrenar ni validar una ETA física defendible.** Se
capturó en lectura exclusiva la lista congelada de509 lotes actuales, no solo dos
muestras. Las fechas corresponden al replay de estados estáticos; no acreditan
una trayectoria de degradación. No se entrenó un modelo con falsas etiquetas RUL
ni se convirtió el score RF a minutos. API y niveles docentes siguen intactos.

[Resultados ejecutados y hashes](CG02_temporal_feasibility.json) ·
[Propuesta de salida temporal, sin despliegue](CG02_ETA_PROPOSAL.json).

## Evidencia nueva de la fuente disponible

- 5.090 filas,50 identificadores,509 instantes entre06:07:53 y10:21:55UTC del19/10.
- La secuencia completa de2.000 estados (ID, tipo, sensores y etiquetas) se repite
  exactamente en el mismo orden cada2.000 emisiones, excluyendo únicamente fecha.
- Los5.090 registros coinciden en sensores/tipo/etiquetas con AI4I oficial de UCI.
  Sus2.000 estados únicos coinciden exactamente, por sensores/tipo, con el
  complemento de nuestras8.000 filas de entrenamiento dentro de las10.000 UCI.
  No se observó solapamiento de sensores/tipo con las8.000 filas del CSV local.
- 485 grupos máquina+instante tienen estados diferentes, afectando1.028 filas.
  En27 grupos hay tanto etiqueta0 como1. No es válido ordenarlos artificialmente.
  No se observaron cambios de machine_type bajo mismo ID en este snapshot.
- Al excluir grupos conflictivos quedan4.062 observaciones únicas. Entre lecturas
  consecutivas el desgaste baja1.992 veces, sin log de cambio de herramienta o
  reparación. Eso no demuestra reparación ni un nuevo ciclo de vida.
- La emisión de lotes tiene mediana30s, pero por identificador la separación tiene
  mediana120s y p95600s;17,25% de intervalos superan5min. La frecuencia del batch
  no es la frecuencia de seguimiento de cada activo.

Los176 estados etiquetados positivos no son176 fallos observados en una fábrica.
La huella UCI demuestra procedencia de esos estados, no el significado físico de
machine_id ni de las fechas añadidas. El complemento de2.000 puede servir para
analizar clasificación estática fuera del train local, con su historial de
exposición documentado; **no es un test temporal ni evidencia industrial nueva**.
Esta auditoría no reevalúa el test antiguo ni cambia selección/modelos.

Como diagnóstico se calculó el siguiente estado positivo estrictamente posterior
solo en series sin conflictos simultáneos:2.768 filas tienen otro positivo y
1.294 terminan sin él. La mediana30,5min **no es ETA**. Es tiempo hasta otra
muestra positiva dentro de un replay circular. Entrenar una regresión con esa
columna premiaría aprender el emisor, no anticipar una avería. Tampoco una
transición0→1 bajo un ID reutilizado equivale a onset confirmado.

## Qué modelo y criticidad sí tendría sentido construir

La necesidad del usuario es pronóstico de tiempo hasta evento, no solo
clasificación del estado. Propuesta inicial de horizontes:5/30/120min, para revisar
con el equipo según tiempo real de intervención y coste. No son límites exigidos
por la rúbrica ni parámetros ya calibrados.

| Nivel temporal propuesto | Condición que habría que validar | Estado actual |
|---|---|---|
| CRITICA | Riesgo suficientemente alto de onset en≤5min | No evaluable |
| ALTA | Sin activar CRITICA, riesgo alto en≤30min | No evaluable |
| AVISO | Sin activar niveles anteriores, riesgo relevante en≤120min | No evaluable |
| NORMAL | Seguimiento/modelo válidos y ningún horizonte activa aviso | No equivale a garantía de no fallar |
| UNKNOWN/INCIERTA | Sin modelo, historial insuficiente, conflicto o distribución desconocida | Es el resultado correcto aquí |

El umbral de probabilidad por horizonte queda por seleccionar con costes y
presupuesto de falsas alarmas. p5≤p30≤p120 debe cumplirse. Se mostrarían
probabilidades acumuladas y, si el soporte lo permite, un intervalo de tiempo
con incertidumbre; no una cuenta atrás exacta. Si el intervalo atraviesa varios
niveles, conservar incertidumbre y revisión humana, sin etiquetar como seguro.
Si un fallo ya está confirmado, informar de ese estado por separado: no emitir
una falsa predicción «fallará en0min».

Para empezar preferiría comparar clasificadores multihorizonte con un modelo
de supervivencia que respete censura. El primero responde directamente a los
niveles solicitados; el segundo permite estimar una distribución temporal.
No se elige ni instala otra librería antes de disponer de etiquetas válidas.
La criticidad temporal será un campo separado de alert_level por score (.15/.70)
que pide el contrato docente: esos umbrales no equivalen a5 o30 minutos.

## Datos mínimos que faltan

| Registro | Campos y significado necesarios |
|---|---|
| Telemetría | physical_machine_id, component_id, lifecycle_id, event_time UTC del sensor, ingested_at separado, sensores/unidades, estado operativo/calidad |
| Evento de fallo | failure_event_id, mismo activo/componente/ciclo, onset_time confirmado, modo de fallo, resolución temporal y fuente de confirmación |
| Intervención | parada planificada, cambio de herramienta, reparación/reinicio, comienzo/fin y nuevo lifecycle_id cuando corresponda |
| Seguimiento | inicio/fin de observación, huecos, frecuencia real por máquina; acordar minutos de calendario frente a minutos efectivos de operación |

Objetivo de adquisición propuesto para probar5min: lectura por activo al menos
cada minuto y onsets con resolución similar, conservando huecos. Es una condición
de observabilidad propuesta, no garantía de que existan señales predictoras.
No usar información de operarios para completar identidades de activos.

Con logs verificados: dentro de cada ciclo, para una lectura en t, registrar el
primer onset posterior y delta=onset−t; si no se observa fallo, registrar el fin
de seguimiento y censura. En clasificación por horizonte, una lectura sin fallo
solo es negativa si se observó todo ese horizonte. No asignar «infinito»,0 o sano
por ausencia de datos. Separar ciclos/periodos y purgar ventanas cuyo horizonte
cruce train/validación/evaluación; no repartir filas vecinas al azar.

Aceptar un modelo requiere medir por evento el primer aviso y su anticipación,
porcentaje de eventos avisados con margen≥5min, errores de tiempo/intervalos,
calibración por horizonte, falsas alarmas por máquina/día y carga de avisos.
La latencia HTTP del API se mide aparte; no acredita anticipación de averías.

## Reproducir y conservar evidencia

Snapshot local inmutable: outputs/smb-eta-2026-10-19/raw +capture_manifest.json.
No está montado en Filebeat, no reinyecta5.090 filas en Kafka y no modifica SMB.
El listado quedó congelado antes de descargar; no es snapshot transaccional del
servidor. Se conservan bytes y SHA-256; credenciales solo en.env privado0600.

```bash
# Otra captura: directorio NUEVO, lectura exclusiva, máximo1000 lotes, sin timer.
uv run --frozen python -m scripts.capture_temporal_snapshot \
  --env-file /ruta/privada/.env --output outputs/smb-eta-otra-captura
# Auditar la captura preservada de esta entrega:
uv run --frozen python -m scripts.audit_temporal_feasibility \
  --root outputs/smb-eta-2026-10-19
uv run --frozen python -m unittest discover -s tests -v
```

El CSV oficial UCI se conservó solo en outputs/.../reference/ai4i2020_uci.csv
para comparar huellas. URL de descarga pública:
https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip
El auditor es offline: sin ese CSV aún verifica conflictos/replay, pero no genera
el apartado official_uci_reference. Su SHA está en el informe para reproducirlo.
No se sustituyen fuentes ni se incorporan esas filas al entrenamiento de modelos.

Fuentes primarias: [AI4I/UCI](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset),
[introducción a supervivencia y censura](https://scikit-survival.readthedocs.io/en/stable/user_guide/00-introduction.html).
La documentación de supervivencia respalda el tratamiento de censura, no una
capacidad de ETA en estos datos. Revisión del equipo y registros físicos pendientes.
