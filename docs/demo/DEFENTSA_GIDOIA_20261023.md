# CNC Guard: defentsarako gidoi editagarria

Jatorrizko gidoia: 2026-10-23. **Eguneratzea: 2026-10-28**, PR91 integratu ondoren. Proiektua: `AABD-Ethazi-2627/T2-erronka1`; egiaztatutako dokumentu-oinarria: `main` `b2186e519e5444dcdb127d9409da105a8fe6d674`. Jatorrizko erreferentzia `55cfd63d71c848acbd7647eab7b69bec768b646d` zen; beheko 23/10eko emaitzak historiko gisa mantentzen dira. Lotutako iturriak egungo oinarrian kontsultatu dira, beren jatorrizko data eta mugekin.

Entsegua prestatzeko Markdown gidoia da. Ez da PPTX aurkezpena, egindako entseguaren akta edo euskararen giza balioztapena. Lau kiderentzako banaketa **proposamena** da; ez du inoren benetako parte-hartzea egiaztatzen. Kideek izenak eta txandak adostu behar dituzte.

Ikasteko azalpen garatuak, adibideak eta bloke bakoitzeko galdera-erantzunak [gaztelaniazko prestakuntza-materialean](AZALPENAK_20261028.md) daude. Uneko neurketa-erreferentzia [28/10eko CG32 kanpaina](../evidence/CG32_CAMPAIGN_20261028.md) da: berreraikitako hautagaia neurtzen du, ez CG26ko bundle historikoa edo RF research paketea.

## Denbora eta erabilera

**Hamar minutuko egitura**, [enuntziatuko «Demo Aurkezpena (10 minutu)»](../../ENUNTZIATUA.md) atala abiapuntu hartuta. Atal horrek sistema live erakustea eskatzen du. Gidoi hau eta [artxibatutako ebidentzien entsegua](ENTSEGU_PRESTATUA_20261028.md) azalpena prestatzeko eta babeskopiatzat erabiltzeko dira; ez dute zuzeneko demo hori egiaztatzen. Azken entregaren data, ordua, kanala eta galderen tartea baieztatzea falta da.

Erabiltzailearen arabera, entrega dokumentazioa eta gelako aurkezpena izan daiteke; oraingoz hipotesia da. Kostuei eta sailkapen tabularrari buruzko postek gai horiek argitzen dituzte, baina ez azken entregaren baldintzak.

Proposatutako lau blokeak:

1. **1. kidea, 0:00-2:00:** sarrera eta lehen ideia: uneko egoera sailkatzen dugu.
2. **2. kidea, 2:00-4:30:** bigarren ideia: datuen mugak eta ebaluazioaren banaketa.
3. **3. kidea, 4:30-7:00:** hirugarren ideia: ereduaren latentzia eta kate osoarena bereizi.
4. **4. kidea, 7:00-10:00:** laugarren ideia: erabakiak kostuekin alderatu; amaiera eta galderetarako gonbita.

Pantailako euskarriak eta hizlariaren oharrak bereizita daude behean. Pantailara izenburua, gako-hitzak eta aukeratutako irudia bakarrik eraman. Erabili letra handia; xehetasun teknikoak eta iturrien zerrenda kontsultarako utzi. Entseguan denbora neurtu eta gidoia egokitu; ez irakurri paragrafo guztiak pantailatik.

## 1. blokea: zer sailkatzen dugu?

### Pantailako euskarria

**CNC Guard: uneko egoeraren sailkapena**

- Uneko irakurketa → sailkapena → pertsonaren berrikuspena.
- Bost sentsore + `machine_type` bundlean; azken aldagai hori argitzeko.
- Makinen gaineko ekintza automatikorik ez.

### Hizlariaren oharrak: 1. kidea

