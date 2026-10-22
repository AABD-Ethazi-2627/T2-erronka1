# CG02 berrikusteko gida

2026-10-16ko berrikuspen teknikoa. CG01 taldeak onartu eta itxi du; CG02ren emaitza teknikoa onartu eta PR #33 mergeatzea beste urrats bat da. Ez da modeloen entrenamendurik edo CG03/CG06ko integraziorik egiten hemen.

## Zer entregatzen da

| Galdera | Ebidentzia |
|---|---|
| Zer iturri eta zertarako? | [sources.json](sources.json): training lokala, SMB batchak eta eman gabeko mantentze-erregistro independentea |
| Zenbat lerro, zer zutabe eta zer kalitate? | [inventory.json](inventory.json): hashak, tamainak, faltanteak, zenbakizko akatsak, etiketak eta denbora |
| Zer esan nahi dute datuek? | [Txostena eta hiztegia](README.md): unitateak, jatorria eta mugak |
| Noiz sortu ziren laginak? | [SMB behaketa gordea](../requisitos/evidencias/CG02_fechas_2026-10-16.json) eta [lau snapshot](../requisitos/evidencias/muestras/) |
| Nola egiaztatu berriz? | `scripts/audit_cg02.py` eta `tests/test_audit_cg02.py`, Python 3.11+ estandarrarekin |

SMBren sarbidea lehenago egiaztatu zen; berrikuspen hau **offline** da. Ez da baieztatzen zerbitzaria une honetan piztuta edo helbide berean dagoenik.

## Nola errepikatu

Biltegiaren erroan:

```bash
python3 -S -m scripts.audit_cg02 --check
python3 -S -m unittest discover -s tests -v
```

`-S` aukerak site-packages kargatzea saihesten du: auditoriak ez du pandas, scikit-learn edo SMB kredentzialik behar. `--check` aukerak gordetako emaitza berriz kalkulatzen du. Ez erabili `--write` desberdintasun bat estaltzeko: iturria zergatik aldatu den berrikusi lehenik. Auditoreak ez ditu etiketa edo jatorrizko fitxategiak konpontzen.

## Berrikuspen lokalaren emaitza

- Inbentarioaren egiaztapena: zuzena.
- 16 unitate-proba: gaindituta (6 CG02 eta 10 lehendik zeuden Project sinkronizaziokoak).
- Training: 8.000 lerro; 271 positibo (%3,3875), timestamparik gabe.
- Trainingean 7 positibo azpifallo aktiborik gabe eta 14 negatibo azpifallo aktiboarekin. Desadostasunak erregistratzen dira, ez dira automatikoki OR bidez berriz etiketatzen.
- Lau batch gordetan: 40 lerro, denak etiketa negatiboarekin, 23 makina-ID.
- Makina/une bereko sentsore-egoera desberdinen 5 talde: ez dira lerro berdinak eta ez da zuzena automatikoki bikote horren arabera ezabatzea.
- 30 sentsore/etiketa firma desberdin eta 10 errepikapen. Trainingarekin ez dago firma zehatz berdinik lagin honetan; horrek ez du independentzia estatistikoa frogatzen.

Ez dira 124 fitxategien lerro guztiak aztertu, baizik eta gordetako lau snapshotak. Ez ondorioztatu 40 lerro negatiboetatik benetako falloen recall edo F1/F2.

## Errubrikarekiko ekarpena

| Irizpidea | CG02k ematen duena | Oraindik frogatzen ez duena |
|---|---|---|
| G36 — datuen azterketa | Inbentarioa, banaketak, faltanteak, etiketen desadostasunak eta unitateak | CG06/CG07ko EDA eta features azterketa osoa |
| G66 — eskemaren koherentzia | Training/batch zutabe eta rolak, denbora eta identitatearen mugak | CG03/CG18ko kontratu operatiboa eta Elasticsearch integrazioa |
| G95 — kalitate probatua | Fixture bidez faltanteak, NaN, bikoiztuak, goiburu okerra eta data baliogabeak probatuta | CG14/CG21eko NiFi bazterketa eta online inferentzian duen benetako eragina |

Irizpide bakoitza hainbat issueren bidez osatzen da. CG02 ixteak ez ditu G36/G66/G95 osoak automatikoki betetzen.

## Taldeak onartu behar duen erabakia

**Uneko egoeraren sailkapena laborategian ebalua daiteke. Hurrengo 24 orduetako matxuraren aurreikuspena ez dago balioztatuta.** Trainingak ez du datarik; batcharen timestampak simulazioaren emisioa adierazten du, ez egiaztatutako jarraipen fisikoa. Ez dago mantentze/averia hasieren erregistro independente eta dataturik edo makina bakoitzaren horizonte osoaren jarraipenik.

Gehiago gordetzeak analisia ahalbidetuko du, baina ez du berez identitate egonkorra edo etorkizuneko etiketa zuzena sortzen. Ez dugu datarik edo emaitzarik asmatuko baldintza horiek betetzeko.

## Onarpen independentea

Beste kide batek komandoak exekutatu, txostena irakurri eta ondorioa onartu behar du. PR #33n jaso: berrikuslea, data, erabilitako commit-a, komandoak, emaitza eta onartutako mugak. Horren ondoren prestatu mergea eta eguneratu issuearen egoera; ez da CG02 automatikoki ixten.
