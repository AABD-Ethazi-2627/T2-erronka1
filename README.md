# CNC Guard — laboratorio reproducible

Clasificación del estado actual con AI4I2020, entrenada offline y servida por
FastAPI. Inferencia por lotes SMB → Filebeat → Kafka → NiFi → API → Elasticsearch
→ Kibana. No acciona máquinas ni acredita predicciones a 24 horas.

**Alcance confirmado20Oct:** entrenar exclusivamente con el CSV reducido docente.
NiFi retira etiquetas y fila CSV cruda antes de `/predict`; la API solo utiliza
cinco sensores y `machine_type`. El score representa clasificación contemporánea,
no porcentaje de desgaste ni probabilidad calibrada de fallo futuro. Fecha/ID solo
sirven para trazabilidad. ETA, RUL, estaciones y aprendizaje temporal quedan fuera
de la entrega; los experimentos históricos se conservan separados y no se cargan
en esta API. [Corrección y verificación](docs/evidence/CG17_CURRENT_STATE_SCOPE.md).

[Índice de evidencias: alcance vigente y registros históricos](docs/evidence/INDEX_2026-10-19.md)
· [Rúbrica y revisión pendiente](docs/rubrica/SEGUIMIENTO.md)
· [Enunciado original](ENUNTZIATUA.md) · [Documentación](docs/README.md).

## Entorno y experimentos

Python 3.11/3.12, DuckDB **2.0.0** y uv; el lock conserva las versiones.

El [contrato de plataforma](docs/PLATFORM_SUPPORT.md) distingue fsync POSIX de
recuperación Windows ante muerte del proceso. Windows no acredita persistencia
de metadatos ante pérdida de energía; las herramientas permiten exigir y
comprobar explícitamente el requisito de fsync de directorios.
[Migración, timestamps UTC y rollback](docs/DUCKDB_2_MIGRATION.md). Desde checkout limpio:

```bash
uv sync --frozen --python 3.11
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python -m scripts.audit_cg02 --check
uv run --frozen python -m scripts.build_history
uv run --frozen python -m scripts.experiment_rf
uv run --frozen python -m scripts.experiment_anomaly
uv run --frozen python -m scripts.report_thresholds
uv run --frozen python -m scripts.package_model
```

Los experimentos y empaquetado rechazan sobrescribir salidas; conservar anteriores.
`outputs/api/` debe contener manifest.json, rf.pkl e if.pkl propios, con hashes
coherentes. No cargar pickles descargados de terceros. Los modelos generados quedan
ignorados por Git; informes compactos y hashes están versionados en docs/evidence.

La API necesita un ledger local persistente y escribible para conservar respuestas
canónicas en reintentos. Compose usa el volumen `scoring-state`; fuera de Compose,
consultar [identidad, recuperación y conflictos 409](docs/SCORING_REPLAY_CONTRACT.md).

Opcional de clasificación: `scripts.experiment_smotenc` compara sobremuestreo dentro
de los folds. Los laboratorios temporales/estacionales y otros datasets son trabajo
histórico fuera del alcance confirmado; no forman parte del entrenamiento, empaquetado
ni despliegue de esta entrega. El test antiguo inspeccionado en PR29 se excluye:
las métricas actuales son de desarrollo.

## Laboratorio local

Docker Compose y memoria suficiente para seis servicios (NiFi/Elasticsearch usan
Java y Kibana usa Node). El laboratorio usa imágenes oficiales fijadas por digest:
NiFi **2.12.0**, Kafka **4.3.1** y Elastic **9.5.5**. Las referencias y su
verificador están en [deploy/images.json](deploy/images.json). La API instala
el grupo `runtime` de `uv.lock` con todas sus transitivas y hashes.

El proyecto Compose nuevo se llama **cnc-guard-lab-v2**: utiliza volúmenes nuevos
y conserva los del laboratorio anterior. Antes de ejecutarlo, leer la
[migración y restauración](docs/DEPENDENCY_MIGRATION.md); actualizar este código
no migra datos ni sustituye una instalación ya arrancada.

```bash
mkdir -p outputs/smb-stream outputs/stream
# Generar primero el bundle outputs/api con los comandos anteriores.
docker compose --profile dashboard config --services
docker compose --profile dashboard up -d --build
bash scripts/init_kafka_topic.sh
uv run --frozen python -m scripts.integration_preflight
```

`CNC_STREAM_DIR` permite una carpeta de fixtures completa de solo lectura.
El segundo input lee `outputs/smb-stream/`; usar `scripts/capture_smb.py --help`
y un `.env` privado 0600 para capturar archivos completos sin exponer secretos a
Filebeat. No se monta NFS, no se modifica el servidor ni hay un timer activado.
Usuario confirmó `smb://192.168.75.150/cnc-stream`; los snapshots históricos pueden
contener otra dirección de origen y se conservan con su procedencia original.

| Servicio | Dirección local |
|---|---|
| API / health | http://127.0.0.1:18001/health |
| API / OpenAPI | http://127.0.0.1:18001/docs |
| NiFi TLS | https://localhost:18080/nifi |
| Elasticsearch | http://127.0.0.1:19200 |
| Kibana | http://127.0.0.1:15601 |
| Kafka | kafka:9092, solo dentro de Docker |

