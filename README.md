# CNC Guard — laboratorio reproducible

Clasificación del estado actual con AI4I2020, entrenada offline y servida por
FastAPI. Inferencia por lotes SMB → Filebeat → Kafka → NiFi → API → Elasticsearch
→ Kibana. No acciona máquinas ni acredita predicciones a 24 horas.

[Índice final: ramas, métricas, comandos y límites](docs/evidence/INDEX_2026-10-19.md)
· [Rúbrica y revisión pendiente](docs/rubrica/SEGUIMIENTO.md)
· [Enunciado original](ENUNTZIATUA.md) · [Documentación](docs/README.md).

## Entorno y experimentos

Python 3.11 y uv; el lock conserva las versiones. Desde checkout limpio:

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

Opcionales: `scripts.experiment_smotenc` compara sobremuestreo dentro de los folds;
`scripts.seasonal_lab` genera un laboratorio temporal separado, sin entrenar
forecast ni convertir fechas inventadas en historial observado. El test antiguo
inspeccionado en PR29 se excluye: las métricas actuales son de desarrollo.

## Laboratorio local

Docker Compose y memoria suficiente para seis servicios (NiFi/Kibana son Java).
La imagen NiFi de este equipo es `iabd-nifi:2.0.0-local`; para otra máquina se debe
proporcionar esa imagen docente o validar `NIFI_IMAGE` compatible. No se afirma
portabilidad ya comprobada en una máquina limpia.

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
| NiFi TLS | https://localhost:18080/nifi; con `CNC_LAN_BIND_IP`, https://IP-LAN-DEL-SERVIDOR:18080/nifi |
| Elasticsearch | http://127.0.0.1:19200 |
| Kibana | http://127.0.0.1:15601 |
| Kafka | kafka:9092, solo dentro de Docker |

NiFi conserva TLS y credenciales autogeneradas: no hay contraseña de ejemplo en
este README. Importar y revisar `nifi-flows/cnc_lab_completed.json` en NiFi2.0;
configurar servicios de controlador y comprobar relaciones/colas antes de arrancar.
Para que los cuatro estudiantes accedan a NiFi desde la LAN, definir
`CNC_LAN_BIND_IP` con la IP LAN del servidor antes de iniciar Compose. Cada
cliente debe confiar en un certificado NiFi válido para esa IP o nombre; no
ignorar errores TLS. Kibana, la API y Elasticsearch siguen ligados a loopback
porque este laboratorio no les configura autenticación. Cada estudiante puede
abrir un túnel SSH individual, por ejemplo:

```bash
ssh -L 18080:127.0.0.1:18080 -L 15601:127.0.0.1:15601 -L 18001:127.0.0.1:18001 usuario@servidor
```

Después se abren `https://localhost:18080/nifi`, `http://localhost:15601` y
`http://localhost:18001/docs` en su propio equipo. Kafka solo se usa dentro
de Docker.
El export final utiliza topics lab-v2/SMB-v1, cuarentena y retries acotados.
`scripts/nifi_client.py` es cliente local para revisión; su token privado no se
versiona y no forma parte del export. Requiere `CNC_NIFI_TOKEN_FILE` con ruta
absoluta a un archivo del usuario en modo `0600` y `CNC_NIFI_CA_FILE` con el
certificado de confianza de NiFi. Verifica TLS y el nombre `localhost`; no
acepta certificados sin validar. No ejecutar scripts temporales del equipo
como si fueran instalación portable.

Aplicar `elasticsearch/index-template.json` como template antes de ingerir y crear
el dashboard con `uv run --frozen python -m scripts.create_lab_dashboard` o importar
`kibana/acceptance-export.ndjson`. La vista filtra índices de aceptación, conserva
el rango temporal del ensayo y no mezcla el montaje v1. Ver CG18/CG19 para pruebas.

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
245.376 filas; modelo experimental separado, sin mejora de precisión garantizada.

[¿Se puede estimar tiempo hasta fallo con el SMB disponible?](docs/evidence/CG02_ETA_SMB.md)
Auditoría de procedencia/continuidad y propuesta de criticidad por5/30/120min.
