# CNC Guard — entrega-gida

2026-11-12ko tokiko paketea. Prestaketa teknikoa da; taldearen defentsa eta plataformako entrega oraindik egiaztatu behar dira.

## Edukia
- `notebooks/02_training.ipynb`: euskarazko azalpenak eta exekutatutako metrikak.
- `models/cnc_failure_model.pkl`: RF modeloaren kopia; APIaren jatorrizkoa `outputs/api/rf.pkl` da.
- `outputs/api/`: RF, IF eta bertsio/hash manifestua.
- `outputs/cg08/` eta `outputs/cg09/`: entrenamendu-txostenak eta balidazio-puntuazioak.
- `nifi-flows/`: NiFi esportazioak; uneko 2.12 fluxua README nagusian identifikatuta dago.
- `kibana/`: panelen esportazioak; `ebidentziak/` karpetan tokiko azken esportazioa eta pantaila-irudiak.
- `docs/memoria/`, `docs/requisitos/`, `docs/rubrica/`, `docs/demo/`: memoria, eranskinak, irizpideak eta defentsa-gidoiak.
- `SHA256SUMS.json`: paketeko fitxategi bakoitzaren hash-a.

## Abiaraztea
Deskonprimitu karpeta berri batean eta jarraitu erroko README.md. Ez ordezkatu martxan dagoen instalaziorik. APIak `outputs/api/manifest.json` erabiltzen du. Bere osasun-kontratuak `status: ready` ematen du; ez du `model_loaded` eremurik. Modeloaren scikit-learn bertsioa 1.5.0 da.

## Hamar minutuko defentsa
1. 0–2 min: arazoa, datuak, partizioak eta sistemaren mugak.
2. 2–4 min: Filebeat → Kafka → NiFi → API → Elasticsearch → Kibana ibilbidea.
3. 4–7 min: koadernoa, desoreka, matrizea, recall/precision eta atalaseak.
4. 7–9 min: benetako laborategian alerta bat erakutsi; ID bera APIan eta panelean egiaztatu.
5. 9–10 min: mantentze-erabakia, mugak eta galderak.

Erabili `docs/demo/` karpetako gidoi xehea. Lau kideek beren hitzekin azaldu eta beste bloke bati buruzko galdera bati erantzun behar diote.

## Oraindik pertsonen esku
- Erabiltzaileak baldintzak eta SMB/NiFi worker baliokidetasunak onartuta daudela baieztatu du; entrega GitHub bidez da. Data eta ordu zehatzak ez dira adierazi.
- Taldearen benetako entsegua eta defentsa egin; akta bete.
- Memoria eta eranskinak berrikusi; benetako ekarpenak berretsi.
- Paketea eskatutako plataformara igo eta egiaztagiria gorde.

Ez da sinadurarik, ahozko parte-hartzerik edo bidalketarik automatikoki egiaztatu.

## 10eko mailarako prestaketa

- [40 irizpideen gida](HAMARREKO_GIDA.md)
- [Defentsako galderak eta erantzunak](DEFENTSA_GALDERAK.md)
- [GitHub entrega-prozedura](GITHUB_ENTREGA.md)

Azken paketea: outputs/entrega_20261112_prestaketa.zip.
