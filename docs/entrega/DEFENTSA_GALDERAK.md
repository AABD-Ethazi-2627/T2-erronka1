# Defentsa prestatzeko galderak eta erantzunak

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
