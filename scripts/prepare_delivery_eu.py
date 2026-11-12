"""Euskarazko entrega lokala prestatu, jatorrizko artefaktuak aldatu gabe."""
import contextlib
import hashlib
import io
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    import os
    os.chdir(ROOT)
    target = ROOT / 'outputs/entrega_20261112'
    if target.exists():
        raise FileExistsError(target)
    target.mkdir()
    report = json.loads(Path('outputs/cg08/report.json').read_text())
    manifest = json.loads(Path('outputs/api/manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert hashlib.sha256((Path('outputs/api') / name).read_bytes()).hexdigest() == expected
    assert report['model_sha256'] == manifest['files']['rf.pkl']
    assert hashlib.sha256(Path('data/ai4i2020_train.csv').read_bytes()).hexdigest() == manifest['training_source_sha256']
    cells = []
    def md(text):
        cells.append(dict(cell_type='markdown', metadata={}, source=text.splitlines(True)))
    def code(text):
        cells.append(dict(cell_type='code', metadata={}, source=text.splitlines(True), execution_count=None, outputs=[]))
    md('''# CNC Guard — entrenamendua eta emaitzen azalpena

Entregako koadernoa, 2026-11-12. Aurretik lokalki entrenatutako RF ereduaren txostena eta balidazio-puntuazioak erabiltzen ditu. Beheko gelaxkak berriz exekutatu dira; ez da entrenamendu historikoa gaur egindakotzat aurkezten.

## Helburua eta datuen muga
Egungo matxura-egoera sailkatzen dugu. Ez dugu ETA, RUL edo etorkizuneko matxura iragartzen. Irakaslearen 8.000 errenkadako CSV baimendua soilik erabiltzen da. 5.600 errenkada entrenatzeko, 1.200 garapen-balidaziorako eta aurretik ikuskatutako beste 1.200 baztertuta: azken multzoa ez da ebaluatzen.
''')
    code('''from pathlib import Path
import os, json, hashlib
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report, recall_score, precision_score
root = Path.cwd()
if not (root / 'outputs/cg08/report.json').exists():
    root = root.parent
os.chdir(root)
report = json.loads(Path('outputs/cg08/report.json').read_text())
manifest = json.loads(Path('outputs/api/manifest.json').read_text())
raw = Path('data/ai4i2020_train.csv').read_bytes()
assert hashlib.sha256(raw).hexdigest() == manifest['training_source_sha256']
df = pd.read_csv('data/ai4i2020_train.csv')
print('Errenkadak:', len(df))
print('Partizioak:', {k: len(v) for k, v in report['splits'].items()})
print('Entrenamenduaren bertsioak:', report['versions'])
''')
    md('''## Aurreprozesamendua eta desoreka
Bost sentsoreak eta `machine_type` erabiltzen dira. IDak eta denbora-markak ez dira ezaugarri prediktiboak; `failure_*` etiketak ere kanpoan geratzen dira. Zenbakizko hutsuneak medianarekin betetzen dira eta makina mota one-hot bidez kodetzen da. Transformazioak entrenamendu-tolesaren barruan doitzen dira.

Dummy eta erregresio logistikoa RF hautagaiekin konparatzen dira. RF hautagaiek ezaugarri fisikoak, klase-pisuak eta zuhaitzen sakonera alderatzen dituzte. Lau toleseko OOF average precision erabiltzen da RF aukeratzeko; F2 atalasea garapen-balidazioan doitzen da. Horregatik emaitzak optimistak izan daitezke: ez dira kanpoko azken test independente baten emaitzak.
''')
    code('''train = df.loc[report['splits']['train']]
print('Entrenamenduko klaseak:')
print(train.machine_failure.value_counts().sort_index().to_string())
print('Hutsuneak:')
print(train[manifest['input_features']].isna().sum().to_string())
print('Aukeratutako konfigurazioa:')
print(json.dumps(report['search'][report['winner']], indent=2))
''')
    md('''## Entrenamendua erreproduzitzea
`scripts/experiment_rf.py` fitxategiak pipeline osoa eta entrenamendu-algoritmoa ditu; `scripts/experiment_anomaly.py` fitxategiak Isolation Forest bereizia entrenatzen du. Berriro entrenatzeko, erabili blokeo-fitxategiko ingurunea eta irteera berriak:

```bash
uv sync --frozen --python 3.11
uv run --frozen python -m scripts.experiment_rf --output outputs/entrega_rf_berria
uv run --frozen python -m scripts.experiment_anomaly --output outputs/entrega_if_berria
uv run --frozen python -m scripts.package_model --rf-dir outputs/entrega_rf_berria --anomaly-dir outputs/entrega_if_berria --output outputs/entrega_api_berria
```

Entregatutako modeloa `outputs/api/rf.pkl` da; `models/cnc_failure_model.pkl` haren kopia berdina da. Zerbitzuak RF, IF eta manifestua batera behar ditu. Ez kargatu modeloa scikit-learn bertsio desberdin batekin.
''')
    code('''for name, expected in manifest['files'].items():
    assert hashlib.sha256((Path('outputs/api') / name).read_bytes()).hexdigest() == expected
assert report['model_sha256'] == manifest['files']['rf.pkl']
print('Modeloen SHA-256 hashak: zuzenak')
scores = pd.read_csv('outputs/cg08/validation.csv', float_precision='round_trip')
assert scores.source_row_index.tolist() == report['splits']['validation']
assert scores.label.tolist() == df.loc[scores.source_row_index, 'machine_failure'].tolist()
cutoff = manifest['risk_threshold']
pred = (scores.rf_score >= cutoff).astype(int)
print('F2 atalasea:', cutoff)
print('Nahaste-matrizea [[TN, FP], [FN, TP]]:')
print(confusion_matrix(scores.label, pred))
print('Sailkapen-txostena:')
print(classification_report(scores.label, pred, target_names=['Matxurarik ez', 'Matxura'], digits=4, zero_division=0))
print('Recall:', recall_score(scores.label, pred))
print('Precision:', precision_score(scores.label, pred))
''')
    md('''## Interpretazioa eta enpresaren erabakia
Recall-ek benetako matxuretatik zenbat detektatzen diren adierazten du; precision-ek alertetatik zenbat diren zuzenak. FN bat detektatu gabeko matxura da eta FP bat alferrikako ikuskapena eragin dezakeen alerta. Accuracy bakarrik erabiltzea desegokia da, matxurak gutxiengoa direlako.

F2-k recall gehiago lehenesten du. APIaren kolore-politikak 0,15 eta 0,70 mugak ditu; `risk_alert` erabakiak manifestuko F2 atalasea erabiltzen du. Ez dira erabaki bera. IFren bitxitasuna ez da matxura-probabilitatea eta ez du RF alerta ezeztatzen. Mantentze-erabakia pertsona batek berrikusten du. 1.200 €/orduko geldialdi-kostuak ez du berez frogatzen sistemak aurrezkia lortu duenik.

## Mugak
Balidazioa berrerabilia da, puntuazioak ez daude industria-arrisku gisa kalibratuta eta ez dago etorkizuneko matxuren ebaluaziorik. Modelo historikoa mantendu da; koaderno honetako berriz kalkulatutako txostenak ez du datu berrien gaineko ebaluazioa ordezkatzen.
''')
    namespace = {}
    count = 0
    for cell in cells:
        if cell['cell_type'] == 'code':
            count += 1
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(''.join(cell['source']), namespace)
            cell['execution_count'] = count
            cell['outputs'] = [dict(output_type='stream', name='stdout', text=output.getvalue().splitlines(True))]
    notebook = dict(cells=cells, metadata=dict(kernelspec=dict(display_name='Python 3', language='python', name='python3'), language_info=dict(name='python', version='3.12')), nbformat=4, nbformat_minor=4)
    Path('notebooks/03_delivery_metrics.ipynb').write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copy2('outputs/api/rf.pkl', 'models/cnc_failure_model.pkl')
    docs = Path('docs/entrega')
    docs.mkdir(exist_ok=True)
    (docs / 'README_EU.md').write_text('''# CNC Guard — entrega-gida

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
- Irakaslearekin formatua, kanala, ordua eta baliokidetasunak baieztatu.
- Taldearen benetako entsegua eta defentsa egin; akta bete.
- Memoria eta eranskinak berrikusi; benetako ekarpenak berretsi.
- Paketea eskatutako plataformara igo eta egiaztagiria gorde.

Ez da sinadurarik, ahozko parte-hartzerik edo bidalketarik automatikoki egiaztatu.
''', encoding='utf-8')
    (docs / 'AKTA_ETA_ENTREGA.md').write_text('''# Entseguaren eta entregaren akta

Egoera: BETETZEKO. Bete ekintza egin ondoren soilik.

| Eremua | Benetako datua |
|---|---|
| Saioaren data eta ordua | |
| Paketearen SHA-256 | |
| Ingurunea eta modeloaren hash-a | |
| Lehen kidea: azalpena eta galdera | |
| Bigarren kidea: azalpena eta galdera | |
| Hirugarren kidea: azalpena eta galdera | |
| Laugarren kidea: azalpena eta galdera | |
| Paneleraino jarraitutako event_id | |
| Erakutsitako alerta eta mantentze-erabakia | |
| Aurkitutako akatsak eta konponketak | |
| Beste kide baten berrikuspena eta data | |
| Irakasleak baieztatutako kanala eta formatua | |
| Entregaren data, esteka eta egiaztagiria | |
''', encoding='utf-8')
    with urllib.request.urlopen('http://127.0.0.1:18001/health', timeout=15) as response:
        health = json.load(response)
    (docs / 'EGIAZTAPENA.json').write_text(json.dumps(dict(checked_at=datetime.now(timezone.utc).isoformat(), health=health, model_hashes_verified=True, notebook_code_cells_executed=count, training_reexecuted=False, human_defense_verified=False, submitted=False), indent=2), encoding='utf-8')
    # Iturri esplizituak: sekretuak, bolumenak eta SMB datu gordinak kanpoan.
    folders = ['cnc_guard', 'scoring', 'planning', 'scripts', 'contracts', 'filebeat', 'elasticsearch', 'nifi-flows', 'kibana', 'notebooks', 'models', 'data', 'vendor', 'tests', 'docs/memoria', 'docs/requisitos', 'docs/rubrica', 'docs/demo', 'docs/entrega', 'outputs/api', 'outputs/cg08', 'outputs/cg09']
    for folder in folders:
        source = ROOT / folder
        if source.exists():
            shutil.copytree(source, target / folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.bak*'))
    for name in ['README.md', 'ENUNTZIATUA.md', 'pyproject.toml', 'uv.lock', 'docker-compose.yml']:
        shutil.copy2(name, target / name)
    # Dokumentazioaren esteka erlatiboak mantentzeko ebidentzia publikoak ere gorde.
    shutil.copytree('docs', target / 'docs', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree('deploy', target / 'deploy', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.bak*'))
    evidence = target / 'ebidentziak'
    evidence.mkdir()
    for name in ['kibana-chain-export.ndjson', 'live-e2e-verification.json', 'live-browser-validation.json', 'live-kibana.png', 'kibana-data-verified.png', 'live-laneki-Abisuak.png', 'live-laneki-Datuak.png']:
        source = Path('outputs') / name
        if source.exists():
            shutil.copy2(source, evidence / name)
    hashes = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
    (target / 'SHA256SUMS.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    archive = Path(shutil.make_archive(str(target), 'zip', target))
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        for name, digest in hashes.items():
            assert hashlib.sha256(zipped.read(name)).hexdigest() == digest
    archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    print(json.dumps(dict(archive=str(archive), files=len(hashes), bytes=archive.stat().st_size, health=health), indent=2))


if __name__ == '__main__':
    main()