> Egun on guztioi. B taldearen CNC Guard lana aurkeztuko dugu. Gure galdera hau da: zer ondorio atera dezakegu makina baten uneko irakurketatik, eta zer ezin dugu ondorioztatu?
>
> Lau ideia azalduko ditugu: lehenik, sistemaren helburua; ondoren, datuak eta ebaluazioa; gero, sistemaren neurketak; eta amaitzeko, alerta baten kostua eta lanaren mugak.
>
> Erronka honetan sailkapen tabularra egiten dugu. Errenkada bakoitza une bateko argazkia da. Sistemak une horretako egoera sailkatzen du; ez du esaten makina noiz apurtuko den, zenbat bizitza erabilgarri geratzen zaion edo hurrengo hogeita lau orduetan zer gertatuko den.
>
> Bundleak Random Forest eta Isolation Forest ditu. Lehenak uneko hutsegitearen sailkapenerako scorea ematen du; bigarrenak irakurketaren ezohikotasuna aztertzen du. Ezohikoa izateak ez du berez matxura baieztatzen. Gainera, zerbitzatutako scorea ez dago probabilitate kalibratu gisa egiaztatuta.
>
> Bost aldagai fisikoak hauek dira: giroko tenperatura, prozesuko tenperatura, biraketa-abiadura, torkea eta erremintaren higadura. Bundleak makina mota ere erabiltzen du. Erabiltzaileak ekarritako postaren adibideak bost sentsoreak bakarrik zerrendatzen ditu; `machine_type` onargarria den argitzea falta da. Ez dugu aldagai hori kendu, ezta bundlea aldatu ere.
>
> Sistemaren irteerak pertsona baten berrikuspena laguntzeko dira. Ez dute makina bat gelditzen edo martxan jartzen.

**Ahotsa eta begirada:** lehen galderaren ondoren eten laburra egin; entzuleei begiratu. Ez zerrendatu aldagaiak presaka.

**Erreleboa:** «Helburua zehaztuta, bigarren kideak azalduko du zer daturekin ebaluatu den eta zer muga dituen ebaluazio horrek».

Iturriak: [CG26ko bundlearen erregistroa eta sarreren zerrenda](../evidence/CG26_REHEARSAL_2026-10-21.json), eta [iturri akademikoen aplikazioa](ORAL_GUIDE_APPLIED_20261023.md).

## 2. blokea: zer frogatzen du ebaluazioak?

### Pantailako euskarria

**Datuen mugak ebaluazioan ere mantendu**

- `tool_wear_min`: uneko kobariablea; ez denbora-historiala.
- CG34: train-eko 5.600 errenkada / 190 positibo, baliozkotze gurutzatuan.
- Test zaharra baztertuta; azken ebaluazio independentea ez dago egiaztatuta.

### Hizlariaren oharrak: 2. kidea

> Lehenengo muga datuen izaera da. `tool_wear_min` aldagaiak erremintaren higadura adierazten du uneko errenkadan. Minututan egoteak ez du errenkaden arteko sekuentziarik edo makina beraren historialik sortzen. Beraz, ez dugu denbora-serieen aurreikuspenik aldarrikatzen.
>
> `timestamp` ez da ereduaren X sarrera-matrizean sartzen. Hala ere, gertakariaren metadatu gisa mantendu daiteke trazabilitaterako, `event_id` identifikatzailearekin batera. Ereduaren sarrerak eta garraioaren metadatuak bereizten ditugu.
>
> Ezaugarri fisikoak interpretatzean ere unitateak zaindu behar dira. Adibidez, tenperaturen diferentzia bi tenperaturen arteko kenketa da. `rpm * torque_Nm` biderkadura potentziarekin lotutako proxy bat da; ez da zuzenean watt-etan emandako potentzia. Watt-etan adierazteko, `2π/60` bihurketa-faktorea behar da. Adibide horrek ez du esan nahi formula berririk gehitu dugunik.
>
> CG34 azterketak train-eko bost mila eta seiehun errenkada erabiltzen ditu; horietatik ehun eta laurogeita hamar positiboak dira. Baliozkotze gurutzatu habiaratuan, aukeraketa eta atalasearen doikuntza barneko zatian egiten dira; kanpoko zatiak emaitzak ebaluatzeko erabiltzen dira.
>
> Kostuen analisia lehendik gordetako scoreekin osatutako gehigarria da. Ez du entrenamendu berririk edo zerbitzuko atalaseen aldaketarik ekarri. Konparazio osagarri batek ere ez du automatikoki ordezkatzen zerbitzatutako RF+IF bundlea.
>
> Test zaharra ez da azterketa honen ebaluazio independente gisa erabiltzen. Aurreko baliozkotze-emaitzak ere ez ditugu azken test baten emaitzatzat aurkezten. Muga hori esatea beharrezkoa da emaitzak behar bezala ulertzeko.

