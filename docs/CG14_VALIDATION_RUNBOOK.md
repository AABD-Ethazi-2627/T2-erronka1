# CG14 — trazabilidad y ejecución local

## Artefactos

- `cg14_validation/validator.py`: validador de referencia, no servicio de
  producción.
- `cg14_validation/resilience.py`: clasificación permanente/transitorio,
  backoff acotado, configuración Kafka desde entorno y redacción de secretos.
- `cg14_validation/metrics.py`: contadores thread-safe (recibidos/válidos/
  rechazados por código/avisos/fallos de publicación/reintentos) y latencia
  de validación; NiFi refleja estos contadores en provenance.
- `tests/fixtures/cg14/`: entradas sintéticas aisladas del CSV histórico.
- `tests/test_cg14_validation.py`: pruebas de contrato y casos límite.
- `tests/test_cg14_regression.py`: regresiones de defectos reales hallados en
  auditoría (pérdida de telemetría, tipos no textuales, sobredimensión).
- `tests/test_cg14_hardening.py`: seguridad, integridad y resiliencia.
- `tests/test_cg14_metrics.py`: observabilidad con datos reales, sin mocks.
- `tests/test_cg14_nifi_flow.py`: blindaje estructural del flujo NiFi.
- `nifi-flows/cg14_validate.groovy` + `cg14_validation_flow_v0.1.0.json`:
  flujo versionable (generado, no desplegado).
- `scripts/build_cg14_nifi_flow.py`: regenera el JSON desde el `.groovy`.
- `docs/CG14_VALIDATION_CONTRACT.md`: reglas, estados PENDIENTES y diseño NiFi.
- `docs/CG14_SECURITY_CHECKLIST.md`: checklist reutilizable (CG15–CG18).

## Comandos reproducibles

Desde la raíz del repositorio, con el entorno local:

```bash
source .venv/bin/activate
python -m pytest -q tests/test_cg14_validation.py tests/test_cg14_regression.py tests/test_cg14_hardening.py tests/test_cg14_metrics.py tests/test_cg14_nifi_flow.py
python -m pytest -q
python -m pytest -q --cov=cg14_validation --cov-report=term-missing --cov-branch tests/test_cg14_validation.py tests/test_cg14_regression.py tests/test_cg14_hardening.py tests/test_cg14_metrics.py
ruff check cg14_validation tests/ scripts/build_cg14_nifi_flow.py
ruff format --check cg14_validation tests/
python -m mypy cg14_validation scripts/build_cg14_nifi_flow.py
python -m pip check
git diff --check
```

Regenerar el flujo NiFi tras editar `nifi-flows/cg14_validate.groovy`:

```bash
python scripts/build_cg14_nifi_flow.py
python -m pytest -q tests/test_cg14_nifi_flow.py
```

Auditorías puntuales (dependencias de desarrollo, ya instaladas en `.venv`):

```bash
python -m pip_audit          # solo informa; no actualiza deps de otros módulos sin autorización
python -m bandit -r cg14_validation -q
```

El validador no necesita Kafka, NiFi, Docker, credenciales ni acceso a red.
Estas pruebas no demuestran que los servicios de infraestructura estén
operativos; esa evidencia requiere una prueba de integración posterior, una
vez aprobados CG03 y CG13.
