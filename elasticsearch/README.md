# Ingestión de predicciones CG18 / G68

El [template](index-template.json) selecciona `cnc-prediction-v1` como
`index.final_pipeline` para los índices nuevos `cnc-telemetry-*` y `cnc-alerts-*`.
El [export](ingest-pipeline.json), versión 1, se genera desde los contratos CG03:

```powershell
uv run --frozen python -m scripts.build_es_ingest_pipeline --check
```

## Responsabilidades y conectores

NiFi proyecta CSV/telemetría a las seis features y elimina las etiquetas del
input antes de scoring. La API valida el JSON Schema completo y devuelve la
respuesta canónica; el ledger conserva sus bytes y `scored_at`. El worker durable
valida esa respuesta, exige recibos de archivo y usa `_create` con el ID compuesto
de evento, artefacto de modelo y política. Estas responsabilidades no cambian.

ES valida la forma, campos requeridos, tipos sin coerción, constantes de estado
actual, enums, cadenas no vacías y límites numéricos antes de almacenar. Rechaza
campos desconocidos tanto raíz como `source`, incluidas etiquetas y `raw_record`.
No calcula scores, no rellena campos, no cambia IDs, fechas, `scored_at`, flags ni
`_source`, y no crea ground truth. No replica todo JSON Schema: los patrones de
identidad y el formato UTC exacto siguen perteneciendo a la API; el mapping valida
las fechas al escribir. Una simulación de pipeline no sustituye una escritura.

El pipeline final permite que NiFi `PutElasticsearchJson` y el worker usen sus
URLs actuales, sin modificar los exports ni el runner de PR68. También se ejecuta
con `?pipeline=_none`: ese parámetro desactiva el pipeline de petición, no el final.
El export NiFi antiguo conserva `index` con `event_id`; su replay no duplica filas,
pero puede sobrescribir un resultado distinto para el mismo evento. El worker usa
`_create` y compara el documento al recibir 409; el guard no convierte el conector
antiguo en un sink inmutable ni se atribuye esa garantía al grafo NiFi.

## Instalación y rollback en un laboratorio propio

Con un endpoint del laboratorio autorizado, instalar en este orden:

1. `PUT /_ingest/pipeline/cnc-prediction-v1` con `ingest-pipeline.json`.
2. `GET /_ingest/pipeline/cnc-prediction-v1`: cotejar el export y su `version: 1`.
3. `PUT /_index_template/cnc-lab-v1` con `index-template.json`.
4. Crear los índices nuevos y comprobar `GET /<indice>/_settings` y `/_mapping`.
5. Ejecutar `POST /_ingest/pipeline/cnc-prediction-v1/_simulate` con un array `docs`,
   cada elemento con `_index`, `_id` y `_source`; después escribir y consultar.

Reinstalar exactamente el export es idempotente. Una actualización concurrente
puede protegerse con `?if_version=<version-observada>`; ES incrementa la versión en
una actualización condicional exitosa. No usar ese incremento como identificación
del export: los hashes y la comparación del cuerpo identifican su contenido.
No reemplazar una versión existente de contenido distinto sin revisar el cambio.

Instalar un template **no migra índices existentes**. No se aplican settings,
reindexados ni migraciones sobre recursos compartidos en esta entrega. Para una
migración posterior se requieren inventario, backup, reconciliación y rollback
propios. Para revertir en un lab, restaurar el template anterior y los settings
previos de cada índice afectado antes de eliminar el pipeline. Con un pipeline
final inexistente, las escrituras fallan; no se admite una degradación silenciosa.

## Verificación reproducible

Desde la raíz, con Docker y la imagen ES 9.5.4 ya presente, definir `PYTHONPATH`
con la raíz y `tests`, y ejecutar con una carpeta D: que todavía no exista:

```powershell
$env:PYTHONPATH='.;tests'
uv run --frozen python tests/verify_es_ingest_pipeline.py --work-dir D:/lab-propio/g68-corrida1 --docker-via-wsl FedoraLinux-43
```

El verificador crea y elimina solo su contenedor, no conecta a ES del host y deja
datos/evidencia bajo esa carpeta. Comprueba un control negativo sin guard,
simulación válida repetida, rechazos, versión/CAS, preservación de `_source`,
pipeline final obligatorio, `_create`/409, conteo único y mapping estricto aislado.
La fixture construida usa metadatos v4 versionados; no ejecuta entrenamiento,
inferencia ni test final. [Resultados y límites](../docs/evidence/G68_ES_INGEST_20261022.md).

Referencias oficiales consultadas para este diseño:
[pipelines](https://www.elastic.co/docs/manage-data/ingest/transform-enrich/ingest-pipelines),
[settings de índice](https://www.elastic.co/docs/reference/elasticsearch/index-settings/index-modules).
La conducta se verifica además en ES 9.5.4 real.