**Azalpenerako laguntza:** entzuleek galdetzen badute, azaldu «barnekoa aukeratzeko; kanpokoa ebaluatzeko». Ez gehitu aurkezpenean ez dagoen azken testaren emaitzarik.

**Erreleboa:** «Orain, hirugarren kideak neurketak erakutsiko ditu: ereduaren kalkulua eta datuak kate osoa zeharkatzeko denbora bereizita».

Iturriak: [CG34ren protokoloa eta mugak](../evidence/CG34_20261023/manifest.json), [kostuen analisiaren konfigurazioa](../evidence/CG34_20261023/business-costs.json), [CG34ren berrikuspena](../evidence/CG34_REVIEW_20261023.md) eta [CG26ren sarrerak](../evidence/CG26_REHEARSAL_2026-10-21.json).

## 3. blokea: zer neurtu da benetan?

### Pantailako euskarria

**Ereduaren denbora eta kate osoarena**

- **28/10eko kanpaina:** zazpi exekuzio; **1.860 eskaini / 1.860 gorde**.
- RF+IF prozesuan: p95 **5,929676 ms**, n = 600; ez HTTP/E2E.
- Hiru oinarrizko exekuzioen E2E p95ak: **82,747 / 83,859 / 78,135 s**.
- **Ez du 10 gertakari/s mantentzen ilara pilatu gabe; ez du E2E p95 ≤1 s betetzen.**

### Hizlariaren oharrak: 3. kidea

