# CNC Guard · Memoria teknikoa euskaraz

[PDFa irakurri](MEMORIA_TEKNIKOA_EU.pdf) · [HTML bertsioa](MEMORIA_TEKNIKOA_EU.html) · [Markdown editagarria](MEMORIA_TEKNIKOA_EU.md)

2026-11-05ean prestatutako dokumentazio teknikoa: 17 kapitulu eta errubrikako 40 deskribatzaileren justifikazio banakatua. Kodea, datatutako emaitzak, hautaketa-arrazoiak eta mugak lotzen ditu. Ikerketa, zerbitzuan erabilitako eredua eta giza baliozkotzea bereizita daude.

Dokumentu berria da: aurreko memoria, ANEXO1/4, zigilu eta akta historikoak kontserbatzen dira. Taldeak euskarazko terminologia, edukia eta benetako ekarpenen esleipena berrikusi behar ditu entrega akademikoa egin aurretik. Ez da notarik edo onarpenik esleitzen.

## Fitxategiak

- `MEMORIA_TEKNIKOA_EU.md`: edukiaren iturri editagarria.
- `MEMORIA_TEKNIKOA_EU.html`: testu osoa, aurkibide nabigagarria eta bi irudi txertatuak; ez du sarerik behar irakurtzeko. Iturri-estekek checkout-eko fitxategietara jotzen dute.
- `MEMORIA_TEKNIKOA_EU.pdf`: orrialde zenbakidunak eta azal propioa; irakurtzeko eta partekatzeko.
- `ITURRIAK.json`: erreferentzien SHA-256 eta Git jarraipenaren egoera.
- `EGIAZTAPENA.json`: dokumentazioaren egiaztapen berriak eta haien mugak.
- `build_reading.mjs`: HTMLaren sortzaile lokala; `make-pdf` trebetasunaren `marked` mendekotasuna erabiltzen du.
- `verify_document.py`: 40 literalak, estekak, iturri-hashak eta hautatutako zenbakizko erreferentziak egiaztatzen ditu; ez du zerbitzurik abiarazten.

## Berreraikuntza lokala

Biltegiaren errotik:

```bash
python -B docs/memoria_teknikoa/verify_document.py
node docs/memoria_teknikoa/build_reading.mjs
node "$HOME/.agents/skills/make-pdf/bin/md2pdf.mjs" \
  --cover --title "CNC Guard: memoria teknikoa" --date "2026-11-05" \
  docs/memoria_teknikoa/MEMORIA_TEKNIKOA_EU.md \
  docs/memoria_teknikoa/MEMORIA_TEKNIKOA_EU.pdf
```

PDF sortzaileak Node, Chromium eta instalatutako `make-pdf` trebetasunaren mendekotasunak behar ditu. Ez du sareko baliabiderik erabiltzen. Iturriren bat aldatu bada, hasierako egiaztapenak gelditu egin behar du: aldaketaren eragina berrikusi manifestua eguneratu aurretik. PDFko kode-bideak tokiko erreferentziak dira; dokumentua bakarrik partekatzeak ez ditu jatorrizko kodea eta frogak barne hartzen.
