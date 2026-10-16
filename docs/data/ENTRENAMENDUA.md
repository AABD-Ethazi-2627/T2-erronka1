# AI4I — Offline entrenamendu erreproduzigarria

2026-10-15 · CG07, CG08 eta CG10 zereginen tokiko aurrerapena.
Ez dira zeregin horiek osorik amaitutzat ematen: CG06ko Parquet/DuckDB,
CG09ko Isolation Forest eta integrazio-probak egiteke daude.

## Exekuzioa

Biltegiaren errotik:

```bash
python -m scripts.train_model
python -m pytest -q
```

Lehen komandoak `models/offline-ai4i-v1/` sortzen du; lehendik badago,
ez du gainidazten. Beste exekuzio baterako `--output models/offline-ai4i-v2`
erabili. Ez erabili test emaitzak parametroak edo atalasea berriz aukeratzeko.

`notebooks/02_training_AI4I.ipynb` notebookak datuen azterketa eta gordetako
exekuzioaren emaitzak erakusten ditu. Jatorrizko irakaslearen TEMPLATE fitxategia
mantendu da. Ez dago kanpoko datuen deskargarik edo NFSren mendekotasunik.

## Metodoa

- CSV bera eta SHA-256 bera erabiltzen dira, inbentarioan dokumentatuta.
- Bost sentsore-aldagaiak: tenperaturak, rpm, torque eta tresna-higadura.
- Ez dira `machine_id`, `machine_failure` edo `failure_*` sarrera gisa erabiltzen.
  `machine_type` ez da lehen baseline honetan erabiltzen; ez da beharrezkotzat
  edo alferrikakotzat frogatu.
- Zatiketa ausazkoa eta estratifikatua: 5.600/1.200/1.200 errenkada,
  seed=42. Ez da kronologikoa eta ez ditu makina berriak ebaluatzeko taldeak bereizten.
- Medianen imputazioa eta eskalatzea Pipeline barruan, entrenamenduan soilik
  doituta. Ez dago etorkizuneko leiho asmaturik.
- RF: 200 zuhaitz, max_depth=12, min_samples_leaf=5,
  class_weight=balanced, random_state=42.
- Erreferentziak: beti zero eta class_weight=balanced erregresio logistikoa.
- RFren atalasea balioztatze-multzoan F1 maximizatuz hautatua (CG10);
  berdinketetan atalase txikiena. Baseline-ek 0,5 erabiltzen dute.
- Modelo bakoitzaren test multzoa behin ebaluatu da, aukeratutako konfigurazioa
  izoztu ondoren. Ez da RF berriro entrenatu: gordetako Pipeline-a ebaluatutakoa da.

## Benetako test emaitzak

Testean 1.200 erregistro eta 40 positibo daude.

- Beti zero: recall=0, precision=0, F1=0; 40 negatibo faltsu.
- Erregresio logistikoa: recall=0,850, precision=0,149, F1=0,254;
  TN=966, FP=194, FN=6, TP=34.
- Random Forest: recall=0,575, precision=0,590, F1=0,582;
  TN=1.144, FP=16, FN=17, TP=23. Atalasea=0,803118076109186.
- RF average precision=0,653 (precision-recall laburpena; ez trapezio bidezko PR-AUC).

RFk F1 hobea du baina 40 hutsegitetatik 17 galtzen ditu. Ez da nahikoa
industria-erabilgarritasuna baieztatzeko. Enuntziatuak recall lehenesten du;
CG10ek F1 bidezko hautaketa akademikoa eskatzen du. Desberdintasun hori taldeak
berrikusi behar du, eta beste hautaketa-irizpide bat probatuz gero test berri
independentea beharko da. Ez dago daturik benetako kostua, alarma/egun edo
24 orduko aurreabisua neurtzeko. `predict_proba` kalibratu gabeko puntuazioa da.

## Artefaktuak eta bateragarritasuna

- `models/offline-ai4i-v1/cnc_failure_model.pkl`: RF Pipeline osoa,
  aurreprozesatzea barne. Tokian sortutako fitxategi fidagarria soilik kargatu.
- `models/offline-ai4i-v1/report.json`: datuen eta modeloaren SHA-256,
  parametroak, partizioen jatorrizko errenkada-indizeak, metrikak eta bertsioak.
- `notebooks/requirements-offline.txt`: exekuzioan erabilitako bertsioak.

Tokiko exekuzioa Python 3.14rekin egin da; bertsio zehatza reportean dago.
`scoring/requirements.txt` fitxategiak scikit-learn 1.5.0 du;
modeloa 1.9.1ekin entrenatu da. Ez kopiatu APIaren `/models/cnc_failure_model.pkl`
bidera bateragarritasuna eta notebook/API parekotasuna egiaztatu arte.
APIa osatu gabeko txantiloia da; ez da zerbitzua edo Docker martxan jarri.

## Egiaztapena

13 proba gaindituta: plangintzako 10 eta entrenamenduko 3.
Entrenamenduko probek partizioen bereizketa eta erreproduzigarritasuna,
etiketa/azpimota/identifikatzaileen aurrean inferentzia aldaezina,
falta diren sentsoreen onarpena eta serializazioaren ondoko parekotasuna aztertzen dute.
Modeloaren hash-a eta berriz kargatutako inferentzia ere tokian egiaztatu dira.
