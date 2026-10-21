# Starlette TestClient y avisos de seguridad — 2026-10-21

Base: PR #51, `9786d7d1e4e7bc657ad4888d5a433e46b46bbab7`. Este
cambio actualiza solo las dependencias de la API y añade regresiones. Los
ensayos son locales en FedoraLinux-43, Python 3.11.15; no acreditan CI ni
la cadena distribuida.

## Selección

- FastAPI `0.133.0` es la primera versión comprobada cuyo metadato permite
  Starlette 1.x; FastAPI `0.132.1` aún exige `<1.0.0`. Se probó también la
  propuesta `0.135.1` con Starlette `1.3.1`, pero la suite y los contratos
  pasan con `0.133.0`. [Metadatos de FastAPI 0.133.0](https://pypi.org/pypi/fastapi/0.133.0/json),
  [notas de versión](https://fastapi.tiangolo.com/release-notes/#01330).
- Starlette `1.3.1` es la primera versión que corrige las seis advisories
  registradas para `0.38.6`: `GHSA-82w8-qh3p-5jfq` (alta),
  `GHSA-wqp7-x3pw-xc5r` (alta), `GHSA-x746-7m8f-x49c` (media),
  `GHSA-86qp-5c8j-p5mr` (media), `GHSA-2c2j-9gv5-cj73` (media) y
  `GHSA-f96h-pmfr-66vw` (alta). También corrige
  `GHSA-jp82-jpqv-5vv3` (baja). El dato procede de los rangos y primeras
  versiones corregidas de cada [advisory oficial](https://github.com/Kludex/starlette/security/advisories)
  y de las [notas de Starlette](https://starlette.dev/release-notes/#131-june-12-2026).
- Starlette 1.3.1 emite una advertencia de deprecación al importar
  `TestClient` con HTTPX 0.27. El grupo `dev` instala HTTPX2 `2.12.0`, la
  primera versión que corrige sus tres advisories conocidas en 2.0.0. El
  cliente ASGI del proyecto sigue usando HTTPX 0.27.
- El lock actualiza `certifi` de `2026.10.18` a `2026.10.19`, que corrige
  `GHSA-6q48-6c7w-9gw2`. No se cambió `pyarrow==18.1.0`.

## Compatibilidad comprobada

`scoring/score_api.py` usa `lifespan` explícito y `FastAPI.middleware`;
no usa las APIs de Starlette retiradas en 1.0 (`on_event`,
`on_startup`/`on_shutdown`, decoradores de rutas o middleware de
`Starlette`). La búsqueda en la ruta API tampoco encontró `request.form()`,
`StaticFiles`, `FileResponse`, `HTTPEndpoint` ni decisiones basadas en
`request.url`. Esto limita la exposición observada de esta API, pero no
sustituye el parche ni demuestra seguridad global.

Con modelos sintéticos pequeños y el lifespan real, el transporte ASGI
devolvió `/health` 200 y `/predict` 200, validó la respuesta contra el
contrato JSON, devolvió 422 para entrada inválida o JSON sin
`Content-Type`, 413 para cuerpo excesivo, 500 ante un fallo de scoring
inyectado y 503 con manifiesto inválido. `/openapi.json` conservó la ruta,
el esquema `Telemetry`, `rpm` obligatorio y `additionalProperties: false`.
El export de NiFi declara `Request Content-Type: application/json`; no
se ejecutó NiFi. El `TestClient` cerró sus streams sin avisos; un control
negativo con streams dejados abiertos emitió dos `ResourceWarning` capturados.

## Validación local

| Comprobación | Resultado |
| --- | --- |
| `uv run --frozen --python 3.11 python tests/run_strict_resources.py` | Dos pasadas: 112 pruebas, 3 omitidas, 0 fallos, 0 errores, 0 warnings escapados, 0 unraisables cada una. |
| `uvx --from uv==0.13.1 uv lock --check` | Pasa. |
| Resolución de `scoring/requirements.txt` con Python 3.11 | Pasa. |
| `python -m scripts.audit_cg02 --check` y `python scripts/check_repository_layout.py` en el entorno fijado | Pasan. |
| Ruff 0.14.14 en los archivos Python añadidos o modificados; formato | Pasan. |
| `uv audit --locked` | Falla: `pyarrow 18.1.0`, `GHSA-rgxp-2hwp-jwgg` / `PYSEC-2026-113` (dos identificadores del mismo problema; severidad alta según GHSA), corregido en `23.0.1`. |
| `ruff check .` | Falla por cuatro E402 en `notebooks/01_EDA_evidence.ipynb` y un E731 en `scripts/audit_cg02.py`; los archivos no cambiaron respecto a la base. |

Los tres tests omitidos requieren el bundle de modelo. No se generó un
bundle de entrega, no se ejecutó el conjunto final ni se activaron
infraestructura compartida o CI manual. El cambio de `pyarrow` y los cinco
hallazgos Ruff quedan fuera del alcance de esta revisión y siguen visibles.