NiFi conserva TLS y credenciales autogeneradas: no hay contraseña de ejemplo en
este README. Importar y revisar
`nifi-flows/cnc_lab_completed_nifi_2.12.0.json` en NiFi 2.12. El export mantiene
todos los componentes deshabilitados; configurar servicios de controlador y
comprobar relaciones/colas antes de habilitar el flujo. Las propiedades se han
migrado a los nombres de NiFi 2.12, conservando scripts y referencias de servicio.
`cnc_lab_completed.json` conserva el export anterior de NiFi 2.0 como procedencia.
El export final utiliza topics lab-v2/SMB-v1, cuarentena y retries acotados.
`scripts/nifi_client.py` es cliente local para revisión; su token privado no se
versiona y no forma parte del export. Requiere `CNC_NIFI_TOKEN_FILE` con ruta
absoluta a un archivo del usuario en modo `0600` y `CNC_NIFI_CA_FILE` con el
certificado de confianza de NiFi. Verifica TLS y el nombre `localhost`; no
acepta certificados sin validar. No ejecutar scripts temporales del equipo
como si fueran instalación portable.

En un laboratorio autorizado, instalar primero `elasticsearch/ingest-pipeline.json`
con `PUT /_ingest/pipeline/cnc-prediction-v1` y comprobarlo con
`GET /_ingest/pipeline/cnc-prediction-v1`. Después aplicar
`elasticsearch/index-template.json` con `PUT /_index_template/cnc-lab-v1`, antes de
crear índices e ingerir. Seguir el [procedimiento de instalación y comprobación](elasticsearch/README.md#instalación-y-rollback-en-un-laboratorio-propio):
el template exige ese pipeline final; si falta, incluso los documentos válidos
reciben HTTP400. El template no migra índices existentes.

`uv run --frozen python -m scripts.create_lab_dashboard` genera ahora
`kibana/cg19-review-source.ndjson` **sin conectarse a Kibana**; `--check` verifica
su reproducción. El candidato v2 incluye temperaturas, heatmap/casos offline,
últimos50 y KPI con denominadores. Importación y revisión humana siguen pendientes:
ver [CG19 vigente](docs/evidence/CG19_2026-10-21.md). El export
`kibana/acceptance-export.ndjson` conserva el ensayo histórico v1 y su rango absoluto;
no demuestra las vistas nuevas. Ambos excluyen el índice de montaje v1.

Elasticsearch sin autenticación está limitado a loopback/red Docker del lab;
no exponer estos puertos en una red compartida. Mononodo no aporta HA.
Preflight es estático y mantiene `ready=false`: la evidencia viva está en CG22.
Para parar sin borrar datos: `docker compose --profile dashboard stop`.
Conservar volúmenes y registros; no usar `down -v`.

## Entrega y colaboración

Una rama feat por issue, con dependencias apiladas y commits trazables en el índice.
Revisión humana y defensa pendientes antes de cerrar issues o atribuir nota.
[Sincronización Project #2 → #1](docs/PROJECTS_SYNC.md) necesita su secret con alcance
Project y activación administrativa; cambios locales no la activan por sí solos.

[Exploración de alternativas RF/GradientBoosting/CatBoost y anomalías](docs/evidence/CG08_ALTERNATIVAS.md):
comparación OOF y nested, costes y latencia; grupo opcional research.

[Dataset estacional sintético ampliado y curva de aprendizaje](docs/evidence/CG11_ESTACIONAL_V2.md):
investigación histórica fuera de la entrega, 245.376 filas y modelo sintético
experimental separado. No se carga en la API ni acredita forecast real.

[¿Se puede estimar tiempo hasta fallo con el SMB disponible?](docs/evidence/CG02_ETA_SMB.md)
Auditoría histórica de procedencia/continuidad; no acredita ETA y sus propuestas
temporales quedan fuera del alcance vigente.

## Rutas y archivos del repositorio

[Mapa de carpetas y política de archivos](docs/REPOSITORY_LAYOUT.md).
Ejecutar `python3 scripts/check_repository_layout.py` desde la raíz.

## CG14: validación e integración pendiente

La validación CG14 y el laboratorio RESTORE tienen un alcance separado de la guía activa anterior. Consultar [contrato](docs/CG14_VALIDATION_CONTRACT.md), [RESTORE](docs/CG14_RESTORE_E2E.md) y [plan de integración PR42](docs/CG14_PR42_INTEGRATION.md). El mock RESTORE no acredita scoring ni archivo durable integrados.

El [worker durable opt-in](docs/CG14_DURABLE_PIPELINE.md) conecta raw, API
canónica, archivo CG15 y ES opcional requerido. PR65 exige recibos `stored` o
`duplicate` por cada stream, incluso en replay; un rechazo persistido bloquea
el ACK. La API limita el cuerpo a 32.768 bytes y la profundidad JSON a 64,
con errores 422 acotados sin devolver la entrada. Véanse la
[corrección y sus límites](docs/evidence/DURABLE_PIPELINE_FIX_R2_20261021.md)
y la [matriz CG14](docs/CG14_ACCEPTANCE_MATRIX.md). La revisión padre y los
ensayos Apache Kafka/NiFi reales siguen pendientes.
