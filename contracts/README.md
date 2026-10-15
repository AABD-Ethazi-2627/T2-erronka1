# CG03 — Datu-kontratuen proposamena 0.1.0

Egoera: berrikusteko proposamena; ez da HTTP API edo NiFi flow bat hedatu.
Oinarriak: `ENUNTZIATUA.md`, tokiko AI4I entrenamendu-CSVa, SMBtik irakurritako
hiru lote txiki eta `scoring/inference.py` inferentzia partekatua.

## Iturriak eta egiaztatutako sarbidea

2026-10-15ean `\\192.168.75.222\cnc-stream` SMB baliabidearen zerrenda eta CSV
laginak irakurri dira. IPa aldakorra izan daiteke; `.env`-ko `SMB_HOST` da tresnaren
uneko konfigurazioa. Ez da NFS esportaziorik edo sistema-muntaketarik suposatzen.
Konexioaren metadatu publikoak eta laginen SHA-256: [source.smb.json](source.smb.json).
Ez dago erabiltzaile edo pasahitzik metadatu horietan.

`data/stream_samples/` karpetako hiru loteek 10na errenkada dituzte. CSVak headerra
du eta ondoko 14 zutabeak, ordena honetan:

```text
timestamp,machine_id,machine_type,air_temp_K,process_temp_K,rpm,torque_Nm,tool_wear_min,machine_failure,failure_TWF,failure_HDF,failure_PWF,failure_OSF,failure_RNF
```

Laginak formatu/inferentzia probetarako gordetzen dira. Ez dira entrenamenduan,
parametro-hautaketan edo test independente berri gisa erabili. Simuladorearen
jatorri zehatza eta entrenamendu-datuekiko independentzia ez daude frogatuta.
Timestamp berriak izateak ez du benetako makina baten luzetarako historikoa edo
24 orduko etiketaren jarraipena frogatzen.

`data/ai4i2020_train.csv` offline iturria da: 13 zutabe, timestampik gabe.
Ez gehitu fitxategiaren mtime-a, deskarga-ordua edo asmatutako orduak event-time gisa.
Ez bihurtu automatikoki telemetria-kontratu honetako gertaera.

## Eskemak eta esanahiak

JSON Schema Draft 2020-12; `common.schema.json` definizio partekatuak.
`$id` URNak dokumentu-identifikatzaile lokalak dira; ez dute sare-deskargarik behar.
`tests/test_contracts.py`-k eskema guztiak erregistro lokalean kargatzen ditu.

- `telemetry.schema.json`: normalizatutako sentsore-gertaera. `machine_type`
  H/M/L eta bost sentsore-aldagaiak ditu; ez du `machine_failure`, `failure_*`
  edo bibrazio asmaturik onartzen goiko mailan.
- `maintenance.schema.json`: mantentze-gertaeraren gutxieneko proposamena:
  inspection/repair/tool_change/unknown eta `failure_observed` boolean/null.
  Ezezaguna null da; ez bihurtu automatikoki negatibo.
- `log.schema.json`: makina, UTC ordua eta kode erauzia, jatorrizko `raw_text`
  testuarekin. Logaren benetako sintaxia ezezaguna da: ez dago fabrikatzaile-parserrik
  ezarrita. Ez erauzi beharrezkoak ez diren operadore-identifikatzaileak.
- `prediction.schema.json`: jatorrizko telemetriaren `event_id`, `machine_id` eta
  `timestamp` mantentzen ditu. `scored_at` inferentziaren ordua da, ez sentsorearena.
  Modeloko puntuazioak, bi abisu independenteak, politika, atalaseak, modeloaren
  bertsioa eta bundle-aren SHA-256 jasotzen ditu.

Lau kontratuek `event_id`, `machine_id`, UTC `timestamp`, `schema_version`,
`quality_flag` eta `source` eskatzen dituzte. Iturriaren `kind`, `uri` eta
`record_ref` jatorriaren trazabilitaterako dira. Erabiltzaile/pasahitzak ez dira payloadaren parte.

## Unitateak eta kalitatea

`air_temp_K` eta `process_temp_K`: Kelvin (>0); `rpm`: bira/min (>=0);
`torque_Nm`: N·m (>=0); `tool_wear_min`: minutu (>=0). Balioak JSON zenbaki finituak
izan behar dira; NaN/Infinity ez dira JSON balioduna. CSVko testuak zenbaki bihurtu
behar dira normalizatzean, unitateak aldatu gabe.

Entrenamenduko min/max barrutiak ez dira automatikoki sentsorearen muga fisiko:
eskemak ez du irakurketa bat baztertzen entrenamenduko maximoa gainditzeagatik soilik.
Oraingoz `machine_id`-ren formatua `CNC-` + hiru digitu da, ez inbentarioaren egiaztapena.

