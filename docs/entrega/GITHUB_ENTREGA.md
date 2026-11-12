# GitHub bidezko entrega

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
