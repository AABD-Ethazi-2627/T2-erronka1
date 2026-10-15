# CNC Guard — Hasteko Argibideak

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
| NiFi | https://localhost:8443 | admin / adminpassword123 |
| Kibana | http://localhost:5601 | — |
| Elasticsearch | http://localhost:9200 | — |
| Scoring API | http://localhost:8000/docs | — |

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

## Datuen inbentarioa

[CG02: datu-iturrien eta etiketaren bideragarritasunaren azterketa](docs/data/INBENTARIOA.md).

## Offline entrenamendua

[AI4I entrenamendua, emaitzak eta mugak](docs/data/ENTRENAMENDUA.md).
Notebook exekutatua: [02_training_AI4I.ipynb](notebooks/02_training_AI4I.ipynb).

```bash
python -m scripts.train_model
python -m pytest -q
```

### RF fintzea eta Isolation Forest

[F1/F2 emaitzak, mugak eta integrazio lokala](docs/data/FIN_SINTONIA.md).
Notebook exekutatua: [03_refinement_AI4I.ipynb](notebooks/03_refinement_AI4I.ipynb).

```bash
python -m scripts.refine_model --jobs 2 --output models/offline-ai4i-v2
```

Artefaktuak lehendik badaude, beste irteera-karpeta bat hautatu; ez dira gainidazten.
