# Starlette TestClient y avisos de seguridad — 2026-10-21

Base: PR #51, `9786d7d1e4e7bc657ad4888d5a433e46b46bbab7`. Este
cambio actualiza solo las dependencias de la API y añade regresiones. Los
ensayos son locales en FedoraLinux-43, Python 3.11.15; no acreditan CI ni
la cadena distribuida.

## Rectificación de la revisión independiente R1

La afirmación anterior de «0 warnings escapados» en el head
`369208347a312f58b2f52fedf899660696ab9ff3` **no estaba acreditada**:
`unittest.discover()` importaba los módulos antes de `catch_warnings()` y
del filtro `always`. Se reprodujo con cuatro `ResourceWarning` reales de
AnyIO durante discovery: el runner original devolvió 0 y contó 0 avisos,
aunque los cuatro aparecieron en stderr al arrancar Python con `-W always`.

La corrección activa la captura antes de discovery y mantiene dentro la
ejecución y el `gc.collect(2)` final, incluso al salir por excepción.
El hook de unraisables cubre todo ese intervalo. Se ejecutan ambas pasadas
y se conserva el fallo de cualquiera de ellas en el código de salida.
Los diagnósticos incluyen categoría, archivo y línea. No se añadieron
supresiones ni se modificaron paquetes instalados o dependencias.

La regresión en `tests/test_strict_resources_runner.py` crea módulos en
directorios temporales y ejecuta el runner con el mismo intérprete en un
subproceso nuevo. Comprueba dos pares reales de streams AnyIO abandonados:
uno se finaliza durante el import de discovery y otro queda en un ciclo
para el GC final. El resultado debe contener cuatro `ResourceWarning` y
devolver **1**. También comprueba un caso limpio con dos pasadas, una
deprecación durante import y un finalizador que lanza una excepción.
El control diferencial sobre el runner original y el corregido confirma
respectivamente salida 0/avisos contados 0 y salida 1/avisos contados 4.

