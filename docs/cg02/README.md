# CG02 — Inventario y viabilidad de la etiqueta

Entrega técnica preparada el 2026-10-16 para [issue #2](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/2).
El usuario acordó entrenar con `data/ai4i2020_train.csv` y tratar los batches SMB
como los registros operativos de máquina del laboratorio. Su procedencia simulada
basada en AI4I se mantiene explícita. Los dos usos no se mezclan en esta entrega.

## Reproducir y revisar

Desde la raíz, con Python estándar; sin red, credenciales, pandas ni scikit-learn:

```bash
python3 -m scripts.audit_cg02 --check
python3 -m unittest discover -s tests -v
```

`--check` recalcula hashes, contenido y resultados y falla si difieren del
[inventario guardado](inventory.json). No modifica los inputs. Solo después de
revisar un cambio intencionado de evidencia, `--write` regenera ese JSON derivado.
El fichero original de entrenamiento nunca se sobrescribe.

Fuentes, origen, licencia, roles y disponibilidad: [sources.json](sources.json).
Requisitos y decisiones de alcance: [CG02.md](../requisitos/CG02.md).

## Inventario comprobado

**Entrenamiento:** 8.000 filas, 13 columnas, 50 identificadores de máquina;
7.729 etiquetas negativas y 271 positivas (3,3875%). Sin timestamp. SHA-256:
`1cce2859f4833b63dbf0992868884e5deac6f79e4d74a245abbc484d34e396ce`.
No se encontraron celdas vacías, fallos de conversión numérica, dominios numéricos
inválidos ni filas completamente duplicadas en ese archivo.

Hay 7 filas positivas sin ningún subtipo activo y 14 negativas con algún subtipo
activo. Se conservan sin «arreglar» la etiqueta por OR. La descripción del origen
y estas discrepancias deben interpretarse por separado: no se atribuye una causa
sin examinar el proceso de adaptación del dataset.

**Batches:** cuatro snapshots íntegros, 40 filas, dos días (15 y 16 de octubre).
Se eligieron el primero y el último conservados por día; no es una muestra
aleatoria ni una copia completa del share. Cada archivo tiene header, UTF-8,
14 columnas (timestamp más las 13 anteriores) y 10 filas. Cada snapshot conserva
su hash y tamaño en inventory.json. Los del día 15 se reutilizan de evidencia
previa del PR30, sin importar contratos o modelos de ese PR.

Todas las 40 etiquetas globales de estas muestras son 0. No se encontraron vacíos,
conversiones numéricas inválidas, etiquetas fuera de 0/1 ni filas completas
duplicadas dentro de cada archivo. Esto no demuestra ausencia de fallos en los
demás batches. En conjunto se observaron 23 identificadores de máquina.

## Diccionario y unidades

- `machine_id`: identificador de máquina asignado por el entorno de laboratorio;
  no se ha probado su correspondencia con una identidad física o estable entre sesiones.
- `machine_type`: categoría H/M/L, observada y registrada por archivo.
- `air_temp_K`: temperatura del aire, número, Kelvin.
- `process_temp_K`: temperatura de proceso, número, Kelvin.
- `rpm`: velocidad de giro, número, revoluciones/minuto.
- `torque_Nm`: par, número, N·m.
- `tool_wear_min`: desgaste de herramienta, número, minutos.
- `machine_failure`: etiqueta contemporánea binaria 0/1.
- `failure_TWF`: indicador de fallo por desgaste de herramienta.
- `failure_HDF`: indicador de fallo por disipación térmica.
- `failure_PWF`: indicador de fallo por potencia.
- `failure_OSF`: indicador de fallo por sobreesfuerzo.
- `failure_RNF`: indicador de fallo aleatorio.
- `timestamp`: solo en los batches; fecha/hora UTC Z de emisión de la simulación.

Los seis últimos indicadores de fallo son etiquetas/resultados, no sensores para
inferir la propia etiqueta. No hay datos de vibración. Los rangos observados de
cada variable están en inventory.json; no son límites físicos garantizados.

## Fechas, identidad y novedad de las observaciones

El listado SMB congelado del día 16 contenía 124 nombres, secuencia 1–124 sin
saltos. Hubo 122 intervalos de 30 segundos y uno de 31 segundos entre nombres.
No se han leído las filas de los 124 archivos: no se extrapola el número total
de filas o su cobertura por máquina. El listado es una observación puntual.

En las dos muestras del día 16 la hora del nombre y el timestamp interno coinciden
en UTC. La modificación mostrada por el cliente SMB está dos horas por delante,
coherente con Europe/Madrid ese día. No se deduce la zona configurada en el servidor.
El mtime no se usa como event-time ni se asigna a las filas de entrenamiento.
No se ha conservado mtime SMB del día 15: no se inventa esa comparación.

Todos los registros de cada muestra comparten la fecha/hora del lote. En tres
archivos existen estados de sensores distintos para el mismo `(machine_id, timestamp)`:
2 grupos en el primer batch del día 15, 2 en el primero del día 16 y 1 en el último
del día 16. Son 5 grupos en total. No son filas exactamente duplicadas y no deben
eliminarse automáticamente por esa pareja de campos. CG02 mide el problema;
la identidad/deduplificación operativa corresponde a la siguiente fase.

Al comparar tipo, cinco sensores y seis etiquetas, ignorando timestamp y machine_id,
las 40 filas tienen 30 firmas distintas y 10 repeticiones más allá de la primera.
Ninguna de esas 40 firmas coincide exactamente con el entrenamiento conservado.
Cero coincidencias en este muestreo pequeño **no prueba independencia** ni partición
correcta del generador. Una hora o un identificador nuevos no hacen nueva una
observación que repite el mismo estado AI4I.

El servidor no ofrece retención, según el usuario. La conservación propia debe
capturar antes de que desaparezca la fuente: Parquet y consultas DuckDB son la
continuación acordada en CG06. La organización Bronze/Silver/Gold es un diseño
pendiente de configurar, no una propiedad automática de NiFi. Los snapshots de
CG02 son evidencia acotada, no ese servicio de retención.

## Decisión sobre el objetivo

**Clasificación del estado actual: viable como tarea de laboratorio.** Hay sensores
y `machine_failure` contemporáneo en el training. Las discrepancias de etiquetas,
la procedencia sintética y la limitación de identidad deben acompañar la evaluación.
No se entrena ni se elige un modelo aquí.

**Predicción de fallo en las próximas 24 horas: no validada con la evidencia actual.**
El training carece de fechas; los batches dan hora de emisión y etiquetas del estado
observado. No se dispone de seguimiento completo por máquina a 24 horas, eventos
independientes de inicio de avería/mantenimiento ni identidad temporal verificada.
Las cuatro muestras cubren instantes separados de dos sesiones, no un seguimiento
continuo. Acumular más batches habilitará análisis, pero no garantiza resolver esas
condiciones ni crear automáticamente una etiqueta futura válida.

Esta conclusión satisface la decisión pedida en CG02: la issue permite determinar
que el horizonte no es validable. No requiere inventar mantenimiento, conseguir
un ledger inexistente o implementar CG06 antes de entregar el inventario.

## Procedencia y licencia

El [registro primario de UCI](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset),
consultado el 2026-10-16, describe AI4I como datos sintéticos y publica unidades,
etiquetas y licencia CC BY 4.0. Referencia: *AI4I 2020 Predictive Maintenance Dataset*
[Dataset] (2020), UCI Machine Learning Repository, DOI `10.24432/C5HS5C`.

Se mantiene esa atribución y se indican las adaptaciones de aula conocidas:
subconjunto de 8.000 filas, nombres de columnas y machine_id. No se dispone del
código/seed de preparación ni del generador, por lo que no se certifica la cadena
completa de transformación o equivalencia byte a byte con UCI. La licencia del
original está comprobada; la ausencia de detalles de adaptación está documentada.

## Aceptación y cierre de la issue

Trazabilidad con los requisitos:

- R01: sources.json separa entrenamiento, registros SMB y mantenimiento no aportado.
- R02: referencia primaria, licencia/atribución y límites de procedencia documentados.
- R03: bytes, hashes, header, encoding y recuentos por archivo en inventory.json;
  originales y snapshots conservados; comando offline de verificación.
- R04: tipos, unidades, categorías, rangos, vacíos, duplicados y etiquetas medidos.
- R05: listado de nombres/mtime congelado, tiempo interno, días, máquinas y conflictos;
  carencias de continuidad y contexto de mantenimiento explícitas.
- R06: clasificación contemporánea viable / horizonte 24h no validado, con razones.
- R07: informe, manifiesto, evidencia y pruebas entregados sin contraseñas ni conexión
  obligatoria al servidor.

El PR permite revisar y aceptar la entrega técnica de CG02. Para marcarla resuelta:

- [ ] Revisar este informe y la evidencia, y ejecutar `--check` y las pruebas.
- [ ] Aceptar explícitamente la conclusión sobre el horizonte de 24 horas y el alcance de laboratorio.
- [ ] Registrar o confirmar el acuerdo de alcance de CG01 (#1), que sigue abierta;
  CG02 no afirma haber completado ese acuerdo por el resto del equipo.
- [ ] En el momento del merge, realizar la validación prevista por el equipo y fusionar el PR.
- [ ] Cerrar CG02 y actualizar su estado solo después de esa aceptación.

No hay auto-cierre, auto-merge, nuevas ejecuciones de CI ni cambios del servidor.
Parquet/DuckDB, schemas, inferencia y modelos quedan fuera de este PR.