> Uneko erreferentzia urriaren hogeita zortziko kanpaina da. Zazpi exekuziotan mila zortziehun eta hirurogei gertakari eskaini eta gorde ziren. Exekuzio bakoitzeko alderaketaren arabera, ez zen baliozko gertakaririk galdu, ez zen azken ID bikoizturik agertu eta ez zen gertakaririk zain geratu; azken laga zero zen. Emaitza horiek laborategiko gertakari nominalei dagozkie; ez dute edozein hutsegiteren edo kargaren aurreko berme orokorrik ematen.
>
> Hiru oinarrizko exekuziotan seiehun gertakari eskaini ziren bakoitzean, segundoko hamar, hirurogei segundoz. Gehieneko laga hirurehun eta berrogeira iritsi zen, eta ondoren hustu zen. Beraz, eskaintza hamar gertakari segundokoa izateak ez du esan nahi sistemak tasa hori ilara pilatu gabe mantentzen duenik. Hustea barne hartuta, behatutako throughput-a 4,1087 eta 4,2702 gertakari/s artekoa izan zen.
>
> Hemen hiru denbora bereizten ditugu. RF eta IF prozesu berean kalkulatzeko p95a 5,929676 milisegundokoa da, seiehun behaketatan; aurreko hogei beroketa-deiak kanpoan utzi ziren. Hiru oinarrizko exekuzioen HTTP zerbitzariko p95ak 14,958, 15,116 eta 14,365 milisegundokoak dira. Kate osoko p95ak, aldiz, 82,747, 83,859 eta 78,135 segundokoak dira. Ez ditugu pertzentil horiek batzen edo exekuzio desberdinetako laginak nahasten.
>
> E2E neurketa CSV lerroaren fsync egin ondoren hasten da eta ESko lehen kontsultak dokumentua ikusten duenean amaitzen da; refresh eta polling barne hartzen ditu. Ez du SMB bidezko deskarga neurtzen. Proposatutako segundo bateko E2E helburua ez da bete; hiru oinarrizko exekuzioek HTTPko ehun milisegundoko helburua bete dute. Ez ditugu helburu horiek irakaslearen baldintza ofizialtzat aurkezten.
>
> Hogei segundoko pausaren eta behatutako SIGKILLaren ondoren, hogeitik hogei gertakari berreskuratu ziren proba bakoitzean. Ez dago frogatuta etena HTTP erantzunaren eta Kafka commit-aren arteko une zehatzean gertatu zenik. Discoverren gordetako irudiak gertakari baten IDa eta RF hash bera erakusten ditu; ez da gertakari guztien banakako ikuskapena.
>
> NiFik zikloak planifikatzen ditu, eta Python workerra da Kafka offsetaren jabe bakarra. APIak erantzuna ledgerrean baieztatzen du 200 eman aurretik; workerrak artxiboa eta ES baieztatu ondoren egiten du Kafka commit-a. Eskaera bera errepikatzean, ledger idempotenteak erantzun bera berreskuratzen du, `scored_at` barne. Ledgerra ez da ereduari emandako sentsore-historiala, eta mekanismo horrek ez du exactly-once banatua frogatzen.
>
> Kanpainak berreraikitako hautagaia erabili du, bere hash eta egiaztagiri propioekin. Ez da CG26ko bundle historikoa, nahiz eta model_version etiketa bera izan; RF research paketea ere beste artefaktu bat da. Hemen gordetako ebidentzia azaltzen dugu, neurketa berririk edo taldearen entsegurik egin gabe. Sistemak ez du CNCaren gaineko ekintza automatikorik egiten; pertsonak berrikusten du alerta.

**Etenaldia:** «ez da betetzen» esan ondoren, tarte laburra utzi. Ez laburbildu sistema osoa «sei milisegundotan dabil» esanez.

**Erreleboa:** «Denborak eta kanpainaren muga ikusita, laugarren kideak azalduko du zergatik alderatzen ditugun alertak kostuen bidez ere».

### Kontsultarako taula: 28/10eko exekuzioak

Taula [kanpainaren txostenarekin](../evidence/CG32_CAMPAIGN_20261028.md) eta [`raw-runs.zip`](../evidence/CG32_CAMPAIGN_20261028/raw-runs.zip) artxiboko exekuzio bakoitzaren `run.json` fitxategiarekin alderatuta dago. [SHA-256 indizeak](../evidence/CG32_CAMPAIGN_20261028/raw-index.json) fitxategi zehatzak identifikatzen ditu. Hiru hamartar erakusten dira; pertzentilak exekuzio bakoitzekoak dira.

| Exekuzioa | Eskaini / gorde | HTTP p95 ms | E2E p95 s | Lag gehien / azken | Hustea s |
|---|---:|---:|---:|---:|---:|
| batch32-base-1 | 600 / 600 | 14,958 | 82,747 | 340 / 0 | 87,888 |
| batch32-base-2 | 600 / 600 | 15,116 | 83,859 | 340 / 0 | 88,596 |
| batch32-base-3 | 600 / 600 | 14,365 | 78,135 | 340 / 0 | 83,132 |
| batch32-kill | 20 / 20 | 15,905 | 39,762 | 20 / 0 | 27,714 |
| batch32-pause | 20 / 20 | 13,414 | 25,728 | 18 / 0 | 8,144 |
| batch32-pilot | 10 / 10 | 13,577 | 12,162 | 9 / 0 | 15,022 |
| rebuilt-pilot | 10 / 10 | 19,906 | 25,928 | 9 / 0 | 29,045 |

