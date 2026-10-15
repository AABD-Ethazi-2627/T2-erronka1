# RF fintzea eta Isolation Forest integrazioa

2026-10-15 · CG08/CG09/CG10 · Tokiko esperimentu erreproduzigarria.
Aurreko `offline-ai4i-v1` artefaktuak mantendu dira.

## Metodoa eta erreprodukzioa

```bash
python -m scripts.refine_model --jobs 2 --output models/offline-ai4i-v2
python -m pytest -q
```

Irteera-karpeta lehendik badago, komandoak uko egiten dio gainidazteari;
beste izen bat erabili. `notebooks/requirements-offline.txt` bertsioak erabili.
Entrenamendua eta inferentzia biltegiaren errotik exekutatu behar dira,
`scoring.model_features` modulu partekatua eskuragarri egon dadin.

Jatorrizko 5.600 entrenamendu-errenkadak eta 1.200 balioztatze-errenkadak
mantendu dira. Lehendik ikusitako 1.200 test errenkadak ez dira erabili:
ez bilaketan, ez atalaseetarako, ez emaitza berriak kalkulatzeko.

25 RF konfigurazio, lau zatiketa estratifikatu, seed=42. Hiperparametroen
espazioa eta hautatutako konfigurazio guztiak `report.json` fitxategian daude.
Ez da bilaketa exhaustiboa edo maximo globalaren froga. Hasierako parametroak
barne daude. `machine_type` one-hot bidez gehitu da. Aldagai eratorrien ablazioa:
`temp_diff`, `power_W = rpm * torque_Nm * 2π/60` eta `wear_torque`.
Azken horiek sentsoreetatik bakarrik eratortzen dira, etiketa edo matxura-azpimotarik gabe.

Medianen imputazioa CV fold bakoitzaren entrenamenduan soilik ikasten da.
Konfigurazio bakoitzaren OOF puntuazioetatik F1/F2 atalaseak kalkulatzen dira;
F1 eta F2 irizpide bakoitzerako konfigurazio bat hautatzen da. Konfigurazio
irabazleak 5.600 errenkadekin entrenatzen dira eta azken atalaseak balioztatzean
hautatzen dira. Ez da berrentrenatzen atalasea hautatu ondoren.

OOF metrika maximoak hautaketan parte hartzen dute: ez dira nested CV bidezko
estimazio independenteak. Balioztatze-metrikek ere atalase-hautaketaren baikortasuna
dute. Kanpoko datu independente berriak behar dira azken ebaluazio baterako.

## F1 eta F2 emaitzak

Balioztatze-multzoak 1.200 erregistro ditu, 41 hutsegiterekin.
Konparazio guztiek multzo bera erabiltzen dute; ez alderatu aurreko test metrikekin.

- Aurreko RF, F1 atalasea: precision=0,667, recall=0,634, F1=0,650;
  FP=13, FN=15, TP=26.
- F1 konfigurazio berria: precision=1,000, recall=0,732, F1=0,845, F2=0,773;
  FP=0, FN=11, TP=30. Atalasea=0,5506458333333333.
- F2 konfigurazio berria: precision=0,912, recall=0,756, F1=0,827, F2=0,783;
  FP=3, FN=10, TP=31. Atalasea=0,3679497423165187.

F2-k recall-i pisu handiagoa ematen dio: Fβ=(1+β²)PR/(β²P+R).
Ez du esan nahi negatibo faltsu bakoitzak ekonomikoki lau aldiz gehiago kostatzen duenik.
F2 aldaerak hutsegite gehigarri bat hautematen du hiru alarma faltsuren truke.
Ez da oraindik onartutako operazio-kosturik edo alarma-aurrekonturik.

F1 hautaketak OOF F1=0,912 du; F2 hautaketak OOF F2=0,879.
Bi hautaketek aldagai eratorriak eta `max_depth=8`, `max_features=1.0`,
`class_weight=None`, `n_estimators=200` erabiltzen dituzte.
`min_samples_leaf` 1 da F1en eta 5 F2n. Beraz, ez dira soilik atalase desberdinak:
bi konfigurazio bereizi dira. API prestaketaren lehenetsia F1 da (CG10),
eta F2 esplizituki hauta daiteke; ez dago produkzio-politika onarturik.

