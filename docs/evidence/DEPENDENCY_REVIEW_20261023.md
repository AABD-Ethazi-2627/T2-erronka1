# Evaluación completa de dependencias — B-taldea, 23/10/2026

Alcance: solo `AABD-Ethazi-2627/T2-erronka1`, base `41cb66f0`. Se revisaron las **58 entradas originales** (56 PyPI, una wheel local y el proyecto virtual), sin omitir dev, research ni marcadores. La tabla añade después la nueva dependencia de FastAPI. “Actual” significa release estable publicada consultada hoy, no prueba de que sea universalmente la mejor.

## Decisión y evidencia

Actualizar API/HTTP/JSON Schema/figuras y mantener la base numérica probada. La ausencia de avisos no sustituye los contratos ni demuestra ausencia de vulnerabilidades. La consulta seleccionada cubre 58 filas del lock y uv adicional: **59 resultados para uv.lock + uv, 0 errores y 0 grupos de avisos activos**. Tras integrar main se añaden 31 pins del entorno separado del estudio: **90 resultados en total**, también sin errores/avisos activos. El requisito Python del artefacto local (>=3.9) se lee de su METADATA y se separa del upstream (>=3.8). La wheel conserva una limitación explícita: la consulta se hace a su versión upstream y sus cambios locales requieren revisión/tests. [Resultado reproducible](DEPENDENCY_REFRESH_20261023/selected-lock-audit.json).

La prueba RF prefijada usó exclusivamente las 5600 filas train y los mismos tres folds, sin ajustar hiperparámetros ni consultar validación/test. La candidata NumPy 2.4.6 + pandas 3.1 + scikit-learn 1.9.1 dio **scores OOF idénticos byte a byte** (AP 0.9020038074). No demuestra que otras funciones/modelos nuevos carezcan de valor. Cambió el esquema Parquet; dos subtests fallaron por el repr de escalares NumPy, no por corrupción numérica demostrada. PyArrow 26 aislado requiere NumPy 2. Los tiempos de una sola ejecución no son un benchmark fiable y no fundamentan capacidad HTTP. [Método, hashes y resultados](DEPENDENCY_REFRESH_20261023/scientific-comparison.json).

No se reemplazó un bundle servido, no se añadió dataset y no se habilitó ETA/RUL/forecast. Se conservan los seis inputs y AI4I current-state.

## Todas las entradas originales

Para las filas sin release nueva: no existe un candidato más reciente que comparar hoy; se conserva la versión compatible resuelta, por la función indicada. No se afirma optimalidad global. Todas las versiones PyPI originales tuvieron 0 avisos en la consulta de auditoría inicial; la consulta del nuevo lock se conserva enlazada arriba. Python del proyecto: >=3.11,<3.13.

