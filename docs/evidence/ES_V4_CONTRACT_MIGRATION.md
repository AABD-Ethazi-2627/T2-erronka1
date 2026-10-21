# Contrato v4 y mapping estricto de Elasticsearch

Corrección F1 sobre PR42, base `28a77543bfd67a36b96ddc2f4acc103b13f62c2e`.
El cambio añade `prediction_scope: keyword`, `temporal_prediction_enabled: boolean`
y `score_semantics: keyword` al template compartido por telemetría y alertas.
Conserva `dynamic: strict`, los metadatos y los contratos de entrada/salida.

## Causa y cobertura

`scoring/score_api.py` devuelve los tres campos y valida la respuesta contra
`contracts/prediction.schema.json`, donde son obligatorios. El export
`nifi-flows/cnc_lab_completed.json` conecta `InvokeHTTP/Response` con
`EvaluateJsonPath` en modo `flowfile-attribute`; sus salidas `matched` alimentan
`PutElasticsearchJson` y `RouteOnAttribute/alert → Put alerts`. Ninguno transforma
el cuerpo de respuesta. Ambos sinks usan `cnc.event_id` como identificador.

El mapping anterior no declaraba los tres campos. Según la
[referencia oficial de dynamic](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dynamic),
`strict` rechaza documentos con campos nuevos. La regresión comprueba todo el
contrato, incluido `source`, además de una respuesta real de `/predict` con
modelos sintéticos pequeños, cargados mediante el lifespan y hashes normales.
No carga pickles publicados, entrena modelos de entrega ni evalúa el test final.

La inspección de conexiones y expresiones NiFi es estática: no ejecuta sus
procesadores. El payload HTTP sí procede de la API ejecutada en un transporte
ASGI de HTTPX, con el lifespan real de la aplicación.
El manifiesto de fixture declara el alcance que exige la API, pero su versión
`synthetic-es-contract-test-only` identifica que no acredita procedencia ni calidad
del modelo de entrega. No se usa fuera de la prueba.

| Criterio relacionado | Aportación de esta corrección | Pendiente |
| --- | --- | --- |
| CG14 | Protege el contrato de salida de la ruta exportada, sin retirar metadatos. | Ejecución NiFi, errores/reintentos y archivo integrado. |
| CG16 | Respuesta API compatible con ambos destinos definidos. | Cadena distribuida v4 con NiFi real. |
| CG18 | Campos y tipos explícitos, conservando strict. | Migración autorizada de índices existentes y retención. |
| CG20 | Regresión acotada del límite API/mapping. | Conciliación por etapa, archivo, paneles y latencias. |
| CG28 | Ejercita lifespan, hashes y salida del endpoint real. | Concurrencia y aceptación del bundle de entrega. |

Ninguna fila acredita E2E completo ni aceptación humana. Los ensayos históricos
de CG16/CG18/CG20 corresponden a sus revisiones originales.

## Índices existentes: procedimiento propuesto, no aplicado

Actualizar un template solo afecta a índices creados posteriormente; no cambia
los ya existentes. Véase la
[API oficial de index templates](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-indices-put-index-template).
No ejecutar los ejemplos siguientes en un servicio compartido sin la autorización
de su responsable. No se ha consultado ni modificado ningún mapping de servicios
compartidos.

1. Inventariar índices concretos de ambos sinks, aliases y template efectivo.
   Las expresiones del export seleccionan `cnc-telemetry-lab-v2`,
   `cnc-telemetry-smb-v1`, `cnc-alerts-lab-v2` y `cnc-alerts-smb-v1`.
   Comprobar cuáles existen y si sus mappings/aliases coinciden; no crearlos ni
   actualizarlos a ciegas ni usar comodines para alcanzar índices ajenos.
2. Guardar mappings, settings, aliases, recuentos y muestras por `event_id`.
   Revisar colas/rechazos y acordar una pausa controlada de escritura/replay;
   conservar la evidencia original. No descartar rechazos para cuadrar cuentas.
