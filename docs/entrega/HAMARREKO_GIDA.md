# 10eko mailarako 40 irizpideen gida
2026-11-12. Jatorria: [errubrikaren kopia](../rubrica/fuente.json), AURRERATUA (10). Gida hau prestaketa da, ez kalifikazioa. Ebidentzia estekatzeak ez du irizpidea automatikoki betetzen.
Erabiltzaileak gaur baieztatu du GitHub dela entrega-kanala eta aurretik galdetutako baldintzak eta SMB/NiFi worker baliokidetasunak onartuta daudela. Baieztapen hori erabiltzaileari egozten zaio; ez da irakaslearen erantzun zuzen berri bat. Data eta ordu zehatzik ez da eman.
## Lehentasunak

1. Lau kideek matrizea eta beren bloketik kanpoko galdera bat azaldu.
2. Zuzeneko demoan gertaera bera eta alerta erakutsi, akta benetako emaitzekin betez.
3. GitHubeko dokumentazioaz gain, baztertutako modelo-paketea Release asset gisa erantsi.
4. Ez aurkeztu E2E ≤1 s edo 10 gertaera/s eutsia lortutzat: artxibatutako kanpainak ez ditu lortu.

## G5 — Kontzeptuak eta arkitektura

**10eko deskriptorea:** Bikain identifikatu eta justifikatu ditu printzipio guztiak: denbora errealeko inferentziaren eta offline ikaskuntzaren bereizketa, itxitako kontrol-begizta eta erabakiak hartzeko autonomia-mailak xehetasunez aztertuz.

**Ebidentziaren abiapuntua:** [docs/evidence/CG30.md](../../docs/evidence/CG30.md).

**Defentsan egiteko:** Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G10 — Datuak eta eredua

**10eko deskriptorea:** Bikain eta sakon sailkatu ditu ereduak: algoritmo gainbegiratuak (Random Forest, Gradient Boosting) eta anomalia-detekzioko eredu ez-gainbegiratuak (Isolation Forest, Autoencoder) alderatu ditu, bakoitzaren abantailak eta erabilera-kasuak CNC telemetrian zehaztuz.

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G14 — Karga eta fidagarritasuna

**10eko deskriptorea:** Bikain baloratu du sistemaren egokitasuna: hutsegite baten kostu ekonomikoa (1.200 €/h) eta mantentze-kostuak kuantifikatu ditu, probabilitate-atalaseak arriskuaren arabera doitu ditu eta denbora errealeko scoring-erako bideragarritasuna guztiz frogatu du.

**Ebidentziaren abiapuntua:** [docs/evidence/CG32_CAMPAIGN_20261028.md](../../docs/evidence/CG32_CAMPAIGN_20261028.md).

**Defentsan egiteko:** Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G16 — Segurtasuna eta ardurak

**10eko deskriptorea:** Bikain eta sakon argudiatu du: EBko AI Act-en sailkapena, CE markaketa eta erantzukizun zibilaren esleipena (fabrikatzailea vs erabiltzailea) xehetasunez jorratu ditu, eta mantentze prediktiboan langileen gaineko kontrol ezkutua ekiditeko irizpide etiko sendoak finkatu ditu.

**Ebidentziaren abiapuntua:** [docs/evidence/CG24.md](../../docs/evidence/CG24.md).

**Defentsan egiteko:** Erakutsi dokumentatutako sarbide-mugak eta datuen helburua. Azaldu zergatik ez den laborategia industria-ziurtagiri bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G17 — Segurtasuna eta ardurak

**10eko deskriptorea:** Bikain ezagutu eta garatu du: Privacy by Design printzipioak txertatu ditu arkitekturan, industria-sekretuen babesa zorrotz definitu du, eta telemetria-datuak operadoreen lan-errendimenduarekin modu irregularrean ez gurutzatzeko berme legal eta teknikoak ezarri ditu.

