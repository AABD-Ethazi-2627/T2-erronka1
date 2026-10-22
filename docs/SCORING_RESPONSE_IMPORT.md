# Importación explícita de respuestas históricas

`python -m scripts.import_scoring_responses` valida por defecto. Sólo `--import`
escribe. Trabaja sobre una **copia local offline**, con API y consumidores detenidos
para esa copia; no descubre volúmenes, archivos históricos, modelos ni servicios.
No ejecuta inferencia, no cambia `scored_at`, no publica mensajes y no confirma ACK.
Es una operación administrativa separada del [replay HTTP](SCORING_REPLAY_CONTRACT.md).

## Evidencia de entrada

El operador aporta un bundle UTF-8 JSON `scoring-response-import.v1` con estas claves
exactas:

```json
{
  "version": "scoring-response-import.v1",
  "contracts": {"nombre.schema.json": "SHA256 de cada contrato compatible"},
  "configuration": {"manifiesto histórico completo": "sin completar metadatos"},
  "configuration_evidence": "referencia al manifiesto original conservado",
  "entries": [
    {
      "telemetry": {"file": "peticion-original.json", "sha256": "SHA256 de sus bytes"},
      "response": {"file": "respuesta-original.json", "sha256": "SHA256 de sus bytes"},
      "identity_evidence": [
        {"system": "cg14", "event_id": "ID original de 64 hex", "reference": "referencia original verificable"},
        {"system": "filebeat", "event_id": "el mismo ID", "reference": "referencia original verificable"}
      ]
    }
  ]
}
```

El fragmento muestra la estructura; los textos explicativos no son valores válidos
para una importación. No existe un generador que rellene evidencia ausente.
`contracts` debe coincidir con el diccionario completo de `contract_hashes()` del
checkout revisado. Esa comprobación detecta cambios de contrato; no demuestra por
sí sola qué contrato se utilizó en el pasado. Antes de preparar el bundle hay que
comprobar la compatibilidad con los registros conservados y su procedencia.

`configuration` es el manifiesto íntegro original, incluidos hashes RF/IF,
`versions`, `model_version`, `policy`, umbrales, features, alcance y cualquier
metadato adicional. Se conserva y compara entero, sin descartar claves. Se exige
además `--configuration` con el manifiesto de destino explícito, que debe ser
idéntico tras canonicalización JSON. No se leen pickle ni se cargan modelos para
suponer la configuración histórica. La API sigue necesitando un bundle válido y
preparado; importar respuestas no la convierte en ready.

Cada snapshot debe estar dentro del directorio del bundle, incluso tras resolver
symlinks. Los hashes se comprueban sobre los bytes leídos una sola vez. Hay límite
de 4 MiB por bundle, 1..1000 entradas, 32.768 bytes por snapshot/configuración y
64 contenedores JSON anidados. Se rechazan claves duplicadas, UTF-8 inválido,
NaN/Infinity, campos desconocidos, etiquetas/ground truth y contratos incompatibles.

La petición pasa por el modelo Telemetry vigente y su esquema. La respuesta debe
contener **todos** sus campos normalizados, sin diferencias, más una Prediction
válida con configuración, hashes y alertas coherentes. No se reconstruyen sensores
que falten en respuestas antiguas. Los bytes originales de petición se fijan con
su hash; el ledger guarda su representación Telemetry normalizada, como el API.
La respuesta se guarda tanto en su representación canónica como en BLOB exacto.
Los snapshots originales deben conservarse junto al bundle para auditar sus bytes.

## Identidad y procedencia

Todas las referencias de `identity_evidence` deben declarar el mismo `event_id`
que la petición y la respuesta. Los campos `system`/`reference` son evidencia
**aportada por el operador**, no autenticada ni verificada por una llamada externa.
Hay que conservar la fuente y su revisión; una cadena o un hash no prueba autoría.

El importador reconcilia ese ID con el payload completo del ledger y la clave
`(event_id, RF SHA256, policy)`. No deduce equivalencia por sensores, timestamp,
nombre de archivo ni número de fila. CG14 y Filebeat con IDs o source distintos
siguen siendo un conflicto, aunque parezcan describir la misma medición. No hay
`--force`, alias, retarget, regeneración de IDs ni modificación de archivos CG15.
Resolver una discrepancia de origen requiere evidencia y un cambio coordinado
revisado fuera de esta herramienta; no se puede dar por migrada aquí.

## Validación e importación sobre copias propias

Los siguientes comandos usan nombres relativos para una copia de laboratorio.
`BUNDLE_SHA256` representa el hash revisado externamente del bundle concreto.