| Paquete | Original | Última consultada | Selección | Python de última / selección | Evaluación de beneficio, compatibilidad y riesgo |
|---|---|---|---|---|---|
| [annotated-doc](https://pypi.org/project/annotated-doc/) | 0.0.5 | 0.0.5 | 0.0.5 | >=3.9 / >=3.9 | Conservar actual: documentación de parámetros FastAPI. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [annotated-types](https://pypi.org/project/annotated-types/) | 0.8.0 | 0.8.0 | 0.8.0 | >=3.10 / >=3.10 | Conservar actual: restricciones de tipos Pydantic. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [anyio](https://pypi.org/project/anyio/) | 4.15.1 | 4.15.1 | 4.15.1 | >=3.10 / >=3.10 | Conservar actual: concurrencia ASGI/HTTP. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [attrs](https://pypi.org/project/attrs/) | 26.1.0 | 26.1.0 | 26.1.0 | >=3.9 / >=3.9 | Conservar actual: modelos de referencias JSON Schema. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [catboost](https://pypi.org/project/catboost/) | 1.2.10 | 1.2.10 | 1.2.10 | no declarado / no declarado | Conservar actual: alternativa de investigación, fuera del runtime. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [certifi](https://pypi.org/project/certifi/) | 2026.10.19 | 2026.10.19 | 2026.10.19 | >=3.7 / >=3.7 | Conservar actual: raíces CA para clientes HTTP. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [click](https://pypi.org/project/click/) | 8.5.0 | 8.5.0 | 8.5.0 | >=3.10 / >=3.10 | Conservar actual: CLI de Uvicorn. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [cnc-guard-offline](../../pyproject.toml) | 0.1.0 | interna | 0.1.0 | >=3.11,<3.13 / >=3.11,<3.13 | Retener versión interna 0.1.0: proyecto virtual, no paquete descargado ni candidato PyPI. Se prueba el código de esta rama. |
| [colorama](https://pypi.org/project/colorama/) | 0.4.6 | 0.4.6 | 0.4.6 | !=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*,!=3.6.*,>=2.7 / !=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*,!=3.6.*,>=2.7 | Conservar actual: color de consola en Windows; se audita aunque Linux no lo instale. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [contourpy](https://pypi.org/project/contourpy/) | 1.3.3 | 1.4.0 | 1.3.3 | >=3.12 / >=3.11 | Retener: 1.4 exige Python >=3.12. 1.3.3 mantiene la misma resolución en 3.11/3.12; Matplotlib 3.11 funciona con ella. |
| [cycler](https://pypi.org/project/cycler/) | 0.12.1 | 0.12.1 | 0.12.1 | >=3.8 / >=3.8 | Conservar actual: ciclos de estilo de figuras. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [duckdb](https://pypi.org/project/duckdb/) | 2.0.0 | 2.0.0 | 2.0.0 | >=3.11.0 / >=3.11.0 | Conservar actual: consulta y verificación del archivo columnar. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [fastapi](https://pypi.org/project/fastapi/) | 0.133.0 | 0.161.1 | 0.161.1 | >=3.10 / >=3.10 | Actualizar: correcciones de validación/aliases y semántica documentada de JSON null/omitido. Los contratos reales pasan; no se atribuye una mejora de ML ni una CVE inexistente. |
| [fonttools](https://pypi.org/project/fonttools/) | 4.67.0 | 4.67.0 | 4.67.0 | >=3.11 / >=3.11 | Conservar actual: fuentes de Matplotlib. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [graphviz](https://pypi.org/project/graphviz/) | 0.21 | 0.21 | 0.21 | >=3.9 / >=3.9 | Conservar actual: visualización del extra CatBoost. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [h11](https://pypi.org/project/h11/) | 0.16.0 | 0.16.0 | 0.16.0 | >=3.8 / >=3.8 | Conservar actual: protocolo HTTP/1.1. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [httpcore](https://pypi.org/project/httpcore/) | 1.0.9 | 1.0.9 | 1.0.9 | >=3.8 / >=3.8 | Conservar actual: transporte de HTTPX. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [httpcore2](https://pypi.org/project/httpcore2/) | 2.12.0 | 2.16.0 | 2.16.0 | >=3.11 / >=3.11 | Actualizar con httpx2; resolución compatible del transporte de pruebas, fuera del runtime. |
| [httpx](https://pypi.org/project/httpx/) | 0.27.0 | 0.28.1 | 0.28.1 | >=3.8 / >=3.8 | Actualizar: mantenimiento del transporte y API de cliente. La eliminación de app/proxies en 0.28 requiere revisar llamadas; el repositorio usa el transporte explícito y sus contratos pasan. |
| [httpx2](https://pypi.org/project/httpx2/) | 2.12.0 | 2.16.0 | 2.16.0 | >=3.11 / >=3.11 | Actualizar el cliente de desarrollo a su release actual; mantener httpcore2 sincronizado. No entra en serving. |
| [httpx2-jsfetch](https://pypi.org/project/httpx2-jsfetch/) | 1.0 | 1.0 | 1.0 | >=3.12 / >=3.12 | Conservar actual: adaptador de plataforma del cliente de desarrollo; también cubierto. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [idna](https://pypi.org/project/idna/) | 3.20 | 3.20 | 3.20 | >=3.9 / >=3.9 | Conservar actual: normalización de dominios HTTP. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [imbalanced-learn](https://pypi.org/project/imbalanced-learn/) | 0.12.4 | 0.14.2 | 0.12.4 | >=3.10 / no instalado | Retener: 0.14.2 adapta compatibilidad a scikit-learn 1.9; la base 0.12.4 es la pareja probada con 1.5. No se probó una mejora de SMOTENC atribuible al cambio. |
| [iniconfig](https://pypi.org/project/iniconfig/) | 2.3.1 | 2.3.1 | 2.3.1 | >=3.10 / >=3.10 | Conservar actual: configuración de pytest. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [joblib](https://pypi.org/project/joblib/) | 1.5.3 | 1.6.0 | 1.5.3 | >=3.10 / >=3.9 | Retener: 1.6 corrige caché de funciones en notebooks e incorpora cloudpickle; ese uso no existe en serving. No justifica cambiar la pareja de persistencia probada. |
| [jsonschema](https://pypi.org/project/jsonschema/) | 4.23.0 | 4.26.0 | 4.26.0 | >=3.10 / >=3.10 | Actualizar: mantenimiento de validadores/referencias; contratos JSON y rechazos de etiquetas inválidas verificados. |
| [jsonschema-specifications](https://pypi.org/project/jsonschema-specifications/) | 2025.9.1 | 2025.9.1 | 2025.9.1 | >=3.9 / >=3.9 | Conservar actual: metaschemas oficiales JSON Schema. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [kafka-python](https://pypi.org/project/kafka-python/) | 3.0.11+cncguard.2 | 3.0.11 | 3.0.11+cncguard.2 | >=3.8 / >=3.9 | Retener wheel local .2: upstream 3.0.11 sigue actual. Sus parches de importlib.resources y client_software_version son necesarios para el protocolo. Hash/procedencia y regresiones específicos; el feed solo cubre upstream. |
| [kiwisolver](https://pypi.org/project/kiwisolver/) | 1.5.1 | 1.5.1 | 1.5.1 | >=3.10 / >=3.10 | Conservar actual: restricciones de layout de figuras. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [matplotlib](https://pypi.org/project/matplotlib/) | 3.10.1 | 3.11.2 | 3.11.2 | >=3.11 / >=3.11 | Actualizar: mantenimiento de renderizado, fuentes/PDF y eliminación de los warnings anteriores de pyparsing. Las figuras futuras pueden cambiar; no reescribir evidencias históricas. |
| [narwhals](https://pypi.org/project/narwhals/) | 2.27.1 | 2.27.1 | 2.27.1 | >=3.10 / >=3.10 | Conservar actual: compatibilidad de dataframes de Plotly. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [numpy](https://pypi.org/project/numpy/) | 1.26.4 | 2.5.4 | 1.26.4 | >=3.12 / >=3.9 | Retener: 2.5.4 exige Python 3.12. Se probó 2.4.6 en 3.11; mismos scores OOF, cambios ABI y dos asserts de repr incompatibles. No se demostró beneficio considerable en este flujo. |
| [packaging](https://pypi.org/project/packaging/) | 26.3 | 26.3 | 26.3 | >=3.9 / >=3.9 | Conservar actual: comparación de versiones y tags. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [pandas](https://pypi.org/project/pandas/) | 2.2.2 | 3.1.0 | 2.2.2 | >=3.11 / >=3.9 | Retener: 3.1 aporta cambios de strings y mejoras de lectura, pero aquí cambia el esquema persistido Arrow a large_string. Misma predicción RF; migración de datos separada. |
| [pillow](https://pypi.org/project/pillow/) | 13.0.0 | 13.0.0 | 13.0.0 | >=3.11 / >=3.11 | Conservar actual: imágenes de Matplotlib. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [plotly](https://pypi.org/project/plotly/) | 7.1.0 | 7.1.0 | 7.1.0 | >=3.8 / >=3.8 | Conservar actual: figuras del extra CatBoost. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [pluggy](https://pypi.org/project/pluggy/) | 1.7.0 | 1.7.0 | 1.7.0 | >=3.10 / >=3.10 | Conservar actual: plugins de pytest. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [pyarrow](https://pypi.org/project/pyarrow/) | 23.0.1 | 26.0.0 | 23.0.1 | >=3.11 / >=3.10 | Retener: 26 trae mantenimiento/funcionalidad columnar, pero su import exige NumPy >=2 incluso cuando los metadatos no lo anticipan. Import aislado con 1.26 falla; necesita migración conjunta. |
| [pydantic](https://pypi.org/project/pydantic/) | 2.14.1 | 2.14.1 | 2.14.1 | >=3.10 / >=3.10 | Conservar actual: validación del contrato API. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [pydantic-core](https://pypi.org/project/pydantic-core/) | 2.50.1 | 2.50.1 | 2.50.1 | >=3.10 / >=3.10 | Conservar actual: motor binario de Pydantic; mantener pareja compatible. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [pygments](https://pypi.org/project/pygments/) | 2.21.0 | 2.21.0 | 2.21.0 | >=3.9 / >=3.9 | Conservar actual: presentación de errores de pytest. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [pyparsing](https://pypi.org/project/pyparsing/) | 3.3.3 | 3.3.3 | 3.3.3 | >=3.9 / >=3.9 | Conservar actual: análisis de expresiones de Matplotlib. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [pytest](https://pypi.org/project/pytest/) | 9.1.1 | 9.1.1 | 9.1.1 | >=3.10 / >=3.10 | Conservar actual: ejecutor de pruebas. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [python-dateutil](https://pypi.org/project/python-dateutil/) | 2.9.0.post0 | 3.0.0 | 2.9.0.post0 | !=3.0.*,!=3.1.*,!=3.2.*,>=2.7 / !=3.0.*,!=3.1.*,!=3.2.*,>=2.7 | Retener: 3 cambia tzfile/DST y añade tzdata. El contrato usa UTC canónico y no se demostró beneficio para esta carga; mantener con pandas 2. |
| [pytz](https://pypi.org/project/pytz/) | 2026.5 | 2026.5 | 2026.5 | no declarado / no declarado | Conservar actual: zonas horarias de pandas 2. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [referencing](https://pypi.org/project/referencing/) | 0.37.0 | 0.37.0 | 0.37.0 | >=3.10 / >=3.10 | Conservar actual: resolución de referencias JSON Schema. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [rpds-py](https://pypi.org/project/rpds-py/) | 2026.9.1 | 2026.9.1 | 2026.9.1 | >=3.11 / >=3.11 | Conservar actual: estructuras persistentes de referencing. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [scikit-learn](https://pypi.org/project/scikit-learn/) | 1.5.0 | 1.9.1 | 1.5.0 | >=3.11 / >=3.9 | Retener: 1.9.1 aporta funciones/optimizaciones generales, pero el RF prefijado produce scores idénticos. Persistencia entre versiones no está soportada; requiere nuevo bundle y validación separada. |
| [scipy](https://pypi.org/project/scipy/) | 1.17.1 | 1.18.1 | 1.17.1 | >=3.12 / >=3.11 | Retener: 1.18.1 exige Python >=3.12. La base 1.17.1 mantiene ambas versiones de Python; no se observó necesidad de cambiar los kernels numéricos. |
| [six](https://pypi.org/project/six/) | 1.17.0 | 1.17.0 | 1.17.0 | !=3.0.*,!=3.1.*,!=3.2.*,>=2.7 / !=3.0.*,!=3.1.*,!=3.2.*,>=2.7 | Conservar actual: compatibilidad de dateutil 2. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [sniffio](https://pypi.org/project/sniffio/) | 1.3.1 | 1.3.1 | retirado | >=3.7 / no instalado | Retirar: dejó de pertenecer a la clausura resuelta de AnyIO/HTTPX seleccionada. No conservar una dependencia huérfana; su versión original también se consultó. |
| [starlette](https://pypi.org/project/starlette/) | 1.7.0 | 1.9.0 | 1.9.0 | >=3.11 / >=3.11 | Actualizar con FastAPI: correcciones de URL/cabeceras y soporte del cliente de pruebas por streaming. Contratos ASGI y cierre de recursos verificados. |
| [threadpoolctl](https://pypi.org/project/threadpoolctl/) | 3.7.0 | 3.7.0 | 3.7.0 | >=3.9 / >=3.9 | Conservar actual: control de hilos BLAS/OpenMP. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [truststore](https://pypi.org/project/truststore/) | 0.10.5 | 0.10.5 | 0.10.5 | >=3.10 / >=3.10 | Conservar actual: raíces nativas del cliente de desarrollo. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [typing-extensions](https://pypi.org/project/typing-extensions/) | 4.16.0 | 4.16.0 | 4.16.0 | >=3.9 / >=3.9 | Conservar actual: tipos de Python compatibles con Pydantic. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [typing-inspection](https://pypi.org/project/typing-inspection/) | 0.4.4 | 0.4.4 | 0.4.4 | >=3.10 / >=3.10 | Conservar actual: introspección de tipos de Pydantic. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [tzdata](https://pypi.org/project/tzdata/) | 2026.5 | 2026.5 | 2026.5 | >=2 / >=2 | Conservar actual: base de zonas horarias en plataformas que la requieren. Sin release nueva ni aviso activo en el feed; compatible en la resolución congelada y en las suites 3.11/3.12. |
| [uvicorn](https://pypi.org/project/uvicorn/) | 0.30.1 | 0.54.0 | 0.54.0 | >=3.10 / >=3.10 | Actualizar: mantenimiento acumulado de protocolo y ejecución ASGI. El arranque de la imagen y predict/replay se verifican; no se afirma más capacidad. |

## Nueva entrada y tooling externo

- **opentelemetry-api 1.45.1**: última consultada, sin avisos activos; dependencia introducida por FastAPI >=0.161 (mínimo 1.44). Instrumentación API, no nuevo servicio ni exportador configurado. Compatible con ambas versiones de Python. [PyPI](https://pypi.org/project/opentelemetry-api/).
- **uv 0.13.1 → 0.13.5**: corregir el almacén de confianza afectado por GHSA-hq85-5cpj-mr62; el mínimo corregido es 0.13.4. Se usa 0.13.5 en CI y Docker. [Aviso oficial](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62), [release](https://github.com/astral-sh/uv/releases/tag/0.13.5).
- **checkout v7.0.1, setup-uv v10.3.2, upload-artifact v7.0.2 y trivy-action v0.36.0**: releases actuales consultadas, fijadas por SHA; los actions JavaScript usan Node 24 en runners hospedados Ubuntu 24.04. No se afirma que un SHA antiguo pruebe una vulnerabilidad. Trivy 0.76.1 se fija explícitamente, no su default anterior.

## Infraestructura y hallazgos restantes

Elastic 9.5.4 → 9.5.5 corrige CVE-2026-103008; se alinean Elasticsearch/Kibana/Filebeat por digest. Los avisos RCS 2.0 de Elasticsearch y Fleet de Kibana tienen condiciones adicionales cuya activación no se acreditó; no se presentan como exposición confirmada. [Aviso Elastic](https://discuss.elastic.co/t/elasticsearch-8-19-23-9-4-8-9-5-5-security-update-esa-2026-198/390872).

Kafka 3.7 pasa al mismo 4.3.1 oficial del entorno CG14. NiFi pasa de una imagen local sin receta ni versión verificable a la oficial 2.12.0. No se atribuye contenido exacto a la imagen local. El export 2.12 conserva scripts/conexiones, remapea propiedades reales y está deshabilitado. [Kafka](https://kafka.apache.org/community/downloads/), [NiFi y avisos](https://nifi.apache.org/documentation/security/).

La API consume únicamente el export runtime completo con hashes, wheel-only y base Python 3.11.17/Debian 13 fijada. Se aplican seis paquetes exactos desde snapshot Debian firmado y se retiran herramientas seed innecesarias. En la imagen construida no quedan avisos con parche publicado, ni avisos Python/Rust. **Persisten 44 hallazgos HIGH de paquetes Debian sin parche**, además de 58 MEDIUM, 61 LOW y 1 UNKNOWN; son hallazgos por paquete, no necesariamente CVE únicos ni explotabilidad confirmada. No se ocultan: [resumen completo por severidad](DEPENDENCY_REFRESH_20261023/api-image-scan.json). CI conserva el JSON sin filtrar y bloquea HIGH/CRITICAL con parche en la API.

Las imágenes oficiales de terceros se escanean completas y sus resultados se publican; una versión nueva de una biblioteca embebida no demuestra que exista un tag corregido y compatible del proveedor. Esos scans son informativos sobre vulnerabilidades (un error de scanner sí falla), sin ignores de CVE. La API construida sí tiene el gate de HIGH/CRITICAL corregibles. Revisar los artefactos antes de merge: CI verde por sí solo no es aceptación de esos riesgos.

La transición stateful queda preparada en un proyecto Compose nuevo; no se reutilizaron volúmenes previos. El template antiguo exige un perfil histórico explícito. [Procedimiento y límites](../DEPENDENCY_MIGRATION.md).

## Validaciones y límites

- Importación/validación real NiFi 2.12: 12 procesadores, 4 servicios, 20 conexiones; sin ejecutar flujo. [Resultado](DEPENDENCY_REFRESH_20261023/nifi-compatibility.json).
- Filebeat 9.5.5 → Kafka 4.3.1 real: 10 registros lab + 1 SMB, claves/mensajes y topics coinciden; fixtures separados por input. No acredita SMB real, ficheros diminutos ni ejecución NiFi. [Resultado](DEPENDENCY_REFRESH_20261023/filebeat-kafka-compatibility.json).
- API HTTP → Elasticsearch 9.5.5, retry/ledger y cierre: PASSED; modelo sintético del harness, sin NiFi/Kafka. [Resultado](DEPENDENCY_REFRESH_20261023/durable-es955.json).
- Suites y smoke de la imagen final se registran en el resumen de validación del mismo directorio; no equivalen a despliegue ni aceptación humana.

## Prevención y mantenimiento

Dependabot propone semanalmente actualizaciones de uv, Actions, Dockerfile y Compose. No fusiona ni despliega. Sus PR deben regenerar `scoring/requirements.txt` y sincronizar `deploy/images.json`: los checks rechazan divergencias. Los cambios científicos van agrupados y necesitan volver a medir esquema, bundle y datos; no hay ignores generales de actualizaciones de seguridad. Los paquetes Debian exactos/snapshot requieren revisión deliberada junto con los nuevos scans; Dependabot no los actualiza.

El auditor consulta metadatos públicos oficiales con timeout, tamaño y concurrencia acotados. Los fallos de red/formato, fuentes desconocidas o hashes locales inconsistentes fallan cerrados. Los avisos retirados siguen visibles sin bloquear. Los aliases se agrupan para evitar contar dos veces el mismo aviso.

## Fuentes de los candidatos evaluados

[FastAPI](https://fastapi.tiangolo.com/release-notes/), [Starlette](https://starlette.dev/release-notes/), [Uvicorn](https://github.com/Kludex/uvicorn/blob/main/docs/release-notes.md), [HTTPX](https://github.com/encode/httpx/blob/master/CHANGELOG.md), [JSON Schema](https://github.com/python-jsonschema/jsonschema/blob/main/CHANGELOG.rst), [Matplotlib](https://matplotlib.org/stable/release/prev_whats_new/whats_new_3.11.0.html), [pandas](https://pandas.pydata.org/pandas-docs/stable/whatsnew/v3.1.0.html), [scikit-learn](https://scikit-learn.org/stable/whats_new/v1.9.html), [persistencia sklearn](https://scikit-learn.org/stable/model_persistence.html), [imbalanced-learn](https://imbalanced-learn.org/stable/whats_new.html), [Joblib](https://joblib.readthedocs.io/en/latest/CHANGES.html), [Arrow 26](https://arrow.apache.org/release/26.0.0.html), [dateutil](https://raw.githubusercontent.com/dateutil/dateutil/master/NEWS). Las fichas PyPI de cada fila documentan la release/Requires-Python consultada.

## Scan de las ocho imágenes declaradas

Los ocho scans terminaron con exit 0 del scanner; el modo informe no usa un umbral de vulnerabilidades. **Todos los avisos siguientes siguen abiertos**, aunque existan parches para bibliotecas dentro de la imagen. No se aprobó su explotabilidad ni su riesgo. Son hallazgos por paquete/ocurrencia, no CVE únicos. [Detalle HIGH/CRITICAL, cuentas completas y hashes de los JSON originales](DEPENDENCY_REFRESH_20261023/external-image-scans.json).

| Imagen declarada | HIGH | CRITICAL | HIGH/CRITICAL con versión de biblioteca corregida |
|---|---:|---:|---:|
| kafka | 27 | 0 | 27 |
| nifi | 142 | 6 | 56 |
| elasticsearch | 28 | 1 | 19 |
| kibana | 53 | 5 | 37 |
| filebeat | 30 | 1 | 15 |
| python | 50 | 0 | 6 |
| mock-python | 4 | 0 | 4 |
| uv | 0 | 0 | 0 |

Las bases Python y uv son etapas de build: su filesystem completo no es el runtime final de la API. La API final tiene su scan separado y los parches Debian descritos arriba. El mock de CG14 conserva tooling de la imagen oficial; sus avisos también permanecen visibles. No sustituir JAR/NAR/bibliotecas embebidas sin build y pruebas de compatibilidad del proveedor. Kafka 4.3.1 y NiFi 2.12 siguen siendo las releases oficiales publicadas consultadas; esto no afirma que sus imágenes carezcan de CVE. Una migración operativa requiere resolver o aceptar expresamente estos riesgos fuera del PR de mantenimiento.

## Cierre de verificación local y revisión

Tras corregir los dos hallazgos de la revisión independiente: **639 passed, 3 skipped y 303 subtests passed en cada Python 3.11.16 y 3.12.14**. Los tres skips son las consultas CG19 que requieren un Elasticsearch desechable explícito; se ejecutaron después por separado contra 9.5.5 y pasaron las tres. No se verificó el render de Kibana. [Resumen y hashes de fuentes/logs](DEPENDENCY_REFRESH_20261023/validation.json), [CG19 real](DEPENDENCY_REFRESH_20261023/dashboard-es-compatibility.json).

La revisión detectó que el gate usaba una caché distinta del action. Se reprodujo el error, se fijó explícitamente la ruta y se probaron ambos comandos consecutivos con una base recién descargada: la imagen final pasa y una imagen anterior con parches pendientes se rechaza sin error de scanner. [Regresión real del gate](DEPENDENCY_REFRESH_20261023/image-gate-regression.json). También se corrigió la distinción Requires-Python de la rueda/upstream con una regresión RED→GREEN.

La revisión fresca cubrió `41cb66f..0e2a0fd`; el autor comprobó las correcciones y la evidencia añadida después con las suites y los JSON originales. La CI remota se observa en el PR; estas pruebas locales no son una ejecución de GitHub Actions.

## Integración de main y entorno de investigación separado

Antes de publicar entró el PR #90 (`5005ccd`), con el estudio de Kalista y un lock compilado independiente de **31 paquetes**. Se integró sin cambiar sus pins, modelos ni evidencias. Su workflow usaba uv 0.11.19: se actualiza también a 0.13.5 y Actions fijados actuales. El auditor periódico cubre ahora ambos manifiestos e identifica cada resultado por su origen.

La colección de pytest por defecto se limita a tests de aplicación: el estudio importa psutil y sus boosters desde su propio entorno. Se reprodujeron cinco errores de colección al mezclar entornos y se corrigió su separación. La investigación conserva su CI sintética explícita: **22 tests y 50/50 adaptadores smoke completos**, con datos sintéticos de 120 filas. No se repitió la selección AI4I ni se promovió un modelo.

Las versiones congeladas son la elección para **reproducir el estudio archivado**, no una afirmación de mejor calidad frente a releases posteriores. No hay avisos activos de PyPI para esos pins en esta consulta. Para promover candidatos nuevos se necesitan métricas comparables del procedimiento completo y un paquete nuevo; el benchmark RF del informe principal no evalúa todos estos boosters.

| Pin de investigación | Versión del estudio | Última consultada | Python de última | Decisión y riesgo |
|---|---|---|---|---|
| [catboost](https://pypi.org/project/catboost/) | 1.2.10 | 1.2.10 | no declarado | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [colorama](https://pypi.org/project/colorama/) | 0.4.6 | 0.4.6 | !=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*,!=3.6.*,>=2.7 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [contourpy](https://pypi.org/project/contourpy/) | 1.3.3 | 1.4.0 | >=3.12 | La última requiere Python >=3.12; conservar receta exacta del estudio, sin cambiar su entorno de figuras. |
| [cycler](https://pypi.org/project/cycler/) | 0.12.1 | 0.12.1 | >=3.8 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [fonttools](https://pypi.org/project/fonttools/) | 4.67.0 | 4.67.0 | >=3.11 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [graphviz](https://pypi.org/project/graphviz/) | 0.21 | 0.21 | >=3.9 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [iniconfig](https://pypi.org/project/iniconfig/) | 2.3.1 | 2.3.1 | >=3.10 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [interpret-core](https://pypi.org/project/interpret-core/) | 0.6.10 | 0.7.8 | no declarado | La rama nueva puede cambiar los EBM e interacciones; no se ha demostrado una mejora en estos folds. Requiere un estudio nuevo para sustituir los paquetes sellados. |
| [joblib](https://pypi.org/project/joblib/) | 1.5.3 | 1.6.0 | >=3.10 | La nueva mejora otros usos de caché; preservar serialización y versiones de los paquetes archivados. |
| [kiwisolver](https://pypi.org/project/kiwisolver/) | 1.5.1 | 1.5.1 | >=3.10 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [lightgbm](https://pypi.org/project/lightgbm/) | 4.6.0 | 4.7.0 | >=3.10 | Release nueva del booster; los scores/costes archivados pertenecen a 4.6. No se atribuye mejora de calidad sin volver a evaluar el procedimiento. |
| [matplotlib](https://pypi.org/project/matplotlib/) | 3.11.2 | 3.11.2 | >=3.11 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [narwhals](https://pypi.org/project/narwhals/) | 2.27.1 | 2.27.1 | >=3.10 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [numpy](https://pypi.org/project/numpy/) | 1.26.4 | 2.5.4 | >=3.12 | La última requiere Python >=3.12 y NumPy 2 cambia ABI/repr; una migración necesita nuevas evidencias del estudio. |
| [packaging](https://pypi.org/project/packaging/) | 26.3 | 26.3 | >=3.9 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [pandas](https://pypi.org/project/pandas/) | 2.2.2 | 3.1.0 | >=3.11 | La nueva cambia inferencia de strings/esquema; conservar artefactos y cálculos archivados. |
| [pillow](https://pypi.org/project/pillow/) | 13.0.0 | 13.0.0 | >=3.11 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [plotly](https://pypi.org/project/plotly/) | 7.1.0 | 7.1.0 | >=3.8 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [pluggy](https://pypi.org/project/pluggy/) | 1.7.0 | 1.7.0 | >=3.10 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [psutil](https://pypi.org/project/psutil/) | 7.1.0 | 7.2.2 | >=3.6 | Mantenimiento de métricas/plataformas; no hay mejora de precisión ML demostrada. Mantener el medidor de recursos con el que se selló la investigación. |
| [pygments](https://pypi.org/project/pygments/) | 2.21.0 | 2.21.0 | >=3.9 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [pyparsing](https://pypi.org/project/pyparsing/) | 3.3.3 | 3.3.3 | >=3.9 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [pytest](https://pypi.org/project/pytest/) | 9.1.1 | 9.1.1 | >=3.10 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [python-dateutil](https://pypi.org/project/python-dateutil/) | 3.0.0 | 3.0.0 | !=3.0.*,!=3.1.*,!=3.2.*,>=2.7 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [pytz](https://pypi.org/project/pytz/) | 2026.5 | 2026.5 | no declarado | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [scikit-learn](https://pypi.org/project/scikit-learn/) | 1.5.0 | 1.9.1 | >=3.11 | No cargar modelos persistidos con otra versión; mantener la receta sellada. |
| [scipy](https://pypi.org/project/scipy/) | 1.13.1 | 1.18.1 | >=3.12 | Conservar 1.13.1 para reproducir la investigación; la última exige >=3.12 y cambiar kernels requiere volver a medir sus modelos. |
| [six](https://pypi.org/project/six/) | 1.17.0 | 1.17.0 | !=3.0.*,!=3.1.*,!=3.2.*,>=2.7 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [threadpoolctl](https://pypi.org/project/threadpoolctl/) | 3.6.0 | 3.7.0 | >=3.9 | 3.7 es la selección actual de la aplicación; el estudio conserva 3.6 para su presupuesto/receta, sin beneficio de calidad medido. |
| [tzdata](https://pypi.org/project/tzdata/) | 2026.5 | 2026.5 | >=2 | Conservar versión actual publicada; compatible en el entorno separado y en sus regresiones sintéticas. |
| [xgboost](https://pypi.org/project/xgboost/) | 3.1.3 | 3.4.1 | >=3.12 | Release nueva del booster con cambios de implementación; los scores/costes y calibradores archivados pertenecen a 3.1.3. Cambiarla requiere nueva evaluación y paquete. |

Los requisitos de investigación siguen siendo el compilado del protocolo recibido; no se mezclan con el export hashed de serving. Su renovación o incorporación de hashes debe conservar las versiones/procedencia de los paquetes sellados y generar evidencia nueva, no reescribir la archivada. Referencias de candidatos: [XGBoost](https://xgboost.readthedocs.io/en/stable/changes/), [LightGBM](https://github.com/microsoft/LightGBM/releases), [InterpretML](https://github.com/interpretml/interpret/releases), [psutil](https://github.com/giampaolo/psutil/blob/master/HISTORY.rst).

Entre las mejoras verificadas en las notas oficiales, XGBoost 3.4 amplía vector-leaf/multi-output y cambia objetivos de regresión cuantílica/MAE; esas capacidades no acreditan por sí solas mejora en este clasificador binario. LightGBM 4.7 añade soporte CUDA 13/ROCm y mejoras de interoperabilidad Arrow, además de correcciones: son candidatos útiles para una nueva evaluación de hardware/compatibilidad, pero no justifican atribuirles los scores del estudio sellado de 4.6. [XGBoost 3.4/3.4.1](https://xgboost.readthedocs.io/en/stable/changes/v3.4.0.html), [LightGBM 4.7](https://github.com/lightgbm-org/LightGBM/releases/tag/v4.7.0).

Tras integrar `5005ccd`, la última ejecución local de aplicación da **640 passed, 3 skipped y 303 subtests passed por Python**. Se añade un test del parser de pins de investigación; sus 22 tests y 50 smoke tests sintéticos corren en el entorno separado. [Integración](DEPENDENCY_REFRESH_20261023/research-integration.json). InterpretML 0.7.8 mejora el tratamiento de datos según la disponibilidad de pandas y el soporte de notebooks; no demuestra por sí misma mejora de los EBM archivados. [Release](https://github.com/interpretml/interpret/releases/tag/v0.7.8).

## Última corrección de CI e intérprete

La primera CI remota falló con el Compose 2.38.2 preinstalado al renderizar CG14. Se fija explícitamente **Compose 5.6.1**, ya validado localmente, mediante `docker/setup-compose-action` v2.4.0 por SHA. La ejecución remota de `619ab67` pasó `lock`, ambas suites Python y `synthetic-research`. [Fallo y verificación remota](DEPENDENCY_REFRESH_20261023/ci-environment-regression.json).

Al contrastar el intérprete descargado por CI se corrigió también el pin inicial 3.11.16: **Python 3.11.17 es la revisión de seguridad vigente** y corrige problemas de ssl, tarfile, zipfile, IDNA y credenciales URL que no quedan cubiertos exhaustivamente por el inventario PyPI. El Dockerfile usa ahora su digest oficial verificado. [Release de seguridad](https://www.python.org/downloads/release/python-31117/), [referencia final](DEPENDENCY_REFRESH_20261023/python31117-reference.json).

Se reconstruyó y escaneó la API: los mismos 29 paquetes exactos del runtime, health/predict/replay/422 correctos y Python 3.11.17 real. No quedan hallazgos con parche publicado; persisten los mismos 44 HIGH Debian sin parche. [Smoke final](DEPENDENCY_REFRESH_20261023/api31117-smoke.json), [scan final de API y base](DEPENDENCY_REFRESH_20261023/python31117-image-scans.json). Los scans y pruebas previos con 3.11.16 permanecen como evidencia histórica, no describen la última base seleccionada.
