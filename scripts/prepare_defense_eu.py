"""Errubrikaren 40 irizpideetarako prestaketa eta GitHub entrega osagarria."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    docs = ROOT / 'docs/entrega'
    source = json.loads((ROOT / 'docs/rubrica/fuente.json').read_text(encoding='utf-8'))
    groups = [
        ([5, 23, 24, 31, 32, 52, 55], 'Kontzeptuak eta arkitektura', 'docs/evidence/CG30.md', 'Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.'),
        ([10, 36, 38, 39, 45, 60, 61, 62], 'Datuak eta eredua', 'notebooks/02_training.ipynb', 'Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.'),
        ([16, 17, 19, 20], 'Segurtasuna eta ardurak', 'docs/evidence/CG24.md', 'Erakutsi dokumentatutako sarbide-mugak eta datuen helburua. Azaldu zergatik ez den laborategia industria-ziurtagiri bat.'),
        ([14, 46, 77, 80, 85, 90, 96], 'Karga eta fidagarritasuna', 'docs/evidence/CG32_CAMPAIGN_20261028.md', 'Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.'),
        ([41, 49, 66, 68, 92, 95, 101], 'Integrazioa eta kalitatea', 'docs/evidence/CG20_SAME_EVENT_20261022.md', 'Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.'),
        ([65, 71, 72, 87, 100, 104, 105], 'Panelak eta negozioa', 'docs/evidence/CG19_2026-10-21.md', 'Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.'),
    ]
    entries = {}
    for rows, label, evidence, action in groups:
        assert (ROOT / evidence).is_file()
        for row in rows:
            entries[row] = (label, evidence, action)
    assert set(entries) == {d['row'] for d in source['descriptors']}
    parts = ['# 10eko mailarako 40 irizpideen gida\n',
             '2026-11-12. Jatorria: [errubrikaren kopia](../rubrica/fuente.json), AURRERATUA (10). Gida hau prestaketa da, ez kalifikazioa. Ebidentzia estekatzeak ez du irizpidea automatikoki betetzen.\n',
             'Erabiltzaileak gaur baieztatu du GitHub dela entrega-kanala eta aurretik galdetutako baldintzak eta SMB/NiFi worker baliokidetasunak onartuta daudela. Baieztapen hori erabiltzaileari egozten zaio; ez da irakaslearen erantzun zuzen berri bat. Data eta ordu zehatzik ez da eman.\n',
             '## Lehentasunak\n\n1. Lau kideek matrizea eta beren bloketik kanpoko galdera bat azaldu.\n2. Zuzeneko demoan gertaera bera eta alerta erakutsi, akta benetako emaitzekin betez.\n3. GitHubeko dokumentazioaz gain, baztertutako modelo-paketea Release asset gisa erantsi.\n4. Ez aurkeztu E2E ≤1 s edo 10 gertaera/s eutsia lortutzat: artxibatutako kanpainak ez ditu lortu.\n\n']
    for d in source['descriptors']:
        label, evidence, action = entries[d['row']]
        parts.append(f"## {d['advanced_cell']} — {label}\n\n**10eko deskriptorea:** {d['advanced_descriptor']}\n\n**Ebidentziaren abiapuntua:** [{evidence}](../../{evidence}).\n\n**Defentsan egiteko:** {action}\n\n**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.\n\n")
    (docs / 'HAMARREKO_GIDA.md').write_text(''.join(parts), encoding='utf-8')
    (docs / 'DEFENTSA_GALDERAK.md').write_text('''# Defentsa prestatzeko galderak eta erantzunak

Erantzunak norberaren hitzekin azaldu. Kide bakoitzak bere blokearen bi galdera eta beste bloke bateko bat praktikatu behar ditu.

## 1. kidea: arazoa eta arkitektura (0–2 min)
**Zer egiten du sistemak?** Sentsoreen uneko irakurketa sailkatu, ezohikotasuna bereizita kalkulatu eta pertsonak berrikus dezan erakusten du. Ez du makina kontrolatzen edo matxurara arteko denbora kalkulatzen.

**Zergatik IA ahula?** Ataza zehatz baterako ikasitako funtzioa da; ez du helburu orokorrik, ulermen orokorrik edo erabakitzeko autonomia industrialik.

**Zer da ikasia eta zer araua?** RFk datuetatik ikasten du scorea; 0,15/0,70 kolore-atalaseak arauak dira. F2 atalaseak beste erabaki bat kontrolatzen du.

**Zergatik Python?** Datuen prestaketa, scikit-learn eta FastAPI ekosistema bateratzen ditu. Java aukera sendoa da azpiegiturarako; Pythonen abantaila proiektu honetako integrazio eta esperimentazio azkarra da. Async erabiltzeak ez du CPUko inferentzia automatikoki azkartzen.

## 2. kidea: eredua (2–4:30 min)
**Zergatik ez accuracy bakarrik?** Klase nagusia beti iragartzen duen ereduak accuracy handia izan dezake eta matxura guztiak galdu. Recall, precision, PR-AUC eta nahaste-matrizea behar ditugu.

**Zer esan nahi du emaitzak?** F2 atalasean TN=1150, FP=9, FN=9 eta TP=32: 41 matxuretatik 32 detektatzen dira, recall %78,05. 41 alerta positiboetatik 32 zuzenak dira, precision %78,05. Ez da test independentea.

**Nola saihesten da leakage?** Etiketak eta matxura-azpimotak ez dira sarrera. Transformazioak tolesaren fit zatian doitzen dira. SMOTENC alderaketak entrenamendu-tolesak soilik erabiltzen ditu; ez da azken RF ereduan automatikoki sartzen.

**Zertarako feature fisikoak?** Tenperatura-aldeak prozesuko beroaren testuingurua ematen du; rpm × torkeak potentziarekin lotutako proxy bat ematen du. Ez da watt-etan dagoen potentzia bihurketa-faktorerik gabe. Korrelazioa ez da kausalitatea.

**RF, Gradient Boosting, IF eta Autoencoder?** RFk zuhaitzen batezbestekoarekin sailkatzen du; boosting-ek aurreko erroreak sekuentzialki hobetzen ditu. IFk isolatzeko errazak diren laginak nabarmentzen ditu; autoencoder-ak berreraikuntza-errorea erabiltzen du. Azken biek ez dute matxura-etiketaren ordez froga ematen. Alderaketak `docs/evidence/CG34_EXPLORACION_20261023.md` fitxategian daude.

**Zergatik ez makina bakoitzeko denbora-historiko asmaturik?** Entrenamenduko argazki tabularrek ez dute benetako denbora-sekuentzia egiaztatzen. Groupby egiteak ez du berez denborazko kausalitatea sortzen.

## 3. kidea: integrazioa (4:30–7 min)
**Zergatik Kafka?** Ekoizlea eta kontsumitzaileak desakoplatzen ditu. Offset-ak eta kontsumitzaile-taldeek berriro irakurtzea ahalbidetzen dute; konfigurazioak eta atxikipenak jarraitutasuna mugatzen dute.

**Zer gertatzen da erantzuna galtzen bada?** ID bera eta sarrera bera errepikatzean ledger-ak erantzun kanonikoa berreskuratzen du. ID bera beste edukiarekin 409 gatazka da. 422 sarrera baliogabea da; 503 zerbitzua ez prest egotea.

**Zergatik behin kargatu modeloa?** Eskaera bakoitzean diskoa eta deserializazioa saihesteko. Abioan hashak, esparrua eta bertsioa egiaztatzen dira.

**Zenbat azkarra da?** 28/10eko beste bundle baten kanpainan HTTP p95 14,365–15,116 ms izan zen oinarrizko hiru korridetan; E2E p95 78,135–83,859 s. 10/s eskaintzean backlog-a metatu zen. Emaitza hori ezin zaio gaurko bundleari automatikoki egotzi.

**Zer frogatzen du zero galerak?** Saiatutako kanpainako IDak helmugan adiskidetu zirela. Ez du etorkizuneko galera-eza, argindar-mozketa edo exactly-once banatua bermatzen.

## 4. kidea: panela eta erabakia (7–10 min)
**Zein grafiko zertarako?** Lerroak bilakaera ikusteko; bero-mapa higadura eta matxura-maiztasunaren erlazioa ikusteko; azken gertaeren taula trazabilitaterako; KPIak laburpenerako. Denbora-tartea eta izendatzailea beti azaldu.

**Zer egiten dugu alerta batekin?** Datuaren data eta kalitatea egiaztatu, makina eta sentsoreak berrikusi, beste ebidentziekin kontrastatu eta ikuskapena proposatu. Ez dugu makina automatikoki gelditzen.

**Zer kostu erabiltzen dugu?** Ariketaren matrizean FN=5.000 €, FP=200 €, TP=300 €, TN=0 €. F2 matrizeak 56.400 € ematen ditu; beti negatiboaren erreferentziak 205.000 €. 148.600 €-ko aldea ariketaren kalkulua da, ez neurtutako industria-aurrezkia. FN bat TP bihurtzeak 4.700 € gutxitzen du; 23,5 FP gehigarriren kostuaren baliokidea.

**Nodo bakarrak zer muga du?** Hostaren hutsegiteak zerbitzu guztiak kaltetu ditzake. Erreplikazioak, quorum-ak eta hutsegite-domeinu bereiziek erabilgarritasuna hobetu dezakete; edukiontzi gehiago host berean edukitzea ez da HA.

**Zer esan pribatutasunaz?** Telemetria mantentze-helbururako erabiltzen da; ez da operadorearen errendimendua ondorioztatzeko gurutzatu behar. Konfigurazio eta sekretu pribatuak entregatik kanpo mantentzen dira. Arau-aplikagarritasunaren azterketa CG24n dago; ez dugu ziurtagiri legalik aldarrikatzen.

## 30 minutuko entsegua
1. 5 min: ireki koadernoa, panelak eta ebidentzien gida; egiaztatu osasuna.
2. 10 min: egin lau txandak kronometroarekin.
3. 10 min: kide bakoitzari beste bloke bateko galdera bat egin.
4. 5 min: bete akta, jaso zalantzak eta zuzendu azalpenak.

Zuzeneko demoak huts egiten badu, erakutsi datatutako ebidentzia historikoa babes gisa eta esan zuzenean ez dela oraingo exekuzioa. Ez aurkeztu pantaila-irudi bat zuzeneko froga gisa.
''', encoding='utf-8')
    (docs / 'GITHUB_ENTREGA.md').write_text('''# GitHub bidezko entrega

Erabiltzaileak 2026-11-12an baieztatua: GitHub da entrega-kanala; galdetutako baliokidetasunak eta baldintzak onartuta daude. Data/ordu zehatzik ez da adierazi.

## Irakasleak ireki beharreko fitxategiak
1. `docs/entrega/HAMARREKO_GIDA.md`: 40 irizpide, jatorrizko deskriptoreak eta ebidentziak.
2. `notebooks/02_training.ipynb`: emaitzak eta azalpenak.
3. `docs/memoria/ANEXO4_CNC_Guard.md` eta `docs/requisitos/ANEXO1_CNC_Guard.md`.
4. `docs/entrega/DEFENTSA_GALDERAK.md`: banaketa eta erantzunak.
5. Release-ari erantsitako ZIPa: modeloak, txostenak eta tokiko ebidentziak.

## Argitaratzeko kontrola
- Berrikusi aldaketak eta gehitu soilik entrega honetako fitxategiak; ez erabili `git add .` lan-kopia osoan.
- Egin commit eta push adostutako adarrera; adierazi entregaren commit zehatza.
- Sortu Release bat commit horri lotuta, eta erantsi `outputs/entrega_20261112_prestaketa.zip` eta haren `.sha256` fitxategia.
- `outputs/` eta modeloak Git-ek baztertzen ditu: push egiteak ez ditu bidaltzen. Release asset behar da modelo-paketea entregatzeko.
- Egiaztatu GitHubetik ZIPa deskargatu eta deskonprimitu daitekeela, eta hash-a bat datorrela.
- Gorde Release esteka, commit-a eta entrega-unea aktan.

Fitxategi hau prestaketa da; ez du commit, push edo Release argitalpenik egiaztatzen. ZIPa tokiko egoeraren kopia da eta aldaketa kommitatu gabeak izan ditzake; argitalpenean commitarekin bateragarritasuna berrikusi.
''', encoding='utf-8')
    # Ez aldatu aurreko ZIPa: bertsio bereizia eta egiaztagarria.
    old = ROOT / 'outputs/entrega_20261112.zip'
    new = ROOT / 'outputs/entrega_20261112_prestaketa.zip'
    additions = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in docs.glob('*.md')}
    additions['scripts/prepare_defense_eu.py'] = Path(__file__).read_bytes()
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(new, 'w', zipfile.ZIP_DEFLATED) as dst:
        hashes = {}
        for name in src.namelist():
            if name.endswith('/') or name == 'SHA256SUMS.json' or name in additions:
                continue
            raw = src.read(name)
            dst.writestr(name, raw)
            hashes[name] = hashlib.sha256(raw).hexdigest()
        for name, raw in additions.items():
            dst.writestr(name, raw)
            hashes[name] = hashlib.sha256(raw).hexdigest()
        dst.writestr('SHA256SUMS.json', json.dumps(hashes, indent=2))
    with zipfile.ZipFile(new) as check:
        assert check.testzip() is None
        for name, digest in hashes.items():
            assert hashlib.sha256(check.read(name)).hexdigest() == digest
    new.with_suffix('.zip.sha256').write_text(hashlib.sha256(new.read_bytes()).hexdigest() + '  ' + new.name + '\n')
    print(f'ONDO: {len(entries)} irizpide; {len(hashes)} fitxategiren hashak egiaztatuta; {new}')


if __name__ == '__main__':
    main()
