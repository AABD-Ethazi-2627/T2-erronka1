# Projects berrikuspena — 2026-10-15

## Irismena eta egiaztapena

- Taldearen iturria: [Project #2](https://github.com/orgs/AABD-Ethazi-2627/projects/2),
  `CNC Guard · T2-taldea`.
- Taldeen zentral komuna: [Project #1](https://github.com/orgs/AABD-Ethazi-2627/projects/1).
- Biltegia: `AABD-Ethazi-2627/T2-erronka1`; Project #2ko repository lotura zuzena zen.
- Taldearen 27 issue-ak irekiak daude eta arduradunak dituzte. Berrikuspenaren
  hasieran guztiak `Egiteke` ziren, tokiko lanean aurrerapenak bazeuden ere.
- `Taldea=B-taldea` eremuaren balioa mantendu da. Taldearen balioa eta repoaren
  izena ez dira kontzeptu bera; sinkronizatzaileak oraindik balio hori erabiltzen du.

## Aplikatutako doikuntzak

Parametroak, GANTT eta KANBAN ikuspegien iragazki hutsak
`repo:AABD-Ethazi-2627/T2-erronka1` bihurtu dira. Ez da zentralaren ikuspegirik aldatu.

Sei issue `Lanean` egoerara igaro dira, lanean hasitako irismena adierazteko:

- CG02: CSVaren inbentarioa eta 24 orduko etiketaren mugak dokumentatuta;
  kanpoko iturriak eta CG01eko akordioa egiaztatzeke.
- CG06: EDA notebooka eginda; Parquet eta DuckDB egiteke.
- CG07: AI4Iko egoera-sailkapenaren zatiketa eta fuga-prebentzioa eginda;
  ez dago denborazko leihoak/horizontea frogatzeko daturik.
- CG08: baseline-ak, RF pipeline-ak, bilaketa eta artefaktuak PRn prest;
  oraindik berrikusi eta integratu behar dira.
- CG09: Isolation Forest prest, normaltasunaren AI4I hurbilketarekin;
  ez da hutsegite-detekzioa hobetu duenik frogatu.
- CG10: F1/F2 eta erroreen analisia eginda; kanpoko test independentea,
  benetako kostuak eta alerta-politika operatiboa balioztatzeke.

[PR #29](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/29) bi Projects-etan
gehitu da, `Lanean` iturrian eta `In Progress` zentralean. `Draft` izaten jarraitzen du.
Ez da issue-rik itxi edo `Eginda` markatu. CG01eko talde-akordioa eta CG03ko
datu-kontratuak oraindik egiteke daude; hurrengo koordinazio-lanaren parte dira.

## Zentralaren parekotasuna

Sei issue-en status aldaketak tokiko sinkronizatzailearekin aplikatu dira,
eta ondorengo dry-runak kudeatutako eremuetan 0 diferentzia eman ditu.
PR berriaren presentzia eta status/talde eremuak ere zuzenean egiaztatu dira
`pullRequest.projectItems` bidez, Projecteko zerrenden indexazioaren mende soilik
utzi gabe.

Lehendik zeuden issue-en `Start date`, `Target date`, `Hasiera-data` eta
`Amaiera-data` balioak aldatu ez direla alderatu da. Hasierako 11 asteko datak
plangintza-proposamenak dira, ez benetako hasiera/amaieren froga; prototipoan
lehenago aurrera egiteak ez du egutegia berriro adostu dela esan nahi.
Beste taldeen lehendik zeuden elementuen identifikazioa eta irakurritako eremuak
berdin mantendu dira. Ez da ezer ezabatu edo artxibatu.

## Aktibazio-mugak

GitHub Actions bidezko 8 orduko sinkronizazioak `PROJECTS_SYNC_TOKEN` behar du,
eta repo-izen berriaren kode-zuzenketa oraindik PR #29n dago, ez main-en.
Eskuzko tokiko doikuntza hau ez da cron-aren aktibazioaren froga.
Ez da CI exekuziorik abiarazi, ez da credentzialik aldatu, eta ez da PRa mergeatu.