El runner corregido descubre además un aviso real en la suite:
`starlette/testclient.py:53`, `DeprecationWarning: The anyio.abc.BlockingPortal
alias is deprecated, use anyio.from_thread.BlockingPortal instead.`
El estricto devuelve **1**; esta revisión no acredita cero avisos.

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
- La deprecación de `BlockingPortal` es independiente de HTTPX2. Está
  confirmada en la [incidencia oficial de Starlette #3497](https://github.com/Kludex/starlette/issues/3497)
  y corregida por [#3498](https://github.com/Kludex/starlette/pull/3498), merge
  `bbee894422c6cc1306327335ae385b901ccfec13`. Las
  [notas de Starlette 1.7.0](https://starlette.dev/release-notes/#170-september-23-2026)
  incluyen ese arreglo junto con otros cambios de comportamiento. El
  [índice oficial de PyPI](https://pypi.org/pypi/starlette/json), consultado
  en esta revisión, solo publica `1.3.0` y `1.3.1` en la serie 1.3;
  `1.3.2` devuelve HTTP 404. La
  [API oficial de AnyIO](https://anyio.readthedocs.io/en/stable/api.html#anyio.from_thread.BlockingPortal)
  documenta `anyio.from_thread.BlockingPortal` como ubicación vigente.
  Se conserva el residuo: actualizar hasta 1.7.0 ampliaría el cambio;
  fijar una versión antigua de AnyIO solo evitaría el aviso sin corregir
  el import de Starlette. No se aplica un monkeypatch ni un filtro para
  fabricar una pasada limpia.

## Metadatos y hashes revalidados en R1

Se descargaron los sdist y wheels fijados, se calculó su SHA-256 y se
comparó tanto con `uv.lock` como con el metadato oficial de PyPI. Ninguno
está retirado (`yanked=false`). Las versiones instaladas coinciden.

| Paquete y fuente PyPI | SHA-256 sdist | SHA-256 wheel |
| --- | --- | --- |
| [Starlette 1.3.1](https://pypi.org/pypi/starlette/1.3.1/json) | `05d0213193f2fbaae60e2ecb593b4add4262ad4e46536b54abe36f11a71724e0` | `c7372aae11c3c3f26a42df7bd626cec2f47d03483d261d369516a615a53714c6` |
| [HTTPX2 2.12.0](https://pypi.org/pypi/httpx2/2.12.0/json), grupo `dev` | `7631fe9887a8a2275f4a2540e053aa670fcc50742864a9ae7c66e609fdcf12cf` | `cc8b6eecb8661c146b8f89a60e97456ee086e91a784ed31ac450c3a9e613dd36` |
| [AnyIO 4.15.1](https://pypi.org/pypi/anyio/4.15.1/json) | `9f28306018cbd6d329e64a36d58256edff76dd996fe423bc957326e578b82a94` | `6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101` |

Las respuestas oficiales de deps.dev para
[Starlette 1.3.1](https://api.deps.dev/v3/systems/pypi/packages/starlette/versions/1.3.1),
[HTTPX2 2.12.0](https://api.deps.dev/v3/systems/pypi/packages/httpx2/versions/2.12.0)
y [AnyIO 4.15.1](https://api.deps.dev/v3/systems/pypi/packages/anyio/versions/4.15.1)
contienen `advisoryKeys: []`. Esto describe esas versiones y esa fuente
en la fecha de consulta; no acredita ausencia global de vulnerabilidades
ni elimina el residuo de PyArrow del audit del lock.

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

R1 repitió esos contratos y añadió una regresión ASGI con JSON válido
fragmentado en bloques de 4096 bytes: el cuerpo total de 32768 bytes
devuelve 200 y el de 32769 devuelve 413. **El 422 para JSON sin
`Content-Type` es un cambio deliberado respecto a la base**: los clientes
deben enviar `Content-Type: application/json`. El export de NiFi ya lo
declara; esa compatibilidad se comprobó estáticamente y con ASGI local,
sin ejecutar el servicio NiFi.

## Validación local

| Comprobación | Resultado |
| --- | --- |
| `.venv/bin/python tests/run_strict_resources.py` | **Salida 1.** Dos pasadas: 117 pruebas, 3 omitidas, 0 fallos, 0 errores y 0 unraisables en cada una. Primera: 1 `DeprecationWarning`; segunda: 0 avisos porque el módulo ya está importado. El fallo de la primera se conserva. |
| `.venv/bin/python -m unittest discover -s tests -p test_strict_resources_runner.py -v` | 4 regresiones pasan; los controles negativos esperan y acreditan salida 1 del subproceso. |
| `.venv/bin/python -m unittest discover -s tests -p test_framework_upgrade_contract.py -v` | 3 pruebas pasan, incluidos los cuerpos fragmentados de 32768/32769 bytes. |
| `uvx --from uv==0.13.1 uv lock --check` | Pasa. |
| Resolución de `scoring/requirements.txt` con Python 3.11 | Pasó en la ronda anterior; no se repitió en R1 porque no se modificaron dependencias ni el lock. |
| `python -m scripts.audit_cg02 --check` y `python scripts/check_repository_layout.py` en el entorno fijado | Pasan. |
| Ruff 0.14.14 en los archivos Python añadidos o modificados; formato | Pasan. |
| `uvx --from uv==0.13.1 uv audit --locked` | Falla: `pyarrow 18.1.0`, `GHSA-rgxp-2hwp-jwgg` / `PYSEC-2026-113` / `CVE-2026-25087` (mismo problema; severidad alta según GHSA), corregido en `23.0.1`. |
| `ruff check .` | Falla por cuatro E402 en `notebooks/01_EDA_evidence.ipynb` y un E731 en `scripts/audit_cg02.py`; los archivos no cambiaron respecto a la base. |

Los tres tests omitidos requieren el bundle de modelo. No se generó un
bundle de entrega, no se ejecutó el conjunto final ni se activaron
infraestructura compartida o CI manual. El cambio de `pyarrow` y los cinco
hallazgos Ruff quedan fuera del alcance de esta revisión y siguen visibles.
El [advisory de PyArrow](https://github.com/advisories/GHSA-rgxp-2hwp-jwgg)
precisa que el fallo requiere pre-buffering en Arrow C++ y que esa función
no está expuesta en los bindings Python. Se conserva la severidad alta
del registro y el fallo del audit; no se afirma explotación de esta API
ni se suprime el hallazgo. Queda pendiente de otra tarea.

Durante la revalidación, un lanzador local resolvió por error el symlink
del intérprete del venv hacia Python base y produjo errores de import por
dependencias ausentes. Se corrigió el lanzador para invocar la ruta
absoluta `.venv/bin/python` sin resolverla y se repitieron los checks en
ese entorno. Esos errores no se contabilizan como validación del cambio.