**Ebidentziaren abiapuntua:** [docs/evidence/CG24.md](../../docs/evidence/CG24.md).

**Defentsan egiteko:** Erakutsi dokumentatutako sarbide-mugak eta datuen helburua. Azaldu zergatik ez den laborategia industria-ziurtagiri bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G19 — Segurtasuna eta ardurak

**10eko deskriptorea:** Diseinuaren atal osoan kontuan hartu eta horrela jaso da da.

**Ebidentziaren abiapuntua:** [docs/evidence/CG24.md](../../docs/evidence/CG24.md).

**Defentsan egiteko:** Erakutsi dokumentatutako sarbide-mugak eta datuen helburua. Azaldu zergatik ez den laborategia industria-ziurtagiri bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G20 — Segurtasuna eta ardurak

**10eko deskriptorea:** Diseinuaren atal osoan kontuan hartu eta horrela jaso da da.

**Ebidentziaren abiapuntua:** [docs/evidence/CG24.md](../../docs/evidence/CG24.md).

**Defentsan egiteko:** Erakutsi dokumentatutako sarbide-mugak eta datuen helburua. Azaldu zergatik ez den laborategia industria-ziurtagiri bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G23 — Kontzeptuak eta arkitektura

**10eko deskriptorea:** Berezitasun kontzeptual eta teknikoak sakonki aztertzen ditu; CNC Guard AA ahularen (ataza espezifikorako eredu optimizatua) paradigma gisa bikain justifikatzen du, AA orokorraren egungo mugekin eta industria-errealitatearekin alderatuz.

**Ebidentziaren abiapuntua:** [docs/evidence/CG30.md](../../docs/evidence/CG30.md).

**Defentsan egiteko:** Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G24 — Kontzeptuak eta arkitektura

**10eko deskriptorea:** AI sinboliko/klasikoaren (arau estatikoak, atalase finkoak) eta Machine Learning-aren (patroi konplexuen ikaskuntza estatistikoa) arteko mugak, abantailak eta mugak sakonki arrazoitzen ditu CNC industriako mantentze-lanen ikuspegitik.

**Ebidentziaren abiapuntua:** [docs/evidence/CG30.md](../../docs/evidence/CG30.md).

**Defentsan egiteko:** Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G31 — Kontzeptuak eta arkitektura

**10eko deskriptorea:** Ikaskuntza mota bakoitzaren ezaugarriak, datu-beharrak eta industria-erabilerak sakonki zehazten ditu, CNC Guard-en zergatik aukeratu den ikaskuntza gainbegiratua (etiketatutako akats historikoak) beste moten aurrean bikain justifikatuz.

**Ebidentziaren abiapuntua:** [docs/evidence/CG30.md](../../docs/evidence/CG30.md).

**Defentsan egiteko:** Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G32 — Kontzeptuak eta arkitektura

**10eko deskriptorea:** Tresnen ekosistema osoa (datuen analisia, desoreka zuzentzea, modelizazioa, serializazioa eta inferentzia-zerbitzua) eta algoritmoak sakonki xehatzen ditu, teknologiak hautatzeko irizpideak bikain arrazoituz.

**Ebidentziaren abiapuntua:** [docs/evidence/CG30.md](../../docs/evidence/CG30.md).

**Defentsan egiteko:** Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G36 — Datuak eta eredua

**10eko deskriptorea:** Datuen tratamendu eta azterketa sakona egin du (EDA), ezaugarriak ezin hobeto prestatuz.

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G38 — Datuak eta eredua

**10eko deskriptorea:** Datuen azterketa sakona egin du, feature engineering aurreratua garatu du (`temp_diff`, `power_est`), ezaugarrien garrantziaren interpretazio fisiko/industriala egin du eta datuen filtrazioa (data leakage) erabat saihestu du SMOTE entrenamenduan soilik aplikatuz.

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G39 — Datuak eta eredua

