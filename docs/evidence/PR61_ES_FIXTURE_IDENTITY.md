# PR61: identidad del fixture Elasticsearch por fuente

Validación local del 2026-10-21. Head original:
`674e8720deba2c4af0de414649309aa4f45569e0`. Base PR42:
`7983beef471dc2de2a9fd977f8596809dc7f665c`.
Composición local antes del ajuste:
`37cf9f0cfdd29371e05cd5a975c2aef1a0a40e60`.

El job 119415579294 del run 39655799837 falla en el segundo source del test
`test_real_api_response_and_exported_nifi_paths_preserve_contract`:
`source='smb_csv'`, `409 != 200`, `Event identity content conflict`.
Se reproduce ese mismo fallo antes del ajuste en Python 3.11.15 y 3.12.15.
El test cambia source manteniendo el event_id del ejemplo dentro de una misma
app. El ledger de PR61 rechaza correctamente ese cambio de contenido.

El único cambio funcional es asignar al fixture
`sha256(f"es-contract:{kind}:synthetic-row-1".encode()).hexdigest()`.
Cada fuente tiene una identidad distinta, estable y válida de 64 caracteres hex. Se conservan
todas las aserciones200, contrato, mapping, identidad y rutas NiFi. API, ledger
y `test_scoring_replay.py` permanecen idénticos al head original; la regresión
`test_same_id_different_valid_payload_conflicts_before_inference` sigue exigiendo
409 ante cambios de rpm, timestamp o source con el mismo ID.

Entorno: WSL `FedoraLinux-43`, OS real Fedora 44. Dos entornos aislados creados
con `uv sync --frozen --python <interpreter> --extra kafka`; Kafka 3.0.11.
La composición usa el workflow de PR42, incluido el extra Kafka y un bundle
presente antes de unittest. Para la validación local se copia exclusivamente el
bundle previo `synthetic-es-contract-test-only`, sin ejecutar los scripts de
entrenamiento ni empaquetado de entrega. Los pequeños fits sintéticos temporales
de los tests existentes se ejecutan normalmente.

Comandos por cada intérprete, desde la composición:

```text
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s tests -p test_elasticsearch_contract.py -v
python -B -m unittest discover -s tests -p test_scoring_replay.py -v
python -B -m scripts.audit_cg02 --check
```

Resultado por intérprete: suite de 237 tests, 0 fallos, 3 skips; ES 2 tests OK;
replay 11 tests OK; auditoría de fuentes OK. Los 3 skips son las consultas de dashboard que requieren
`Disposable CG19 ES`; no se levanta ningún servicio. No hay skips por bundle.

Ruff 0.17.1 global, E/F/I/PLW1510, formato de 210 archivos, diff completo desde
la base 7983 y delta desde 674, contratos, layout y lock: exit 0.
Auditoría de dependencias exportadas del lock con extra Kafka y hashes:
`pip-audit --require-hashes --disable-pip -r <export>` devuelve exit 0,
`No known vulnerabilities found`.

Hashes SHA256 del bundle antes y después, iguales en ambas versiones:

```text
manifest.json 63f9822fc179670c133c2771da2fb8d7a37b26418444215a1274461fbe5427a1
rf.pkl       6029cd3fc76d3d4e46ac27c8f172097d8f44aa496fe129674971015b29512877
if.pkl       ba2a0b74d6522c1daa18655a5d124d98346c82c9cb838a9d3d3b817a0c8c004b
```

Logs íntegros, argv y códigos de salida en el taskroot local
`D:/github/_local/t2-babysit-20261021/pr61-ci-fix`.
Estos resultados son locales: no acreditan CI automático del nuevo head ni
revisión independiente de este delta, ni ejecución de NiFi/ES/Kafka real.