3. Ensayar con una copia desechable del mapping real. Si los tres campos están
   ausentes o ya tienen exactamente los tipos previstos, actualizar el template
   aprobado y añadir los campos a **cada índice concreto existente** mediante
   la [API oficial de mapping](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-indices-put-mapping).
   Ejemplo de petición para un solo índice expresamente seleccionado:

   ```http
   PUT /<indice-concreto-verificado>/_mapping
   {
     "dynamic": "strict",
     "properties": {
       "prediction_scope": {"type": "keyword"},
       "temporal_prediction_enabled": {"type": "boolean"},
       "score_semantics": {"type": "keyword"}
     }
   }
   ```

4. Si hay tipos incompatibles, detener la actualización. Preparar otro índice
   con el mapping corregido y una reindexación revisada. Los sinks actuales
   escriben nombres concretos, por lo que una estrategia de alias requiere
   coordinar sus destinos; no basta con crear un alias nuevo. Ese cambio y su
   ejecución quedan fuera de este PR.
5. Leer el mapping efectivo, probar un evento v4 sin etiquetas y verificar
   `_id`, `_source`, hash, versión y alcance en telemetría y en la rama de alertas.
   Repetir el mismo ID y comprobar el conteo estable. Confirmar que un campo
   desconocido sigue siendo rechazado. Conciliar rechazos/replay por ID antes
   de reanudar. Las actualizaciones de mapping no rellenan documentos históricos
   ni recuperan documentos previamente rechazados por sí solas.
6. Ante un fallo, pausar el replay y conservar colas/evidencias. Añadir mappings
   no permite después eliminar campos o cambiar sus tipos para deshacerlo;
   preparar recuperación mediante el índice anterior o un índice nuevo, sin
   borrar datos. No retirar los campos de alcance de la API para evitar el error.

## Reproducción local acotada

En Fedora WSL explícita, desde este checkout y con Python soportado por el lock:

```sh
uv sync --frozen --python 3.12
uv run --frozen python -m unittest discover -s tests -p 'test_elasticsearch_contract.py' -v
```

No ejecutar `experiment_rf`, `experiment_anomaly` ni `package_model` para esta
regresión: crea sus propias fixtures temporales y las elimina al terminar.
La migración compartida y el ensayo NiFi completo siguen pendientes.

La prueba real de ES es optativa y se ejecuta aparte de `unittest discover`:

```sh
docker pull docker.elastic.co/elasticsearch/elasticsearch:9.5.4
PYTHONPATH=.:tests uv run --frozen python tests/verify_elasticsearch_contract.py \
  --output outputs/es-contract/live.json
```

Exige la imagen local, no hace pull por sí misma, no usa Compose ni una URL ES
externa y se niega a sobrescribir evidencia. Crea un contenedor con nombre único,
red `none`, sin puertos publicados ni volúmenes persistentes, datos en tmpfs,
límites de CPU/memoria y llamadas por `docker exec` a su propio loopback. Elimina
solo ese contenedor al acabar, también si falla. Requiere el commit base completo
para contrastar el mapping anterior con `git show`.

## Resultado local del 21/10/2026

Ver [registro compacto](ES_V4_CONTRACT_20261021.json). En FedoraLinux-43,
Python3.12.15 y dependencias frozen:

- Los dos tests nuevos fallaron con el mapping anterior y pasan con el corregido.
  Cubren todos los campos/tipos de prediction/source y respuestas reales de la API
  para ambas procedencias, con inspección de las conexiones/propiedades NiFi.
- ES9.5.4 desechable:44 operaciones HTTP verificadas. El mapping antiguo rechaza
  la respuesta con400/strict_dynamic_mapping_exception; actualizar solo el template
  mantiene ese400 en el índice existente. La ampliación explícita de su mapping
  permite201 y lectura idéntica. Los cuatro destinos nuevos aceptan la respuesta
  de su procedencia, conservan `_source` y cuentan1 después del reintento.
  Campos desconocidos de raíz/source y booleano inválido reciben400.
- Suite:106 tests descubiertos,103 OK y3 omitidos por no existir el bundle de
  entrega. Esos tres tests siguen pendientes; la nueva regresión usa su propio
  bundle sintético y no se omite. Se observaron ResourceWarning de streams anyio
  en la suite completa. La ejecución separada de los104 tests heredados pasó con
  las mismas3 omisiones, sin emitirlos. No se suprimen ni se atribuye aquí su causa;
  la suite completa no se presenta como libre de warnings.