**10eko deskriptorea:** Ebaluazio ezin hobea: Recall, Precision eta Confusion Matrix sakonki interpretatu ditu.

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G41 — Integrazioa eta kalitatea

**10eko deskriptorea:** Inplementazio profesional eta sendoa garatu du: APIak eredua memorian behin kargatzen du abioan, sarrerak zorrotz baliozkotzen ditu, erroreak kudeatzen ditu, alerta-mailak kalkulatzen ditu (`OK`, `AVISO`, `CRITICA`) eta NiFi fluxuarekin denbora errealean integratuta dago.

**Ebidentziaren abiapuntua:** [docs/evidence/CG20_SAME_EVENT_20261022.md](../../docs/evidence/CG20_SAME_EVENT_20261022.md).

**Defentsan egiteko:** Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G45 — Datuak eta eredua

**10eko deskriptorea:** Algoritmoen egokitasunaren balorazio bikaina: klase-desoreka larriaren aurrean Recall-a (%76+) lehenestea justifikatzen du, False Negative (1.200 €/h geldialdia) eta False Positive (alferrikako ikuskapena) kostu ekonomikoak alderatuz, eta ereduaren egokitasun industriala guztiz bermatuz.

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G46 — Karga eta fidagarritasuna

**10eko deskriptorea:** Sistema adimendunaren aplikazio praktikoa bikain ebaluatu du: osagaien desakoplamendua (Kafka buffer), datu-galerarik gabeko transferentzia (NiFi), scoring-aren latentzia baxua, eta muturretik muturrerako fidagarritasuna (sentsoretik mantentze-alertara) sakonki baliozkotuz.

**Ebidentziaren abiapuntua:** [docs/evidence/CG32_CAMPAIGN_20261028.md](../../docs/evidence/CG32_CAMPAIGN_20261028.md).

**Defentsan egiteko:** Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G49 — Integrazioa eta kalitatea

**10eko deskriptorea:** Ekoizpen-mailako ikaskuntza konputazional automatikoa garatu du: streaming etengabeko datu-bolumen handiak prozesatzen ditu (NFS -> Filebeat -> Kafka), NiFik atributuak automatikoki ateratzen ditu, ereduak denbora errealean balioesten du eta informazio egituratua (KPIak, agregazioak, alertak) indexatzen da Elasticsearchen giza esku-hartzerik gabe.

**Ebidentziaren abiapuntua:** [docs/evidence/CG20_SAME_EVENT_20261022.md](../../docs/evidence/CG20_SAME_EVENT_20261022.md).

**Defentsan egiteko:** Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G52 — Kontzeptuak eta arkitektura

**10eko deskriptorea:** Bikaintasunez eta sakonki justifikatzen du Python-en egokitasuna: datuen aurreprozesamendurako eta modelizaziorako liburutegiak, FastAPI-k eskaintzen duen asinkronia eta REST integrazio azkarra, eta industria-ingurunean pipeline osoarekin (NiFi, Docker) konektatzeko malgutasuna aztertzen ditu, beste aukera batzuekin konparazio arrazoitua eginez.

**Ebidentziaren abiapuntua:** [docs/evidence/CG30.md](../../docs/evidence/CG30.md).

**Defentsan egiteko:** Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G55 — Kontzeptuak eta arkitektura

**10eko deskriptorea:** Bikaintasunez egituratutako programa: arkitektura garbia eta modularra, entrenamendua eta ekoizpen-APIa erabat bereizita, Pydantic mota-egiaztapen sendoak, errore- eta salbuespen-kudeaketa aurreratua, eta kode-estilo garbia (PEP8 eta praktika onak errespetatuz).

**Ebidentziaren abiapuntua:** [docs/evidence/CG30.md](../../docs/evidence/CG30.md).

**Defentsan egiteko:** Azaldu sarrera, irteera, ikasitako eredua, arau finkoa eta pertsonaren erabakia. Eman CNCko adibide bat.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G60 — Datuak eta eredua

