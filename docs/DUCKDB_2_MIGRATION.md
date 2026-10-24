# DuckDB 2.0.0: entorno y conversión temporal

El entorno activo fija `duckdb==2.0.0` en `pyproject.toml` y `uv.lock`, con
Python `>=3.11,<3.13`. pandas, NumPy, PyArrow, FastAPI, Starlette y el wheel local
Kafka conservan sus versiones. La migración no introduce servidores, Quack,
VARIANT, triggers, cambios del ledger SQLite ni del esquema Elasticsearch.

## Instalación y comprobación

Usar uv 0.13.1 desde la raíz del clon. Mantener el entorno anterior intacto y
elegir una ruta nueva absoluta para `UV_PROJECT_ENVIRONMENT`:

```bash
UV_PROJECT_ENVIRONMENT=/ruta/nueva/venv uv sync --frozen --python 3.11 --extra kafka --no-build
uv lock --check
/ruta/nueva/venv/bin/python -m unittest discover -s tests -p 'test_duckdb_output.py' -v
/ruta/nueva/venv/bin/python -m unittest discover -s tests -p 'test_columnar_upgrade_contract.py' -v
/ruta/nueva/venv/bin/python tests/run_strict_resources.py
```

Repetir con 3.12. En PowerShell asignar `$env:UV_PROJECT_ENVIRONMENT` y usar
`<venv>/Scripts/python.exe`. El lock fija URL y SHA-256; `--no-build` exige
wheels y evita compilar fuentes. Los cuatro wheels DuckDB Windows/Linux
3.11/3.12 se contrastan también con los hashes oficiales de PyPI.

La suite global incluye caminos heredados que requieren fcntl, fsync de
directorios y permisos POSIX. Se valida completa en Linux con temporales en
un filesystem que respete chmod; no pasa completa en Windows. Las pruebas
DuckDB/Parquet de esta migración sí se ejecutan en Windows 3.11 y 3.12. No
confundir esa compatibilidad focal con portabilidad de toda la aplicación.

## SQL, pandas y Arrow

Las lecturas `read_parquet(?)`, los parámetros, globs y consultas agregadas se
mantienen. `execute(...).fetchone()` sigue siendo el camino de los conteos.
Para resultados temporales se usa una relación `con.sql(query, params=[...])`,
seguida de `scripts.duckdb_output.to_pandas_utc`. El helper consume `to_arrow_table()` y
convierte únicamente columnas Arrow timestamp con zona a UTC, conservando su
unidad, enteros de época y NULL. No atribuye una zona a timestamps naive.
Gold y el agregado del notebook no proyectan timestamps: mantienen `.df()`
sobre la relación para conservar la conversión establecida de sum(HUGEINT) a
float64. Arrow representa ese agregado como Decimal; usarlo en Gold cambiaría
el dtype y provocaría una reescritura injustificada. El helper temporal sigue
las conversiones Arrow para las columnas restantes, incluidos los Decimal.

DuckDB 2.0 reconoce Parquet UTC/ns como `TIMESTAMPTZ_NS`. En los wheels probados,
`.df()` conserva sus valores ns pero pierde la anotación de zona; la salida de
Arrow sí conserva ambos. No se aplica `tz_localize` a valores de procedencia
desconocida ni se convierte a microsegundos. Un `TIMESTAMPTZ` de microsegundos
mantiene esa unidad: no se inventa precisión. Los contratos cubren UTC, offsets,
ambos cambios DST de Madrid, otra zona de sesión, instantes anteriores a 1970,
nanosegundos, NaT/NULL, resultados vacíos y agregados count/sum/avg.

Los scripts de historial usan conexiones en memoria. Gold continúa escribiéndose
con pandas/PyArrow; un replay idéntico conserva los bytes existentes. No se
regenera `historical/`, modelos, pickles, ZIP ni conjuntos de entrega para
justificar el cambio. Las sondas usan copias y fixtures inertes en temporales.
Los notebooks documentan el entorno nuevo; las salidas EDA guardadas son
**legacy**, no una ejecución con 2.0.0. El TEMPLATE no entrena la entrega ni
evalúa el test final. Los informes fechados de versiones anteriores siguen
siendo evidencia histórica inmutable.

## Integridad y rollback

Antes de aceptar un histórico, ejecutar `scripts.verify_history.verify` sobre
una copia. `retain` rechaza un manifiesto/archivo inconsistente; no cambiar los
hashes para aceptar corrupción. Los hashes CG25 actuales se actualizan solo
para fuentes modificadas deliberadamente; `historical_snapshot`, el pin base y
la revisión humana pendiente se conservan.

Para volver a 1.2.2, usar un checkout separado del commit previo a la migración
y un venv nuevo con su lock frozen; conservar el checkout/venv 2.0 para poder
comparar. Verificar los hashes de Parquet y manifiestos y probar la relectura
en copias antes de reutilizarlos. El motor 1.2.2 pierde precisión sub-us al
consultar timestamps UTC/ns; los bytes originales Parquet deben conservarse.
No rebaselinar ni reescribir Gold para que el rollback pase.

No abrir una base DuckDB persistente 2.0 con un motor antiguo: las sondas previas
verificaron rechazo por 1.2.2. La documentación habla de storage 69 mientras el
wheel verificado informó 999; la discrepancia sigue sin causa determinada.
Este flujo no migra bases DuckDB persistentes. Si se añaden después, necesitarán
backup y un ensayo de exportación/restauración específico; no hay garantía de
downgrade por cambiar el pin.

## Fuentes primarias

- [Anuncio 2.0.0](https://duckdb.org/2026/10/21/announcing-duckdb-200).
- [Migración Python](https://duckdb.org/docs/2.0/clients/python/migration).
- [Tipos timestamp](https://duckdb.org/docs/2.0/sql/data_types/timestamp).
- [Parquet](https://duckdb.org/docs/2.0/data/parquet/overview).
- [Migración general](https://duckdb.org/docs/2.0/operations_manual/migration).
- [Metadatos PyPI](https://pypi.org/pypi/duckdb/2.0.0/json).