El campo `source.kind=smb_csv` se prueba como valor del contrato con URI de fixture;
no se lee SMB. No se ejecutan NiFi/Kafka/Filebeat/Kibana, latencias del pipeline,
modelos de entrega, infraestructura compartida ni migración de índices reales.

## Corrección de los residuales de revisión

Sobre el head revisado `0272276a77f6b42c6164e4772590854bbb48dace`:

- Ruff Windows 0.17.1: imports ordenados y `check=False` explícito en la sonda
  de disponibilidad. Un retorno no cero forma parte de la espera intencional;
  las peticiones de verificación siguen usando `check=True`. Sin `noqa` nuevos.
- El caso mínimo `with TestClient(FastAPI())` reproduce el defecto ajeno al
  scoring: tres ciclos, `gc.collect(2)` y ResourceWarning como error producen
  seis excepciones no propagables de streams AnyIO sin cerrar. No demuestra
  una fuga en producción. El [código de Starlette 0.37.2](https://github.com/encode/starlette/blob/0.37.2/starlette/testclient.py)
  deja abiertos ambos extremos de `stream_receive`; la
  [corrección upstream #2693](https://github.com/Kludex/starlette/pull/2693)
  se publicó en [Starlette 0.38.6](https://starlette.dev/release-notes/#0386-september-22-2024).
- [FastAPI 0.111.0 exige Starlette >=0.37.2,<0.38.0](https://github.com/fastapi/fastapi/blob/0.111.0/pyproject.toml).
  No se fuerza una versión incompatible ni se amplía la actualización de
  dependencias. `pyproject.toml`, `uv.lock` y el código de producción permanecen
  sin cambios en esta corrección.
- Las pruebas usan ahora el [transporte ASGI público de HTTPX](https://www.python-httpx.org/advanced/transports/#asgi-transport),
  también descrito en las [pruebas async de FastAPI](https://fastapi.tiangolo.com/advanced/async-tests/).
  `tests/api_client.py` entra y sale del contexto lifespan de la aplicación:
  HTTPX no lo ejecuta automáticamente. No se modifican las clases de Starlette
  ni sus streams internos. Se conserva la carga y descarga real de las fixtures,
  las comprobaciones de readiness y las validaciones de petición/respuesta.
  Dos regresiones comprueban cierre del cliente y shutdown con respuesta normal
  y con excepción de la aplicación, que sigue propagándose. El shutdown usa
  `AsyncExitStack.aclose()` sin inyectar esa excepción en el lifespan, igual que
  el ciclo independiente de TestClient. El caso de error se comprobó primero
  en rojo con un lifespan que limpia después de `yield`, como el de scoring.

`-W error::ResourceWarning` por sí solo no convierte las excepciones de `__del__`
en fallos de proceso. `tests/verify_resource_cleanup.py` añade recolección de
generación 2 después de cada test y al terminar cada suite; registra y muestra
las excepciones de `sys.unraisablehook`, y falla si aparece cualquiera de ellas.
No suprime warnings. Repite la suite dos veces y exige los mismos IDs y orden de
descubrimiento. Para reproducir con el entorno frozen anterior:

```sh
outputs/venv/bin/python tests/verify_resource_cleanup.py
```

La evidencia de esta ejecución se registra por separado en
[ES_V4_CONTRACT_HYGIENE_20261021.json](ES_V4_CONTRACT_HYGIENE_20261021.json);
el JSON anterior conserva los resultados históricos del head original.

La validación final repite 108 tests: 105 correctos y tres omitidos en cada
pasada, sin ResourceWarning ni excepciones no propagables con GC forzado.
El control negativo con dos streams deliberadamente abiertos termina con
código 1 aunque su unittest termine correctamente. El ensayo de ES desechable
repite las 44 operaciones y elimina su contenedor, sin warnings de recursos.
Ruff Windows 0.17.1, formato, auditoría inmutable CG02 y layout pasan localmente.
La revisión independiente del cambio, el CI del nuevo head y los tres tests
que requieren modelos de entrega quedan separados de estos resultados locales.
