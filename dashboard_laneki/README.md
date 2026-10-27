# Laneki · CNC egoeraren prototipoa

Interfaze hau **prototipoa** da. Lehenetsitako `demo` moduak datu sintetiko
deterministak erabiltzen ditu. Goiburuak orri guztietan erakusten du.
API lokala ere demo-datuen zerbitzaria da: harekin konektatzeak ez du CNC Guard,
NiFi, Kafka, Elasticsearch, benetako sentsoreak edo modelo bat egiaztatzen.

## Instalazio erreproduzigarria (Windows, Python 3.12)

Repoaren karpeta honetatik, instalatu Python 3.12 eta `uv` aurretik:

```powershell
$env:UV_CACHE_DIR = 'D:/uv-cache'
uv venv D:/cnc-dashboard --python 3.12
uv pip install --python D:/cnc-dashboard/Scripts/python.exe --require-hashes -r requirements.txt
$env:LANEKI_PYTHON = 'D:/cnc-dashboard/Scripts/python.exe'
./iniciar.ps1
```

`requirements.txt`-ek ebatzitako dependentzia guztiak bertsio eta hash bidez
finkatzen ditu. Ez instalatu soilik `requirements.in`: locka berritzeko iturria da.
Konfigurazio honetako probak Python 3.12.10 eta Streamlit 1.66.1ekin egin dira.

Lehenetsitako helbideak: Streamlit `127.0.0.1:8501`, demo API
`127.0.0.1:8001`. APIaren 8001 portuak proiektuaren `/predict` APIko 8000
portuarekiko talka saihesten du. Abiarazleak prozesuen PIDak eta logak
`runtime/` karpetan gordetzen ditu; ez ditu beste zerbitzuak gelditzen.

## Datuen modua

- `LANEKI_MODE=demo`: ez du APIari deitzen. Pantaila guztiek demo-iturri bera
  erabiltzen dute, neurketak edo egoerak galeriatik aldatu gabe.
- `LANEKI_MODE=api`: `LANEKI_API_URL` (lehenetsia
  `http://127.0.0.1:8001/api`) kontsultatzen du. Iturriaren kontratua prototipo
  honena da, **ez** CNC Guarden `/predict` kontratua. APIa eroriz gero edo
  snapshota baliogabea bada, errorea eta daturik gabeko egoera erakusten dira;
  ez dira demo-datuak ordezkatzen. 1–50 makina onartzen dira, ID bakarrekin,
  neurketa finitu ez-negatiboekin eta `Normala/Berrikusteko/Akatsa` egoerekin.

Alboko `Eguneratu` botoiak cachea garbitu eta iturria berriz kontsultatzen du.
5 segundoko cacheak ez du freskatze automatikoa eragiten. Pantailako ordua
interfazearen ordua da, ez sentsorearen timestamp-a; ez da datuen freskotasuna
egiaztatzen. Iturriak historikorik ez badu, ez da serierik asmatzen.

Ez dago osasun-indize edo mantentze-historial egiaztaturik. Galeriak datu
horiek falta direla adierazten du. Demo egutegia adibidea da. Abisuen kostuak
1.200 €/h eta 1/8/24 orduko geldialdi osoa suposatzen duten **eszenatokiak**
dira; ez dira galera edo aurrezki neurtuak, ezta 24 orduko iragarpena ere.

## Egiaztapena

```powershell
& $env:LANEKI_PYTHON -W error -m unittest discover -s . -p test_domain.py -v
& $env:LANEKI_PYTHON -m unittest discover -s . -p test_app.py -v
uv pip check --python $env:LANEKI_PYTHON
```

Domeinuko probek snapshotaren baliozkotzea, galeriako neurketen koherentzia,
API errorea/datu partzialak eta URL/maparen hautapena estaltzen dituzte.
Streamlit AppTest-ek orriak, hautapena eta daturik gabeko egoera egiaztatzen ditu.
Ez dute pixel-mailako renderra, teklatu/kontraste osoa, mugikorreko itxura edo
CNC Guard integrazio erreala egiaztatzen.

## CG19 eta gainerako mugak

Interfaze honek ez ditu Kibana/CG19 entregagarriak ordezkatzen. Benetako
integrazioak irakurketa- eta inferentzia-kontratu bat behar du (`event_id`,
`machine_id`, timestamp, unitateak, kalitatea eta modeloaren bertsioa),
Elasticsearch-en gordetako gertaeren kontsulta eta jatorriaren frogak.
K eta °C bereizi behar dira; prototipoaren tenperaturak °C demo-balioak dira.
Ez dago 24h iragarpenik; proiektuaren `AI4I_CURRENT_STATE_ONLY` muga mantentzen da.
Azken 50 gertaeren taula, denbora-leihoak, FP/FN/etiketa behatuak, Kibana
artefaktuak eta onarpen humana ez dira prototipo honekin amaitutzat ematen.
