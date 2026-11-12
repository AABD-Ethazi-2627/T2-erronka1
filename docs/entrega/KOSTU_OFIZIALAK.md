# Kostu operatiboen taula ofiziala

Iturria: erabiltzaileak 2026-11-12an emandako kostuen taula.

| Kasua | Kostua | Esanahia |
|---|---:|---|
| FN | 5.000 € | Atzeman gabeko matxura: geldialdia eta urgentziazko konponketa barne |
| FP | 200 € | Alferrikako ikuskapenaren batez bestekoa |
| TP | 300 € | Mantentze prebentiboko piezak |
| TN | 0 € | Funtzionamendu egokia |

Kostua = 5.000 × FN + 200 × FP + 300 × TP. Ez gehitu berriro 3 × 1.200 €/h FNri: dagoeneko barnean dago. Tarifa hauek kasuaren batez besteko kostuak dira, ez fakturatutako gastu zehatzak.

Lanekiko Abisuak orriak azken behaketa indarrean duten AVISO/CRITICA makinen kopurua berriz kalkulatzen du. Makina bakoitzeko esku-hartze bakarra suposatuta, alerta guztiak FP balira 200 €/alerta dira; guztiak TP balira 300 €/alerta. Ez da scorea probabilitate kalibratu gisa erabiltzen. Tarte horrek ez ditu ezkutuko FNak hartzen eta ez da lantegiaren kostu osoaren muga.

AVISO eta CRITICA larritasun-mailak dira: ez dira FP eta TPren sinonimoak. Benetako kasuen kostua kalkulatzeko etiketa baieztatuak behar dira, baita alertarik gabeko matxuren erregistroak ere. Emandako taulak ez ditu erregistro horiek hornitzen; panelak baieztatutako kostua E/D mantentzen du.

Datuak orriak balidazioaren matrize egiaztatuarekin kostua erakusten du: FN=9, FP=9, TP=32, TN=1150 → **56.400 €**. Beti negatiboaren agertokia: 41 × 5.000 = 205.000 €; aldea 148.600 €. Balidazio berrerabiliko ariketa ekonomikoa da, ez zuzenean neurtutako aurrezkia.

Dokumentu honek aurreko egiaztapeneko 200 € AVISO / 300 € CRITICA esleipen-proposamena ordezkatzen du. Kostu ofizialak ez dira larritasunaren arabera esleitzen.

Egiaztapena: 34 proba gaindituta; Datuak eta Abisuak API errealarekin exekutatuta. Ebidentzia: `outputs/laneki-official-costs-tests.log` eta `outputs/laneki-official-costs-live.json`.

PRaren egiaztapena: azken origin/main oinarrian isolatutako adarrak 33 proba gainditu ditu. Aurreko 34ko zenbaketa tokiko lan-kopia zabalagoari dagokio.
