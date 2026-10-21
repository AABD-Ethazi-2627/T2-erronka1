# Respuestas canónicas de scoring

`POST /predict` conserva el esquema de telemetry/prediction 0.1.0. Un 200
representa una respuesta validada y confirmada en el ledger SQLite local antes
de entregarla por HTTP. `scored_at` identifica esa inferencia confirmada, no cada
intento HTTP. No se introducen IDs de intento ni se cambia el archivo.

## Identidad y conflictos

Antes de validar Telemetry, el API limita el cuerpo completo a 32.768 bytes
(413 si los supera, también con transferencia fragmentada) y a 64 contenedores
JSON anidados. Superar la profundidad o fallar sintaxis/modelo de entrada da
422 con diagnóstico fijo acotado, sin `input` ni contexto de validación. Las
comillas, escapes y bytes UTF-8 dentro de cadenas no cuentan como estructura.
Estos rechazos no llaman a scoring ni abren el ledger. El manejador sólo trata
`RequestValidationError`; MemoryError y errores internos no se convierten en
422. Una petición Telemetry válida con bundle inválido/ausente conserva 503.

- `event_id` queda vinculado a **todo** el telemetry validado, incluidos source,
  máquina y timestamp. El orden de las claves JSON y las representaciones
  numéricas normalizadas al mismo JSON por Pydantic no crean otra ocurrencia
  (por ejemplo, un sensor `1500` y `1500.0`).
- La clave de respuesta es `(event_id, model_artifact_sha256, policy)`, igual a
  la identidad de prediction del archivo. El hash corresponde a `rf.pkl`.
- La configuración vinculada es el manifiesto completo validado al arrancar:
  ambos hashes RF/IF, versiones declaradas, model_version, policy, umbrales,
  features, alcance y metadatos. Incluso un cambio sólo documental del manifiesto
  causa conflicto: es una comparación conservadora que evita omitir un nuevo
  parámetro que pueda afectar a la inferencia.
  Una repetición con la misma clave y configuración devuelve la respuesta
  completa original, incluido `scored_at`, sin volver a inferir.
  La primera respuesta y su replay usan el mismo orden JSON, también en source:
  el cuerpo HTTP es idéntico byte a byte bajo el mismo contrato de serialización.
- Reutilizar un event_id con otro payload válido devuelve **409**. Cambiar la
  configuración bajo la misma clave de respuesta también devuelve **409**.
  No se oculta el conflicto devolviendo el resultado antiguo para otra entrada.
- Un nuevo hash RF o una nueva policy permite otra inferencia del mismo evento
  inmutable. Cambiar sólo el modelo IF, model_version, runtime declarado o un
  umbral requiere también una nueva policy (o un RF diferente), porque el archivo
  no distingue esos cambios por sí solos. No basta con renombrar model_version.
  Los artefactos deben corresponder a los hashes verificados al arrancar.
  Policy conserva el enum existente `f1`/`f2`: no admite nombres arbitrarios de
  despliegue. Si esas identidades ya están usadas para el evento, un cambio que
  mantenga RF necesita evolucionar explícitamente el contrato de policy o la
  identidad del archivo antes de desplegarlo; este parche no amplía ese enum.

Una nueva ocurrencia legítima exige su propio event_id asignado por la ingesta.
La API no reconcilia las identidades distintas de CG14 y Filebeat, ni deriva
event_id del payload. NiFi/los clientes deben tratar 409 como conflicto terminal
para reconciliación, no como fallo transitorio que se resuelve cambiando el ID.

## Persistencia y recuperación

`create_app(..., ledger_path=...)` permite aislar el ledger en tests. En operación,
`SCORING_LEDGER` selecciona el archivo; por defecto es `responses.sqlite3` junto
al manifiesto. Su directorio debe existir y ser escribible. Compose lo fija en
`/state/responses.sqlite3`, dentro del volumen `scoring-state`, con propietario
65532 preparado en la imagen. El bundle `/models` permanece de sólo lectura.
No compartir este SQLite por SMB/NFS, ni usar `:memory:`. Se necesita un sistema
de archivos local con los bloqueos y garantías de sincronización de SQLite.

`BEGIN IMMEDIATE` serializa inferencia y commit entre hilos/procesos que usan el
mismo ledger. `synchronous=FULL` conserva la respuesta antes de retornar. El
coste deliberado es un escritor a la vez y espera máxima de bloqueo de 30 s;
este cambio no acredita rendimiento ni capacidad distribuida. Distintas réplicas
con ledgers separados no ofrecen esta garantía conjunta.

- Fallo antes del commit: rollback; no hay 200 y se puede repetir la inferencia.
- Commit seguido de timeout, desconexión o respuesta perdida: repetir la misma
  petición recupera la respuesta confirmada, incluso tras reiniciar el proceso.
- Fallo de inferencia, validación o almacenamiento: 500 genérico, sin respuesta
  alternativa. Un ledger inaccesible/corrupto no se reemplaza automáticamente.
- Bundle ausente o inválido: 503, aunque exista una respuesta previa. El replay
  requiere una API preparada con la misma configuración.

El cliente debe conservar la petición y su identidad ante un resultado HTTP
incierto. Una respuesta 200 recuperable no prueba que ya se haya publicado o
archivado: la entrega downstream mantiene su delivery_id estable y sólo hace ack
tras su propio commit durable. El archivo sigue comparando todo el JSON y rechaza
un `scored_at` distinto bajo la misma identidad.

No borrar, truncar ni rotar este ledger de forma independiente del archivo y sus
backups. No hay TTL: eliminar una respuesta permite rescoring y puede volver a
provocar el conflicto original. Un despliegue sobre eventos archivados antes de
este cambio necesita reconciliar/importar sus respuestas canónicas con control
de identidad; el ledger nuevo no puede reconstruir sus timestamps. Esa migración
no está implementada aquí. El almacenamiento local se considera confiable; no
se pretende autenticar una modificación maliciosa del SQLite.

## Compatibilidad y límite de aceptación

No cambian los contratos JSON, el ID de Elasticsearch ni la detección de
conflictos del archivo. Sí cambian el significado de scored_at en reintentos,
la necesidad de almacenamiento escribible persistente y el 409 documentado.
Los clientes que suponían un nuevo resultado para cada POST deben adoptar este
contrato. Las pruebas usan dobles deterministas, SQLite y archivo reales; no
entrenan ni consumen el test final. No prueban NiFi/Kafka/SMB, modelos de entrega,
caída eléctrica, restauración de backups ni aceptación E2E de CG14.
