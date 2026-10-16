# ANEXO1 CNC Guard talde plana eta jarraipena

**Zirriborroa — 2026ko urriaren 16a.** Bertsio hau da GitHuben berrikusi eta eguneratzeko dokumentu nagusia. Ikasgelako txantiloiaren edukia Markdownera egokituta dago; ez du jatorrizko maketazioa mantentzen.

Erabiltzaileak lau GitHub kontuak eta rol teknikoak baieztatu ditu. Tutoretzako karguen banaketa, konpromisoak eta taldearen azken onespena baieztatzeko daude. Dokumentu honek ez du sinadurarik edo irakasleei egindako entregarik egiaztatzen.

## Taldearen datuak

| Eremua | Balioa |
|---|---|
| Proiektua eta taldearen behin behineko izena | CNC Guard |
| Ikasturtea | 2026–27 |
| Iraupena | 11 aste, enuntziatuaren arabera |
| Hasiera eta entrega data ofizialak | Irakasleekin baieztatzeko; plangintza honek ez du epea berrabiarazten |
| Ikastaldea | T2, izendapen ofiziala baieztatzeko |
| Tutorea | Baieztatzeko |
| Jatorrizko txantiloia | `01_Erronka1_CNC_Guard/materialak/ANEXO1-Eus.docx`, ikastaroko biltegian |

## Talde helburuak

1. Lana taldean egiten ikastea eta kide guztien parte hartzea bermatzea.
2. Elkar laguntzea, bakoitzak bere lana eta sistemaren ibilbide osoa ulertzeko.
3. CNC Guard laborategia garatzea: datuen trazabilitatea, ML ereduak, integrazioa eta panela, emaitza erreproduzigarriekin eta mugak argi adierazita.
4. [Errubrikako maila aurreratuko 40 deskribatzaileei](../rubrica/OBJETIVOS_Y_ETAPAS.md) ebidentziak lotzea, nota edo industria-eraginkortasuna frogatu gabe baieztatu gabe.
5. Etapak elkarrekin berrikustea eta azken defentsan norberaren ekarpena eta sistemaren funtzionamendua azaltzea.

## Baieztatutako rol teknikoak

| Rol nagusia | GitHub kontua | Banakako issue irekiak |
|---|---|---|
| Infra | petiteiker | #4, #5, #12, #13, #21, #23 |
| Diseinua | Angiecrizu | #19, #25, #26 |
| Dev | Niistal | #14, #15, #16, #17, #18 |
| Generalista ML eta Project lead | tears-mysthrala | #2, #3, #6, #7, #8, #9, #10 |

#24 partekatua da tears-mysthrala eta Angiecrizu artean. #1, #11, #20, #22 eta #27 lau kideei esleituta daude. Esleipena ez da lana amaitu izanaren froga. Iturria: [27 issue irekien snapshot-a](CG01_reparto_issues.json), 2026-10-16an egiaztatua.

## Tutoretzako karguak eta betebeharrak

Banaketa hau rol teknikoetatik eratorritako **proposamena** da, taldean baieztatzeko. Bost kargu eta lau kide daudenez, diseinuaren arduradunak bi kargu hartzea proposatzen da.

| Kargua | Proposatutako kontua | Betebeharrak |
|---|---|---|
| Koordinatzailea | tears-mysthrala | Bilerak moderatu, taldearen urratsak eta entregak antolatu, mendekotasunak jarraitu eta kideak animatu |
| Bozeramailea | Angiecrizu | Taldearen izenean hitz egin, erabakiak komunikatu eta irakasleekin harremana bideratu |
| Idazkaria | Angiecrizu | Dokumentuak eta aktak idatzi, gorde eta partekatu; hizkuntza zaindu eta entregak prestatu |
| Laguntzailea 1 | Niistal | Komunikazioaren tonua zaindu eta azalpen teknikoetan eta berrikuspenetan lagundu |
| Laguntzailea 2 | petiteiker | Denborak kontrolatu eta erabilgarritasunaren eta blokeoen jarraipenean lagundu |