Guztira 1.860 dira, baina ez 1.860 behaketa independente recall-a neurtzeko: train-eko fixture nominalak dira, agerraldi bakoitzeko ID berriekin. `rebuilt-pilot` exekuzioak `max_records=1` erabili zuen; besteek 32. Ez da 50/s-ko probarik egin, 10/s-koak ilara pilatzen duelako eta helburua betetzen ez duelako. Pilotu bakoitzaren errepikapen bakarrak ez du A/B hobekuntza kausala frogatzen.

**Jatorriaren muga:** [provenientziak](../evidence/CG32_CAMPAIGN_20261028/provenance.json) `b815771` gaineko hasiera gordetzen du, commit gabeko egokitzapenarekin; lab kodearen byteak `3061a6c`rekin bat datoz. Kanpaina ez zen goiburuko merge garbiaren gainean exekutatu. Grafoko APIak Python 3.11 darabil; tokiko osagarriak 3.12.14. Osagarriaren HTTP bezeroaren joan-etorria eta taulako HTTP zerbitzariaren denbora neurketa desberdinak dira.

Iturriak: [ereduaren 600 behaketak](../evidence/CG32_CAMPAIGN_20261028/model-latency.json), [hautagaiaren identitatea](../evidence/CG32_REBUILT_IDENTITY_20261028.json), [runtime eta birkarga](../evidence/CG32_CAMPAIGN_20261028/supplement-runtime-reload.json), [Discoverren egiaztagiria](../evidence/CG32_CAMPAIGN_20261028/discover-receipt.json), [grafoko kontratua](../CG14_AUTOMATIC_GRAPH.md) eta [ledgerreko erantzunen kontratua](../SCORING_REPLAY_CONTRACT.md).

### Erreferentzia historikoa: 23/10eko jatorrizko bundlea

23/10eko [ereduaren neurketak](../evidence/CG32_ORIGINAL_MODEL_20261023.json) RF+IF p95 **11,073 ms** eman zuen, n=600. [Pilotuak](../evidence/CG32_ORIGINAL_PILOT_20261023.json) **10 eskaini / 10 gorde** eta hamar ES dokumentu jaso zituen; baieztatutako offseta 10 zen. HTTP p95 **60,320 ms** eta E2E p95 **55,748 s** ziren. [Discoverren orduko erregistroa](../evidence/CG32_ORIGINAL_DISCOVER_20261023.json) ere mantentzen da. Datu historikoak dira, ez azken kanpaina, eta ez dira 28/10eko hautagaiaren emaitzekin bateratzen edo hobekuntza kausal gisa aurkezten.

## 4. blokea: nola alderatu alerten kostua?

### Pantailako euskarria

**Recall-a eta kostua batera aztertu**

- FN **5.000 €** · FP **200 €** · TP **300 €** · TN **0 €**.
- [Lehendik sortutako kostu-kurbak](../evidence/CG34_20261023/business-cost-curves.png): OOF train, ez azken ebaluazioa.
- Kostu-eszenarioa; ez da benetan lortutako aurrezpena.

Grafikoa erakusteko laguntza: horizontalean atalasea edo recall-a dago; bertikalean kostua, **€/1.000 gertakari**. Jatorrizko grafikoak hiru eredu erakusten ditu, ez katalogo osoa. Ez txikitu irudia testuarekin batera pilatzeko; iturriaren izenburua, ardatzak eta mugak ikusgai mantendu.

### Hizlariaren oharrak: 4. kidea