**10eko deskriptorea:** Bikaintasunez eta sakontasunez definitutako eredua: adibidez, ereduaren egokitasuna hiperplano ez-linealetan, datu-desorekaren efektu larriak (laginen %3,4 bakarrik hutsegiteak), SMOTE eta klase-pisuen eragina, eta negozioaren errealitatearekin bat datozen erabakiak (threshold tuning) eta metrikak (Recall eta ROC-AUC vs Accuracy tranpa) modu zehatzean definitu ditu.

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G61 — Datuak eta eredua

**10eko deskriptorea:** Bikaintasunez inplementatutako soluzioa: eredua hiperparametro egokiekin entrenatua, serializazio garbia, FastAPI zerbitzu sendoa `/health` eta `/predict` bideekin, alerta-atalase zehatzak (>=0.15 AVISO, >=0.7 CRITICA), eta denbora errealeko probekin egiaztatutako errendimendu sendoa. Threshold tuning egokiarekin findu du eredu matematikoa "geldialdi programatuaren paradoxa" justifikatuz.

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G62 — Datuak eta eredua

**10eko deskriptorea:** Ereduaren hasierako emaitzak (Nahasmen-matrizea) ikusi ondoren, emaitzak hobetzeko aplikatu dezaketen "teknika desberdin" onenetarikoa aldagai berriak sortzea da (Feature Engineering). Makina bakoitzaren historikoa groupby bidez kalkulatzea emaitzak hobetzeko eta ebaluazio borobil bat egiteko ezinbesteko tresna da. Datu ezazagunen aurreko portaera aztertzeko balidazio-gurutzatua egin du. Justifikatu ditu ebaluazioak. Fine tuning bidez eta teknika desberdinak baliatuz ereduaren hiperparametroak doitu ditu. Nahasmen-matrizeak eta eta sailkapen-txostenen emaitzak aztertu eta interpretatu ditu erabakiak justifikatzeko (threshold tuning).

**Ebidentziaren abiapuntua:** [notebooks/02_training.ipynb](../../notebooks/02_training.ipynb).

**Defentsan egiteko:** Erakutsi partizioak, ezaugarriak, hautaketa eta matrizea. Azaldu zergatik den balidazio berrerabilia eta ez azken test independentea.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G65 — Panelak eta negozioa

**10eko deskriptorea:** Datuak automatikoki prozesatu eta informazio operatibo zein prediktibo bihurtzen ditu, sentsoreen datuak eta inferentziaren emaitzak uztartuz. Makinen arrisku-egoerak, joerak eta alertak identifikatzeko informazio erabilgarria eskaintzen du, mantentze-erabakiak errazteko.

**Ebidentziaren abiapuntua:** [docs/evidence/CG19_2026-10-21.md](../../docs/evidence/CG19_2026-10-21.md).

**Defentsan egiteko:** Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G66 — Integrazioa eta kalitatea

**10eko deskriptorea:** Datuen egitura osoan koherentzia bermatzen du, eta telemetria eta inferentziaren emaitzak integratzeko formatu egokia definitu eta egiaztatzen du.

**Ebidentziaren abiapuntua:** [docs/evidence/CG20_SAME_EVENT_20261022.md](../../docs/evidence/CG20_SAME_EVENT_20261022.md).

**Defentsan egiteko:** Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G68 — Integrazioa eta kalitatea

**10eko deskriptorea:** Indizeak eta ingest-pipelineak ezin hobeto sortu ditu datuak zuzen gordetzeko.

**Ebidentziaren abiapuntua:** [docs/evidence/CG20_SAME_EVENT_20261022.md](../../docs/evidence/CG20_SAME_EVENT_20261022.md).

**Defentsan egiteko:** Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G71 — Panelak eta negozioa

**10eko deskriptorea:** Kibanako bistaratze-teknikak modu arrazoituan alderatu eta hautatu ditu, denbora-serieak, makinen arteko konparazioak eta alerta-adierazleak irudikatzeko. Grafikoen konfigurazioa (denbora-tarteak, agregazioak eta iragazkiak) egokia dela egiaztatu eta justifikatu du.

