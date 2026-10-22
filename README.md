# CNC Guard — Hasteko Argibideak

## Dokumentazioa eta errubrika

[Dokumentazioaren aurkibidea](docs/README.md) · [Errubrika eta ebidentzien jarraipena](docs/rubrica/README.md).

## 1. NFS karpeta muntatu (behin bakarrik)

```bash
sudo mkdir -p /mnt/cnc-stream
sudo mount ZERBITZARI_IP:/opt/cnc-stream /mnt/cnc-stream
ls /mnt/cnc-stream/   # CSV fitxategiak ikusi behar dituzu
```

## 2. Zerbitzuak abiarazi

```bash
docker compose up -d --build
docker compose ps     # 6 zerbitzu "running" ikusi behar dituzu
```

| Zerbitzua | URLa | Erabiltzailea / Pasahitza |
|---|---|---|
| Kafka | kafka:9092 (Docker barnetik) | — |
| NiFi (laborategi osoaren adarretan) | https://localhost:8443 | Ingurunean konfiguratutako kredentzialak |
| Kibana | http://localhost:5601 | — |
| Elasticsearch | http://localhost:9200 | — |
| Scoring API | http://localhost:8000/docs | — |

`docs/templates/infra/docker-compose.yaml` es la plantilla histórica canónica
(antes `infra/`), con Filebeat y scoring propios. No sustituye al Compose principal.
Para validarla sin arrancar servicios:

```bash
# Valores ficticios solo para validar; configurar credenciales reales fuera de Git.
CNC_NIFI_PASSWORD=validation-only-password CNC_STREAM_DIR=/tmp/cnc-fixture \
  docker compose -f docs/templates/infra/docker-compose.yaml config --quiet
python3 scripts/check_lab_compose.py
```

Exige `CNC_NIFI_PASSWORD` (al menos 12 caracteres para NiFi) y `CNC_STREAM_DIR`
(directorio local ya montado). No guarda credenciales CIFS en Docker.
Por defecto publica todos los puertos en loopback y permite los Host HTTP
`localhost:8443,127.0.0.1:8443` en NiFi. Para acceso LAN autorizado, configurar
ambas variables antes de usar esta plantilla:

```bash
export CNC_LAN_BIND_IP=192.0.2.10  # sustituir por la IP LAN concreta del servidor
export CNC_NIFI_PROXY_HOST=192.0.2.10:8443  # Host de la URL externa, sin https:// ni ruta
# Si se usa DNS: CNC_NIFI_PROXY_HOST=cnc-lab.example:8443
# Varios Host exactos: lista separada por comas, cada uno con :8443.
```

`CNC_LAN_BIND_IP` solo cambia la publicación Docker de NiFi.
`CNC_NIFI_PROXY_HOST` configura `NIFI_WEB_PROXY_HOST` / `nifi.web.proxy.host`:
es una allowlist de cabeceras HTTP Host, no emite certificados ni añade SAN ni
confianza TLS. Acceder mediante `https://<host-configurado>:8443/nifi/` requiere
provisionar previamente un certificado de servidor cuyo SAN incluya ese DNS
(o SAN de tipo IP si se accede por IP), su clave privada y cadena en el keystore
de NiFi, y confiar en la CA emisora en cada cliente. El certificado autogenerado
para el hostname del contenedor no garantiza cobertura de la IP/DNS externa.
No ignorar errores TLS ni desactivar HTTPS/autenticación. Esta plantilla no
provisiona certificados ni acredita acceso LAN operativo.

Fuentes oficiales: [start.sh de NiFi 1.25.0](https://github.com/apache/nifi/blob/rel/nifi-1.25.0/nifi-docker/dockerhub/sh/start.sh)
(mapea la variable y avisa si falta en modo seguro) y
[guía de administración, Proxy Configuration y Security Configuration](https://nifi.apache.org/docs/nifi-docs/html/administration-guide.html).
Kafka, Elasticsearch, Kibana y scoring siguen en `127.0.0.1`; usar un túnel SSH
individual, por ejemplo `ssh -L 8000:127.0.0.1:8000 usuario@servidor` para la API.

## 3. Proiektuko fitxategiak

```
cnc-guard/
├── filebeat/
│   └── filebeat.yml          ← 1. fasea: ZURE ZEREGINA (osatu — Kafka outputera bideratu)
├── scoring/
│   └── score_api.py          ← 3. fasea: ZURE ZEREGINA (osatu hutsuneak FastAPI-n)
├── nifi-flows/
│   └── cnc_fase1_INCOMPLETO.json  ← 1. fasea: NiFi-n inportatu eta osatu (ConsumeKafka jada konfiguratuta)
├── notebooks/
│   └── 02_training_TEMPLATE.ipynb ← 2. fasea: ZURE ZEREGINA (osatu)
├── models/                   ← 2. fasea: hemen gorde model.pkl
└── data/
    └── ai4i2020_train.csv    ← entrenamendurako datuak
```

## 4. Erronkaren dokumentua

`ENUNTZIATUA.md` irakurri — hiru faseetan zer egin azaltzen du.

## Planning automatikoa

[Project #2 → #1 sinkronizazioa, 8 orduro](docs/PROJECTS_SYNC.md).