> Azken ideia da recall-a igotzea ez dela irizpide bakarra. Hutsegite gehiago atzematea baliagarria izan daiteke, baina alarma faltsuek eta alerta zuzenek ere kostua dute.
>
> Erabiltzaileak ekarritako, Aitor Aretxaga Agirreri egotzitako urriaren hogeita biko postak lau kostu ematen ditu: atzeman gabeko hutsegite bakoitzeko bost mila euro; alarma faltsu bakoitzeko berrehun; alerta zuzen bakoitzeko hirurehun; eta negatibo zuzen bakoitzeko zero. Erronkako kostu-parametro gisa erabiltzen ditugu. Ez ditugu enpresa baten kontabilitate erreal gisa egiaztatu.
>
> Kalkulua lau gelaxken batura da: FN kopurua bider bost mila, FP kopurua bider berrehun, TP kopurua bider hirurehun eta TN kopurua bider zero. TPren kostua ere sartzea beharrezkoa da. Ez dugu onartzen alerta zuzen oro doakoa denik.
>
> Hona hemen adibide aritmetiko bat: FN bat TP bihurtuz gero, eszenarioaren kostua lau mila eta zazpiehun euro jaisten da. Beste emaitzak berdin mantenduta, horrek hogeita hiru koma bost alarma faltsu gehigarriren kostua berdinduko luke. Hau ez da operazio-arau unibertsala; emandako lau kostuen ondorio aritmetikoa da.
>
> Grafikoan atalasea eta recall-a aldatzean kostua nola mugitzen den ikus dezakegu. Kurba horiek Python bidez egindako analisiaren barruan daude jada. OOF train-eko doikuntza-kurbak dira; ez dira azken testaren emaitza edo lantegian neurtutako aurrezpena. Kostuen gehigarriak ez du zerbitzuko bundlea edo atalasea aldatu.
>
> Amaitzeko: uneko egoera sailkatzen dugu; ebaluazioaren datuak eta mugak bereizten ditugu; ereduaren denbora eta kate osoarena ez ditugu nahasten; eta alertak lau kostuen bidez ere alderatzen ditugu. Hurrengo erabakietan argitu beharrekoak dira `machine_type` aldagaiaren onarpena eta entregaren baldintzak. Azken kanpainak ez du segundo bateko E2E helburua betetzen, eta ez du 10 gertakari/s ilararik gabe mantentzen.
>
> Eskerrik asko zuen arretagatik. Orain, galderak erantzuteko prest gaude, gordetako ebidentziak eta haren mugak oinarri hartuta.

**Grafikoa azaltzean:** lehenik ardatzak eta unitatea azaldu; gero kurba bat seinalatu. Ez aurkeztu kostu minimoa azken test independente batean edo ekoizpenean baieztatuta balego bezala.

Iturriak: [lau kostuen konfigurazioa](../evidence/CG34_20261023/business-costs.json), [emaitzak eta 23,5eko oreka aritmetikoa](../evidence/CG34_20261023/business-summary.json), [kostu-taulak](../evidence/CG34_20261023/business-tables.md), [faseko kostu-koaderno osagarria](../../notebooks/02_business_costs_evidence.ipynb) eta [iturri akademikoen jatorria](ORAL_GUIDE_APPLIED_20261023.md).

## Galderetarako erantzun laburrak

Erantzuleak ere proposatuak dira. Galdera entzun, eten laburra egin eta erantzun. Daturik falta bada, esan argi; ez asmatu erantzunik.

1. **«Noiz apurtuko den aurreikusten duzue?» (1. kidea)**
   «Ez. Uneko snapshot-a sailkatzen dugu. Ez dago ETA, RUL edo etorkizuneko denbora-horizonte baten balioztapenik».
2. **«`tool_wear_min` denbora-serie bat da?» (2. kidea)**
   «Uneko higaduraren kobariablea da. Bere kabuz ez du makina beraren behaketa ordenatuen historialik ematen».
3. **«Zergatik dago `machine_type`, postak bost sentsore esaten baditu?» (1. kidea)**
   «Bundlearen kontratuak bost sentsoreak eta makina mota jasotzen ditu. Postaren adibidearekiko desberdintasuna dago; azken aldagaiaren onarpena irakaslearekin argitu behar da. Ez dugu bundlea aldatu».