**Ebidentziaren abiapuntua:** [docs/evidence/CG19_2026-10-21.md](../../docs/evidence/CG19_2026-10-21.md).

**Defentsan egiteko:** Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G72 — Panelak eta negozioa

**10eko deskriptorea:** Sentsoreen datuak eta negozio-helburua modu arrazoituan erlazionatzen ditu, eta monitorizazioaren emaitzetatik mantentze-erabaki erabilgarriak proposatzen ditu.

**Ebidentziaren abiapuntua:** [docs/evidence/CG19_2026-10-21.md](../../docs/evidence/CG19_2026-10-21.md).

**Defentsan egiteko:** Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G77 — Karga eta fidagarritasuna

**10eko deskriptorea:** Datuen erauzketa eta biltegiratze-prozesu sendoa garatzen du, telemetria eta alertak hainbat tratamendu-agertokitarako antolatuz, eta datuen osotasuna eta erabilgarritasuna egiaztatuz.

**Ebidentziaren abiapuntua:** [docs/evidence/CG32_CAMPAIGN_20261028.md](../../docs/evidence/CG32_CAMPAIGN_20261028.md).

**Defentsan egiteko:** Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G80 — Karga eta fidagarritasuna

**10eko deskriptorea:** Sistemaren portaera karga-proba sinpleekin egiaztatu du, hobekuntza egokiak proposatu ditu eta segurtasun-neurri oinarrizkoak justifikatu ditu (sarbideak, portuak, kredentzialak eta datuen babesa).

**Ebidentziaren abiapuntua:** [docs/evidence/CG32_CAMPAIGN_20261028.md](../../docs/evidence/CG32_CAMPAIGN_20261028.md).

**Defentsan egiteko:** Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G85 — Karga eta fidagarritasuna

**10eko deskriptorea:** Soluzioaren mugak aztertzen ditu, eta nodo bakarreko ingurunearen eta kluster erredundante baten arteko desberdintasunak teknikoki justifikatzen ditu.

**Ebidentziaren abiapuntua:** [docs/evidence/CG32_CAMPAIGN_20261028.md](../../docs/evidence/CG32_CAMPAIGN_20261028.md).

**Defentsan egiteko:** Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G87 — Panelak eta negozioa

**10eko deskriptorea:** Aginte-koadro oso eta argia garatu du, bistaratze egoki eta kalitatezkoekin.

**Ebidentziaren abiapuntua:** [docs/evidence/CG19_2026-10-21.md](../../docs/evidence/CG19_2026-10-21.md).

**Defentsan egiteko:** Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G90 — Karga eta fidagarritasuna

**10eko deskriptorea:** Datu-irenste sistema sendoa garatu du, Kafka-ren desakoplamendu-funtzioa eta kontsumitzaile independenteak egoki erabiliz. Kontsumitzaileen etenaldiak eta berrabiarazteak probatu ditu, offset-en kudeaketa eta datuen jarraitutasuna egiaztatuz.

**Ebidentziaren abiapuntua:** [docs/evidence/CG32_CAMPAIGN_20261028.md](../../docs/evidence/CG32_CAMPAIGN_20261028.md).

**Defentsan egiteko:** Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G92 — Integrazioa eta kalitatea

**10eko deskriptorea:** Datuen prozesamendu- eta inferentzia-fluxu osoa modu sendoan automatizatu du: datuak eraldatu eta balioztatzen ditu, InvokeHTTP bidez scoring-APIaren emaitzak jasotzen ditu, RouteOnAttribute edo baliokidea erabiliz arrisku-mailaren arabera bideratzen ditu, eta telemetria zein alertak Elasticsearch-en egoki biltegiratzen direla egiaztatzen du. Erroreen kudeaketa eta fluxuaren funtzionamendua probatu ditu.

