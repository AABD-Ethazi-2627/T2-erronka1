# Laneki — metrikak eta kostuak

2026-11-12ko tokiko egiaztapena. Lau orriak (Hasiera, Makinak, Datuak eta Abisuak) Streamlit AppTest bidez exekutatu dira API errealarekin, salbuespenik gabe. Nabigatzailearen ikus-egiaztapena ezin izan da egin, automatizazio-host-a erabilgarri ez zegoelako.

33 probak gainditu dira. APIko makina-kopurua, alerta kritikoak eta batez besteko tenperatura makina-zerrendarekin kontrastatu dira. Azken behaketan 50 makina zeuden, bi AVISO eta zero CRITICA; une horretako argazkia da.

## Ereduaren metrikak

Ebaluazioa modeloaren SHA-256, atalase, iturri eta balidazio-partizioarekin lotuta dago. Matrizea: TN=1150, FP=9, FN=9, TP=32; recall eta precision %78,05. Garapen-balidazio berrerabilia da, ez zuzeneko kalitatea. CSV puntuazioak `float_precision='round_trip'` erabiliz irakurri dira, atalaseko konparazioak ez aldatzeko.

`python scripts/configure_laneki_evaluation.py` komandoak lotura berreraikitzen du; ondoren `docker compose restart scoring-api`. Modelo edo esparru berria erabiltzean ebaluazioa berriz egiaztatu behar da.

## Kostuak

Abisuak orriak makina bakoitzaren azken AVISO/CRITICA behaketatik aurrekontua kalkulatzen du. Lehenetsitako 30 minutuko indarraldia, 200 € ikuskapena, 300 € esku-hartzea, zero geldialdi-ordu eta 1.200 €/h erabiltzaileak alda ditzake. Plangintza-suposizioak dira, ez gastu errealak. Ez da scorea galeraren probabilitate bihurtzen.

Gertaera errepikatuek ez dute makina birritan kontatzen. Ondorengo OK behaketak aurreko alerta ordezkatzen du. Datu zaharrak eta baliogabeak kalkulutik kanpo geratzen dira eta estalduraren muga erakusten da. Freskatzeak ez du gastu metatua handitzen.

Erabiltzaileak tarifa eta benetako geldialdien erregistroak badituela baieztatu du. Iturriaren kokapena oraindik falta da: makina, geldialdiaren hasiera/amaiera, orduko tarifa eta esku-hartze kostua behar dira benetako gastua konektatzeko. Bitartean gastu erreala E/D da.

Ebidentzia lokalak: `outputs/laneki-live-check-20261112.json`, `outputs/laneki-checks-20261112.log`. Bideoa egiteke dago; grabatu aurretik benetako kostuak eta pantailaren ikus-egiaztapena osatu.
