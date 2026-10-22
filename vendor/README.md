# Kafka: recursos de Python y compatibilidad de protocolo

`kafka_python-3.0.11+cncguard.2-py3-none-any.whl` es una distribución local
del wheel oficial `kafka-python==3.0.11`, bajo Apache-2.0. Conserva su licencia
en `*.dist-info/licenses/LICENSE`. No es una versión publicada por upstream.

El 2026-10-21, la [API oficial de PyPI](https://pypi.org/pypi/kafka-python/json)
indicaba 3.0.11 como última versión. La
[fuente oficial inspeccionada](https://github.com/dpkp/kafka-python/blob/cd3f7938e1c119fa1e78c333778767606c2a802f/kafka/protocol/schemas/load_json.py#L14)
seguía usando `importlib.resources.read_text`. En Python 3.11, el primer import
emite 218 DeprecationWarning; una segunda importación en el mismo proceso no
permite comprobar la reparación.

El parche sustituye esa llamada por
`importlib.resources.files(package).joinpath(msg_type + '.json').read_text(encoding='utf-8')`,
como recomienda la [documentación de Python 3.11](https://docs.python.org/3.11/library/importlib.resources.html#importlib.resources.read_text).
No cambia los 108 JSON de protocolo, su parser ni el comportamiento ante recursos
ausentes. Se marca el archivo modificado, se distingue la versión local en
`kafka/version.py` y METADATA, se renombra dist-info y se regenera RECORD.
El wheel declara Python >=3.9 porque `files()` se incorporó en esa versión;
el proyecto conserva su soporte >=3.11,<3.13 y valida ambas versiones.

La revisión local `.2` también transforma `+` en `-` en el valor predeterminado
`client_software_version` de conexión y gestor. La identidad del paquete sigue
siendo PEP 440 (`3.0.11+cncguard.2`); el protocolo envía
`3.0.11-cncguard.2`. Apache Kafka 3.7.2 rechaza el signo `+` en
[ApiVersionsRequest v3](https://github.com/apache/kafka/blob/3.7.2/clients/src/main/java/org/apache/kafka/common/requests/ApiVersionsRequest.java#L53).
El ensayo con broker real reprodujo `INVALID_REQUEST` (42) con `.1` y comprobó
bootstrap, producción, consumo y commits con `.2`. No cambia schemas ni parser.

## Instalación y reproducción

`uv sync --locked --extra kafka` instala el wheel versionado mediante una
[fuente path soportada por uv](https://docs.astral.sh/uv/concepts/projects/dependencies/#path).
`uv.lock` fija la ruta, versión y SHA256. No requiere un compilador, un fork
remoto ni una modificación de site-packages. La instalación con pip debe usar
explícitamente este archivo local; `pip install kafka-python==3.0.11` instala
el paquete upstream sin corregir. No usar `uv --no-sources` para este extra.

Para reconstruir, descargar únicamente el wheel oficial enlazado en
`kafka-python-provenance.json` y ejecutar desde la raíz del repositorio:

```sh
python3 scripts/repack_kafka.py /ruta/kafka_python-3.0.11-py3-none-any.whl \
  --output /tmp/kafka_python-3.0.11+cncguard.2-py3-none-any.whl
sha256sum /tmp/kafka_python-3.0.11+cncguard.2-py3-none-any.whl vendor/*.whl
```

El script sólo usa la biblioteca estándar y rechaza un wheel de origen con hash
distinto. ZIP sin compresión y metadatos fijos permiten reproducir sus bytes en
Python 3.11/3.12 y Windows/Linux. La adaptación sigue el
[formato wheel de PyPA](https://packaging.python.org/en/latest/specifications/binary-distribution-format/).
No se descarga nada durante la reconstrucción ni al importar Kafka.

## Mantenimiento y retirada

El parche pertenece al proyecto educativo CNC Guard. Al actualizar Kafka,
comprobar primero si una versión oficial corrige el lector. Si lo corrige,
retirar esta fuente, wheel y repacker, fijar la versión oficial y regenerar el
lock. En ambos casos ejecutar la regresión de import limpio, los tests del
adaptador, el lab de protocolo loopback y el runner estricto en 3.11 y 3.12.
La regresión vive en `tests/test_kafka_dependency.py` y no depende de que otros
tests hayan importado previamente Kafka. Mantener la trazabilidad del parche
al auditar: una versión local no acredita ausencia de vulnerabilidades upstream.

Para regenerar el lock tras cambiar el wheel local, usar
`uv lock --upgrade-package kafka-python --refresh-package kafka-python` y
comprobar que su hash coincide con el manifiesto. Una actualización posterior
del parche debe usar una versión local nueva; no reemplazar un artefacto ya
publicado manteniendo su versión.