## Lan konpromisoen proposamena

Konpromiso hauek esleitutako lana laburbiltzen dute. Kide bakoitzak bere konpromisoa berrikusi eta berretsi behar du; ez dira automatikoki onartutako adierazpen pertsonalak.

| Kontua | Proposatutako konpromisoa | Jarraipenaren ebidentzia | Berrespena edo sinadura |
|---|---|---|---|
| tears-mysthrala | Datuen eta ereduen trazabilitatea mantendu; ebaluazioa eta atalaseak justifikatu; mendekotasunak eta berrikuspenak koordinatu | Inbentarioa, esperimentuak, metrikak eta issue/PR berrikuspenak | Pendiente |
| Niistal | Kontratuak eta integrazio modularra garatu; erroreak eta bazterketak tratatu; gertaeren trazabilitatea probatu | Kodea, NiFi fluxuaren esportazioa, proba-datuak eta emaitzak | Pendiente |
| Angiecrizu | Panela eta memoria irizpideekin lotu; akordioak jaso; demoaren eta defentsaren gidoia prestatu | Kibana esportazioa eta irudiak, memoria, aktak eta gidoia | Pendiente |
| petiteiker | Abiarazteko eta berreskuratzeko argibideak mantendu; erabilgarritasuna eta blokeoak jaso; ahalmen- eta akats-probak egin | Konfigurazioak, komandoak, emaitzak eta berreskuratze-probak | Pendiente |

## Talde lanerako akordioen proposamena

- Kide guztien iritziak errespetatu eta proposamenak idatzi aurretik hausnartu eta adostu.
- Norbaitek zerbait ulertzen ez duenean, azalpena eman eta ikasten lagundu.
- Denbora aprobetxatu, materiala antolatuta mantendu eta lana epean aurkeztu.
- Besteen lanari eragiten dioten absentziak, aldaketak eta blokeoak garaiz jakinarazi.
- Desadostasunak konpontzeko tartea hartu eta hartutako erabakia aktan jaso.
- Astean behin issue bakoitzaren arduraduna, egoera erreala, ebidentzia, blokeoa eta hurrengo pausoa berrikusi.
- E1–E8 etapetako kontrol-puntuetan ebidentziak batera berrikusi. Push bat edo PR bat irekitzea ez da etapa amaitzea.

CI mergea prestatzeko unean exekutatuko da, erabiltzailearen jarraibidearen arabera.

## Helburu pertsonalak berrikusteko gida

Jatorrizko txantiloiak laguntza eskaintzea, ideiak ematea, besteen iritziak kontuan hartzea, zalantzak galdetzea, materiala zaintzea, arreta eta denbora hobeto kudeatzea proposatzen du. Kide bakoitzak bere helburuak aukeratu eta idatziko ditu; dokumentu honek ez dio inori jarrera edo gabeziarik egozten.

## Onespena eta jarraipena

- [x] Lau kontuak eta rol teknikoak erabiltzaileak baieztatuta.
- [x] Banaketa issue irekien esleipenekin kontrastatuta.
- [ ] Tutorea, ikastaldea eta data ofizialak baieztatu.
- [ ] Tutoretzako karguak eta konpromiso pertsonalak taldean berretsi.
- [ ] Helburuak, [urriaren 16tik azaroaren 6ra bitarteko lan-plana](../planificacion/README.md) eta errubrikaren zalantzak berrikusi.
- [ ] Bileraren data, parte-hartzaileak, aldaketak eta akordioa jaso.
- [ ] Sinadurak eta entrega egin, irakasleak eskatzen duen moduan, eta ebidentzia gorde.

Azalpen osagarria gaztelaniaz: [reparto y seguimiento](ANEXO1_reparto_y_seguimiento.md). Hemendik aurrera ANEXO1 honen edukia Markdown honetan mantenduko da; ez dago DOCX paralelo bat sinkronizatzeko beharrik.