```text
python -m scripts.import_scoring_responses copia/bundle.json --bundle-sha256 BUNDLE_SHA256 --configuration copia/manifest.json --ledger copia/responses.sqlite3
python -m scripts.import_scoring_responses copia/bundle.json --bundle-sha256 BUNDLE_SHA256 --configuration copia/manifest.json --ledger copia/responses.sqlite3 --validate
python -m scripts.import_scoring_responses copia/bundle.json --bundle-sha256 BUNDLE_SHA256 --configuration copia/manifest.json --ledger copia/responses.sqlite3 --import --backup copia/before-import.sqlite3
```

`--dry-run` equivale a `--validate`, también predeterminado. No crea un ledger
ausente ni un backup. `--import --create-ledger` autoriza crear un archivo nuevo;
su directorio debe existir. Un ledger existente exige un backup SQLite **nuevo**
antes de modificarlo. No se sobrescribe una ruta de backup existente. Si todo el
lote ya está importado exactamente, se devuelve `duplicate` sin escrituras ni un
nuevo backup. La salida sólo contiene modo y contadores; exit 1 rechaza, exit 2
indica argumentos CLI inválidos. No se imprimen los payloads rechazados.

Después de leer/validar todos los snapshots, `BEGIN IMMEDIATE` vuelve a comprobar
el estado bajo bloqueo de escritor. Todo conflicto se detecta antes de insertar.
El backup se toma desde otra conexión read-only mientras el bloqueo impide cambios
de otros escritores. Se comprueba su integridad y se sincroniza antes de insertar.
El lote completo, esquema auxiliar, bytes y referencias se confirma una sola vez
con `synchronous=FULL`. Fallos de validación, inserción o commit dejan cero entradas
parciales. Un fallo al crear un ledger puede dejar un archivo vacío, sin respuestas
confirmadas. No se elimina automáticamente ninguna evidencia de fallo ni backup.

Se rechazan copias WAL, incluso sin sidecars, y copias con WAL/SHM pendientes.
Validate también rechaza un journal pendiente para no ejecutar recuperación con
escrituras. Un `--import` explícito permite que SQLite recupere su propio journal
antes de comprobar el estado y tomar el backup; no se ignora ni borra manualmente.
Después de una interrupción, conservar la **copia propia** y sus sidecars antes de
reintentar. No copiar sólo el `.sqlite3` de un servicio activo.
Un mismo bundle completo puede reejecutarse; cambiar sus bytes, referencias,
configuración o respuesta para una identidad ya importada se rechaza. Para otro
lote, conservar el bundle original y preparar otro con sólo las nuevas entradas.

## Replay, rollback y límites

La API conserva los 409 por evento/configuración y 503 por bundle no preparado.
Para entradas importadas devuelve el BLOB original validado, incluidos espacios,
orden, UTF-8 y `scored_at`; el resto mantiene su serialización previa. No se puede
sustituir una respuesta que ya existía en el ledger por otros bytes, aunque su JSON
sea equivalente. El esquema auxiliar es aditivo; un API anterior lo ignora y
volvería a serializar JSON. **No volver a una versión anterior del API sobre un
ledger importado** si se necesita conservar esos bytes.

Antes de cualquier uso real, el responsable debe revisar el dry-run y probar
restauración en otra copia offline. Un rollback posterior al commit consiste en
restaurar el backup completo y verificarlo, con todos los escritores detenidos y
sin nuevas respuestas posteriores que puedan perderse. No borrar filas ni editar
estados para eludir conflictos. El backup sólo cubre scoring, no el archivo CG15,
worker, offsets o ES. Restaurarlos de forma independiente tras nuevas entregas
requiere una reconciliación coordinada adicional.

No pueden migrarse fielmente registros sin respuesta original/scored_at, petición
completa, manifiesto completo verificable, ambos hashes y runtime histórico,
procedencia/identidad estable, o con contratos incompatibles. Una proyección ES,
CSV, Parquet o JSON reserializado que perdió los bytes HTTP no acredita el cuerpo
original: no inventar esos bytes ni el tiempo de inferencia. Si sólo queda JSON
semántico, hace falta otro contrato de migración explícito; éste lo rechaza como
evidencia insuficiente en la revisión de entrada. La herramienta verifica los
hashes suministrados, pero no puede detectar que un operador los inventó.

SQLite local requiere bloqueos/sincronización adecuados; no usar SMB/NFS ni réplicas
con ledgers separados. Windows acredita recuperación de proceso en las pruebas,
no pérdida eléctrica. No hay migración de datos reales, modelos de entrega,
entrenamiento/test final, aceptación E2E ni cierre de issues12/14/15/21 por disponer
de esta CLI. Evidencia y revisión del padre se registran por separado.