4. **«`rpm * torque_Nm` watt-ak dira?» (2. kidea)**
   «Proxy bat da. Potentzia mekanikoa watt-etan kalkulatzeko, `P = torque_Nm * rpm * 2π/60` bihurketa behar da».
5. **«Sarrera bakoitza independentea bada, zergatik ledgerra?» (3. kidea)**
   «Ereduak ez du aurreko sentsore-errenkaden sekuentziarik behar. Ledgerra baieztatutako erantzun bera berreskuratzeko da, eskaera errepikatzean. Trazabilitatea eta inferentziaren sarrerak gauza desberdinak dira».
6. **«11 ms-ko latentzia du sistema osoak?» (3. kidea)**
   «11,073 ms 23/10eko neurketa historikoa da, RF+IF prozesuan. 28/10eko hautagaiaren p95a 5,929676 ms da prozesuan; oinarrizko hiru exekuzioen HTTP p95ak 14,958/15,116/14,365 ms eta E2E p95ak 82,747/83,859/78,135 s dira. Ez da sistema osoaren latentzia bakarra, eta segundo bateko E2E helburua ez da betetzen».
7. **«Ez da inoiz daturik galtzen?» (3. kidea)**
   «28/10eko zazpi exekuzioek 1.860 eskaini eta 1.860 gorde dituzte, zero galera eta zero azken ID bikoizturekin. Lagin nominal horrek eta behatutako etenek ez dute karga edo hutsegite guztietarako bermerik ematen; 10/s-ko eskaintzak ilara pilatzen du».
8. **«Azken test independentea gainditu du?» (2. kidea)**
   «Ez dugu hori aldarrikatzen. CG34k train-eko 5.600 errenkadetan baliozkotze gurutzatua erabiltzen du. Test zaharra baztertuta dago, eta aurreko baliozkotzea ez da azken test independentea».
9. **«Zenbat diru aurreztu duzue benetan?» (4. kidea)**
   «Ez dugu aurrezpen errealik neurtu. Emandako lau kostuekin eszenarioak kalkulatu ditugu. Benetako aurrezpena frogatzeko, operazio-emaitzak eta benetako kostuak egiaztatu beharko lirateke».
10. **«Kostuek atalase berria jarri dute ekoizpenean?» (4. kidea)**
    «Ez. Gehigarria lehendik gordetako scoreekin egin da. Ez da refit berririk edo aldaketa operatiborik egin. Analisiaren aukeraketa eta zerbitzatutako atalasea bereizita mantentzen ditugu».
11. **«IFren alerta batek hutsegitea baieztatzen du?» (1. kidea)**
    «Ez. IFk ezohikotasuna adierazten du. Hori eta RFren uneko sailkapen-scorea bereizten ditugu; ez dira etorkizuneko matxuraren probabilitate kalibratuak».
12. **«Noiz, non eta zenbat denboran aurkeztu behar da? Nota berezia ziurtatuta dago?» (4. kidea)**
    «Enuntziatuak hamar minutuko demo live bat jasotzen du; egitura hori prestatzen ari gara. Azken data, ordua, kanala eta galderetarako tartea argitzea falta da. Postak analisi ekonomikoa baloratzen du, baina ez dugu nota edo ohorezko emaitzarik ziurtatzen».

## Entsegu-fitxa: taldeak betetzeko

- Adostutako izenak eta blokeak: ____________________
- Irakasleak baieztatutako iraupena eta galderen tartea: ____________________
- Entseguaren data eta benetako iraupena: ____________________
- Euskararen giza berrikuslea eta egin beharreko zuzenketak: ____________________
- Moztu edo argitu beharreko pasarteak: ____________________
- `machine_type` eta azken entregaren baldintzei buruz jasotako baieztapena: ____________________

Fitxa bete gabe dago. Prestaketa honek ez du egindako entsegurik, taldearen benetako parte-hartzerik, giza onarpenik edo entrega buruturik egiaztatzen.