Balioztatze-erroreen ondorengo diagnostikoa (ez da erabili aldagai edo
parametro berriak aukeratzeko): F1en FNen artean 8 TWF, 2 HDF eta azpimotarik
gabeko 1 daude; F2n 9 TWF eta azpimotarik gabeko 1. Azpimotak ez dira
sarrera bihurtu. Horiek ez dute beren kabuz hutsegiteen kausa frogatzen.
F1=1 helburua ezin da bermatu; datu gehiago eta etiketen kalitatearen azterketa behar dira.

## Isolation Forest

CG09ko hasierako parametroak: `n_estimators=200`, `max_samples=256`, seed=42.
Entrenamenduko `machine_failure=0` erregistroak soilik erabiltzen ditu.
AI4Iko une bereko etiketa hori normaltasunaren hurbilketa da, ez industria-historia
balioztatua. Ez da etorkizuneko etiketa edo aurreko testik erabiltzen.

Puntuazioa `-score_samples` da: handiagoa, anomalia handiagoa.
Atalasea normal gisa etiketatutako balioztatze-erregistroen 99. pertzentila da,
`higher` metodoarekin. %1eko helburu esploratzailea da, ez erabiltzaileak
onartutako operazio-muga; berdinketek benetako tasa alda dezakete.

Atalasea=0,6338224044766037. 1.159 normaletatik 12 markatzen ditu (%1,035),
eta 41 hutsegiteetatik 0. Ez dago benetako anomalia-etiketarik; hutsegitearekiko
konparazioa diagnostikoa da soilik. Emaitza horrek ez du bermatzen anomalia
berriak hautemango dituenik. Ez dago IFk hutsegiteen detekzioa hobetu duen frogarik.

## Integrazio lokala

```python
import pandas as pd
from scoring.inference import load_bundle, predict_signals

bundle = load_bundle('models/offline-ai4i-v2')
sample = pd.DataFrame([{
    'machine_type': 'L', 'air_temp_K': 300.0, 'process_temp_K': 310.0,
    'rpm': 1500.0, 'torque_Nm': 40.0, 'tool_wear_min': 100.0,
}])
print(predict_signals(bundle, sample, policy='f1'))
print(predict_signals(bundle, sample, policy='f2'))
```

Erantzuna: `failure_score`, `risk_alert`, `anomaly_score`, `anomaly_alert`,
`policy`, `model_version`. Arriskua eta anomalia independenteak dira:
ez dago AND baldintzarik edo CNCa gelditzeko agindurik.
Ez da anomalia-puntuazioa hutsegite-probabilitate bihurtzen.

`load_bundle`-k hash-a eta sklearn/numpy/pandas/joblib bertsioak egiaztatzen ditu
kargatu aurretik. Hash-a osotasun-kontrola da, ez jatorriaren autentifikazioa:
tokian sortutako eta fidagarriak diren joblib fitxategiak bakarrik kargatu.
`score_api.py` txantiloia ez da ordezkatu edo abiarazi: HTTP eskema, eskaeren
kalitate-balioztatzea eta Docker/NiFi integrazioa ondorengo lana dira.

## Artefaktuak eta egiaztapena

`models/offline-ai4i-v2/`: `bundle.pkl`, `rf_f1.pkl`, `rf_f2.pkl`,
`isolation_forest.pkl`, `validation_scores.csv` eta `report.json`.
Reporteak modeloen hashak, bertsioak, bilaketa, parametroak, folden errenkadak,
IF entrenamenduko errenkadak eta baztertutako testaren identifikazioa jasotzen ditu.

`notebooks/03_refinement_AI4I.ipynb` exekutatutako notebookak emaitzak eta
inferentzia partekatua erakusten ditu, ereduak berriro entrenatu gabe.
Unitate-probek F2 kalkulua, sentsore-aldagaiak, IF normal-only entrenamendua,
puntuazioaren noranzkoa, bi abisuen independentzia eta hash/bertsio okerren
bazterketa egiaztatzen dituzte. Artefaktuak berriz kargatuta puntuazioak
`validation_scores.csv`-rekin eta metrikak reportarekin alderatu dira;
CV folden disjuntzioa eta IF jatorria ere egiaztatu dira.
