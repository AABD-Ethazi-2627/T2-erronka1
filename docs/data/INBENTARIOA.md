# CG02 — Datu-iturrien inbentarioa eta etiketaren bideragarritasuna

Azterketa-data: 2026-10-15. Iturria: [CG02](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/2).
Egoera: tokiko inbentarioa egiaztatuta; CG01eko talde-akordioa eta kanpoko iturriak egiaztatzeke.

## Eskuragarri dagoen iturria

`data/ai4i2020_train.csv`: 8.000 erregistro, 13 zutabe, 50 makina-identifikatzaile.
Jatorria eta lizentzia, `ENUNTZIATUA.md` dokumentuaren arabera: UCI AI4I 2020,
CC BY 4.0. Tokiko CSVaren eraldaketa-prozesua eta jatorrizko UCI fitxategiarekiko
parekotasuna ez dira egiaztatu; CNC identifikatzaileek ez dute benetako makinen
jarraipena frogatzen. Ez da kanpoko daturik deskargatu edo test multzorik erabili.

SHA-256: `1cce2859f4833b63dbf0992868884e5deac6f79e4d74a245abbc484d34e396ce`.
Neurketa zehatzak: [ai4i_inventory.json](ai4i_inventory.json).

- `machine_id`: identifikatzailea; ez sartu automatikoki ereduaren aldagai gisa.
- `machine_type`: H/M/L kategoria; H=789, M=2.381, L=4.830.
- `air_temp_K`: Kelvin, 295,3–304,5.
- `process_temp_K`: Kelvin, 305,7–313,8.
- `rpm`: bira/min, 1.168–2.886.
- `torque_Nm`: N·m, 3,8–76,6.
- `tool_wear_min`: minutu, 0–253.
- `machine_failure`: une bereko etiketa binarioa; 271 positibo eta 7.729 negatibo.
- `failure_TWF/HDF/PWF/OSF/RNF`: matxura-azpimoten adierazleak; helburuarekin
  lotutako emaitzak dira, ez inferentziarako sentsore-aldagaiak.

Ez dago hutsik dagoen gelaxkarik edo errenkada oso bikoizturik. Horrek ez du
frogatzen neurketa guztiak zuzenak edo independenteak direnik. 7 erregistrotan
`machine_failure=1` dago azpimotarik gabe; 14tan azpimota bat dago
`machine_failure=0` izanik. Jatorrizko balioak mantendu; ez berridatzi etiketa
azpimoten OR bidez. Desadostasun horien jatorria argitu behar da.

## Beste iturri batzuen egoera

`ENUNTZIATUA.md`-k NFS simuladoreko CSVak deskribatzen ditu, UTC denbora-markarekin.
Checkout honetan ez dago stream laginik, muntaketaren frogarik edo mantentze-historikorik.
Erabiltzaileak 2026-10-15ean emandako helbidea: `192.168.7.150\cnc-stream`;
zerbitzaria piztuta egotearen mende dago. Protokoloa eta esportazio-bidea
egiaztatzeke daude: SMB/UNC forma `\\192.168.7.150\cnc-stream` litzateke;
NFSrako `192.168.7.150:/esportazio-bidea` behar da, eta ezin da bidea izenetik ondorioztatu.
Saio honetako TCP konexio-probek 111, 2049 eta 445 portuetan timeout eman dute
(3 segundoko muga). Horrek ez du zerbitzaria itzalita dagoenik frogatzen:
sarea, VPN edo suebakia ere izan daitezke. Ez da baliabidea muntatu edo aldatu.
Adibideko timestamp-ak ez du entrenamendu-CSVari denbora-ordena ematen.
Ez dago benetako makina-logik, bibrazio-neurketarik edo etorkizuneko matxuren
jarraipen egiaztaturik. NiFi, Filebeat eta scoring fitxategiak osatu gabeko
txantiloiak dira; Compose-k ez du pipeline osoaren konfigurazioa ematen.

## Erabakia eta ondorengo lanaren mugak

Une bereko egoeraren sailkapena bakarrik ebaluatu daiteke datu hauekin.
Ez dago timestamp zutaberik, mantentze-gertaerarik edo 24 orduko jarraipenik:
ezin dira 5 minutuko benetako leihoak, 70/15/15 zatiketa kronologikoa,
aurreabisu-denbora edo makina/egun bakoitzeko alarma faltsuak balioztatu.
Ez asmatu datak edo bibrazioa falta horiek betetzeko.

CG07rako: sentsore-aldagaiak eta etiketa bereizi; `failure_*` baztertu,
aurreprozesatzea entrenamenduan soilik doitu, eta AI4Iko zatiketa ez-kronologikoa
argi etiketatu. Beti zero iragartzeak %96,6125 accuracy emango luke:
horregatik recall, precision, F1 eta nahasmen-matrizea behar dira.

24 orduko helburua ebaluatzeko, benetako denbora-markak, makina bakoitzeko
jarraipen osoa, matxuren hasiera eta mantentze-erregistro lotugarriak behar dira.
Ez konektatu CNC fisikoetara. CG02 ez da kanpoko datuen erabilgarritasunaren
edo CG01eko akordioen froga.

## Egiaztapena berriro egitea

Biltegiaren errotik, Python estandarra erabiliz:

```bash
python - <<'PY'
import collections, csv, hashlib, json
from pathlib import Path
p = Path('data/ai4i2020_train.csv')
e = json.loads(Path('docs/data/ai4i_inventory.json').read_text())
r = list(csv.DictReader(p.open()))
assert hashlib.sha256(p.read_bytes()).hexdigest() == e['sha256']
assert len(r) == e['rows']
assert list(r[0]) == e['columns']
assert dict(collections.Counter(x['machine_failure'] for x in r)) == e['target_counts']
assert len({x['machine_id'] for x in r}) == e['machines']
assert len(r) - len({tuple(x.values()) for x in r}) == e['duplicate_rows']
for c in e['columns']:
    assert sum(not x[c].strip() for x in r) == e['missing'][c]
for c, bounds in e['numeric_ranges'].items():
    v = [float(x[c]) for x in r]
    assert {'min': min(v), 'max': max(v)} == bounds
print('CG02: CSVaren hash, eskema, kopuruak eta barrutiak egiaztatuta')
PY
```

CG03rako kontratuak eta CG01eko ANEXO1 talde-berrikuspena egiteke daude.

## 2026-10-15eko eguneratzea — SMB egiaztatuta

Erabiltzaileak helbidea zuzendu du: lehen 192.168.75.150, ondoren
`\\192.168.75.222\cnc-stream` egungo SMB baliabidea. Azken helbide horretan
zerrenda eta hiru CSV lote irakurri dira (30 erregistro guztira), idazketarik gabe.
Aurreko 192.168.7.150 helbidearen timeout-a aurreko behaketa da, ez uneko egoera.

Laginek timestamp UTC eta entrenamenduko 13 zutabeen headerra dute. Hashak,
fitxategiak eta jatorria `contracts/source.smb.json`-en daude; kopiak
`data/stream_samples/`-en. Ez dago mantentze edo log iturri errealik egiaztatuta.
Ez dira laginak entrenamenduan edo test independente berritzat erabili.
Denbora-markak simulazioarenak dira: 24 orduko aurreikuspena oraindik ez da balioztatu.
Credentzialak `.env` pribatuan daude, Git-etik kanpo; kontratuen dokumentazioak
konexioaren metadatuak soilik jasotzen ditu.