0.1.0 kontratu hauek `quality_flag=OK` gertaera normalizatuak soilik onartzen dituzte.
Falta diren balioak, zenbaki akastunak, unitate ezezagunak edo denbora-marka okerrak
baztertu behar dira inferentziara iritsi aurretik, jatorrizko lerroa eta arrazoia
berrikusketarako mantenduz. Ez markatu OK erregistro bat ereduaren imputazioak
bakarrik onartzen duelako. Errefusen biltegia eta haren envelope-kontratua hurrengo
integrazio-lana dira; oraindik ez dago dead-letter pipeline funtzionalik.

UTC formatua `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` da; baliozko egutegi-data behar da.
Eskema erabiltzen duen balioztatzaileak `date-time` formatua egiaztatu behar du;
testek Python datetime erabiliz egiten dute, regex hutsa ez baita nahikoa.

## Identitatea, errepikapenak eta etiketen banaketa

SMB bide edo IP aldaketak ez luke gertaera bera beste bat bihurtu behar. Proposamena:

```text
event_id = sha256(UTF8("cnc.telemetry.v0.1.0\n" + source_namespace + "\n" + raw_record))
source_namespace = "cnc-simulator-v1"
```

`raw_record` jatorrizko CSV datu-lerroa da, bukaerako CR/LF kenduta baina beste
karaktereak aldatu gabe. Ez da headerra. Horrela fitxategia berrirakurtzeak edo
birizendatzeak identitate bera ematen du. Headerra aparte iragazi behar da.
Lerro guztiz berdineko bi benetako gertaera bereizteko ez da nahikoa: simuladorearen
jatorrizko event ID edo sekuentzia global fidagarria beharko litzateke.
Ez da exactly-once portaera frogatu edo inplementatu.

Raw CSVko azken sei etiketak jatorrizko laginean/`source.raw_record`-en gordetzen dira,
baina ez inferentziaren aldagai gisa. Modeloak sentsoreak eta `machine_type` soilik
hartzen ditu. Etiketak ebaluazio/testuingururako aparte prozesatu behar dira.

Iragarpena deduplikatzeko giltza proposatua `(event_id, model_artifact_sha256, policy)`
da: gertaera bera modelo edo politika desberdinekin puntuatu ahal izateko.

## RF / Isolation Forest eta aurreko txantiloia

`failure_score` [0,1] arrisku-puntuazio kalibratu gabea da. Ez deitu automatikoki
`failure_probability`-ri eta ez aldatu `.5/.8` alert-maila zaharrak isilean.
`risk_alert` hautatutako politikaren atalasearekin kalkulatzen da; `anomaly_alert`
IFren atalase bereiziarekin. IFren puntuazioa ez da hutsegite-probabilitatea.
Ez dago AND baldintzarik edo makina gelditzeko komando edo eremurik.

Eskema honek eremuen motak/formatuak balioztatzen ditu. Abisuen eta atalaseen
arteko erlazioa, event_id-ren hash-a eta iturriko timestamp bera mantentzea
integrazioaren arauak dira; JSON Schema estandarrak ez ditu berez berriz kalkulatzen.
`predict_signals`-en probek bi abisuen independentzia egiaztatzen dute.

## Adibideak eta probak

`examples/valid/telemetry.json`: SMBtik gordetako lehen benetako laginetik normalizatua.
`prediction.json`: lagin horri gordetako RF/IF bundle-a aplikatuta sortua.
Maintenance eta log adibideak **fixture sintetikoak** dira; ez dira jasotako iturri errealak.
`examples/invalid/manifest.json`-ek 12 adibide oker eta baztertzeko arrazoiak zerrendatzen ditu.

```bash
python -m unittest discover -s tests -p 'test_contracts.py' -v
```

CI manualaren `requirements-ci.txt`-k jsonschema gehitzen du. Probak offline dira:
eskemak, adibide zuzen/okerrak, ezinezko datak, etiketa-ihesa eta gordetako 30 SMB
errenkaden normalizazioa egiaztatzen dituzte. Ez dute `.env` edo sareko sarbiderik behar.

## SMB automatizazio lokala

`.env.example`-tik norberaren `.env` prestatu, lehendik dagoena gainidatzi gabe,
eta `chmod 600 .env` aplikatu. `.env` eta haren aldaerak Git-ek ignoratzen ditu;
`.env.example`-k ez du credentzialik. IPa aldatzen denean `SMB_HOST` bakarrik eguneratu.
Ez inprimatu `.env`-ren edukia edo kargatu shell kode gisa.

```bash
python -m scripts.check_smb_source
python -m scripts.check_smb_source --download-dir data/stream_samples
```

Lehenak zerrenda kontsultatzen du. Bigarrenak lehen eta azken lote behatuaren
kopia lokalak jasotzen ditu; ez du desberdina den laginik gainidazten.
`smbclient` behar da, baina ez root, muntaketa edo zerbitzariaren aldaketarik.
Credentzialak 600 baimeneko aldi baterako fitxategi batez pasatzen dira, ez argv bidez;
eragiketaren amaieran fitxategia kentzen da. Tresnak `ls`/`get` komandoak bakarrik
onartzen ditu. Ez dago sinkronizazio, ezabaketa, scheduler edo CI sare-probarik aktibatuta.