**Ebidentziaren abiapuntua:** [docs/evidence/CG20_SAME_EVENT_20261022.md](../../docs/evidence/CG20_SAME_EVENT_20261022.md).

**Defentsan egiteko:** Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G95 — Integrazioa eta kalitatea

**10eko deskriptorea:** Datuen kalitate-kontrolak probatu eta dokumentatu ditu (balio falta direnak, formatu okerrak, bikoizketak), eta errore horiek ondorengo analisian eta inferentzian izan dezaketen eragina azaltzen du.

**Ebidentziaren abiapuntua:** [docs/evidence/CG20_SAME_EVENT_20261022.md](../../docs/evidence/CG20_SAME_EVENT_20261022.md).

**Defentsan egiteko:** Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G96 — Karga eta fidagarritasuna

**10eko deskriptorea:** Etenaldi edo karga-probak egiten ditu, datu-galerak eta bikoizketa posibleak egiaztatzen ditu, eta horiek murrizteko neurri egokiak proposatu eta aplikatzen ditu.

**Ebidentziaren abiapuntua:** [docs/evidence/CG32_CAMPAIGN_20261028.md](../../docs/evidence/CG32_CAMPAIGN_20261028.md).

**Defentsan egiteko:** Bereizi HTTP latentzia eta E2E latentzia; azaldu backlog-a, berreskurapena eta nodo bakarraren muga. Kanpainaren modeloa eta gaurko modeloa ez nahastu.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G100 — Panelak eta negozioa

**10eko deskriptorea:** Datu-hautaketa estrategikoa egin du, sentsoreen neurketak, makinen metadatuak eta inferentziaren emaitzak (hutsegite-probabilitatea eta alerta-maila) integratuz. Aldagai bakoitzaren erabilgarritasuna justifikatu du eta hautatutako datuek mantentze prediktiboaren analisian eta erabakiak hartzeko prozesuan duten ekarpena frogatu du.

**Ebidentziaren abiapuntua:** [docs/evidence/CG19_2026-10-21.md](../../docs/evidence/CG19_2026-10-21.md).

**Defentsan egiteko:** Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G101 — Integrazioa eta kalitatea

**10eko deskriptorea:** Garbiketa- eta eraldaketa-fluxu sendoa garatzen du, balio baliogabeak bereiziz eta datuen koherentzia egiaztatuz, biltegiratzean eta scoring-APIarekin integratzean.

**Ebidentziaren abiapuntua:** [docs/evidence/CG20_SAME_EVENT_20261022.md](../../docs/evidence/CG20_SAME_EVENT_20261022.md).

**Defentsan egiteko:** Jarraitu event_id bera katean. Azaldu baliozkotzea, baztertzea, replay eta bikoizketen kontrola.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G104 — Panelak eta negozioa

**10eko deskriptorea:** Alerten emaitzak kritikoki interpretatzen ditu, alerta okerren ondorioak eta geldialdien kostua aztertzen ditu, eta datuetan oinarritutako mantentze-jarduera arrazoituak proposatzen ditu.

**Ebidentziaren abiapuntua:** [docs/evidence/CG19_2026-10-21.md](../../docs/evidence/CG19_2026-10-21.md).

**Defentsan egiteko:** Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.

## G105 — Panelak eta negozioa

**10eko deskriptorea:** Erabakiak denbora errealean hartzea ahalbidetzen duen dashboard ikusgarri eta zehatza sortu du.

**Ebidentziaren abiapuntua:** [docs/evidence/CG19_2026-10-21.md](../../docs/evidence/CG19_2026-10-21.md).

**Defentsan egiteko:** Erakutsi denbora-tartea, makina-iragazkia, alerta eta mantentze-erabakia. Ez nahastu behaketa zaharra uneko egoerarekin.

**Egoera:** materiala eskuragarri; ikaslearen azalpena eta irakaslearen balorazioa egiaztatzeko.
