# CG14 — informe de calidad (local, sin publicar)

Rama: `feat/14-nifi-validation`. Fecha: 2026-10-16. Sin commit/push/PR/merge.
CSV original intacto (`data/ai4i2020_train.csv`: 8.000 filas, 271 fallos,
verificado por lectura directa).

## 1. Tests antes y después

- Antes (estado comunicado, verificado): 41 tests CG14 / 51 totales.
- Después: **80 tests CG14 / 90 totales. Aprobados 90, fallidos 0, omitidos 0.**
- Cobertura `cg14_validation`: **100 % líneas (287/287), 100 % ramas (116/116)**
  (`pytest-cov --cov-branch`).
- Rendimiento medido (Omarchy, Python 3.12, `.venv`): ~90.000 eventos/s en
  `parse_csv_event` (5000 validaciones en 0,06 s). Margen sobrado para el
  throughput del simulador antes de NiFi.

## 2. Bugs encontrados y corregidos

1. **Crítico — pérdida de telemetría en inferencia.** Una fila CSV con etiqueta
   activa se rechazaba entera: un fallo real nunca llegaba a scoring.
   Regresión: `tests/test_cg14_regression.py::test_inference_forwards_telemetry_when_labels_are_active`
   (creada en rojo, 3 fallos iniciales confirmados). Corrección: el adaptador
   CSV valida `0/1`, elimina las etiquetas del evento, conserva el original y
   emite aviso `TRAINING_LABEL_STRIPPED`. El JSON canónico con etiquetas sigue
   rechazado (`TRAINING_LABEL_IN_INFERENCE`).
2. **Excepción sin capturar con entrada no textual** (`None`, `bytes`, `int`)
   → `INVALID_TYPE`. Regresión dedicada.
3. **Sin presupuesto de tamaño** → `MESSAGE_TOO_LARGE` (`CG14_MAX_LINE_BYTES`
   8192, `CG14_MAX_FIELD_CHARS` 512, por entorno). Regresión dedicada.
4. **`IndexError` en `redact_for_log`** con patrón PEM sin grupos — detectado
   por test, corregido (ramas con/sin grupos).
5. **Código muerto**: constante `EVENT_FIELDS` sin uso — eliminada (G08).
6. **`retry_delays` sin cota**: un entero absurdo (`10**6`) asignaba ~8 MB.
   Tope `MAX_RETRY_ATTEMPTS=10` con `ValueError` (fail fast).
7. **`stable_event_id` silencioso ante basura**: `None`/`int`/`bytes` generaban
   un hash válido y ocultaban errores de programación. Ahora `TypeError`.
8. **Paridad Python↔Groovy**: el script no hacía `trim` en etiquetas ni UTF-8
   explícito al escribir (divergencia con `int()` y riesgo con no-ASCII).
   Corregido y fijado con test de paridad. Léxicos exóticos (`1_0`, floats
   hex) pueden diferir entre `float()` y `parseDouble`: fuera de alcance,
   el simulador emite decimales planos.

## 3. Seguridad (G02)

- `ruff check` PASS · `ruff format --check` PASS · `mypy` PASS ·
  `bandit -r cg14_validation` sin hallazgos · `pip check` PASS ·
  `git diff --check` PASS.
- Fuzzing propio (1000 entradas hostiles, semilla fija, fijado como test):
  0 excepciones.
- `pip-audit` informa vulnerabilidades en `starlette 0.37.2` (p. ej.
  PYSEC-2026-161/1941/1943/2280/2281): dependencia de scoring/CG28, ajena a
  CG14 (stdlib puro). No actualizada desde CG14; documentada como riesgo
  externo medio, pendiente de autorización del dueño del módulo.
- Sin secretos en código CG14; Kafka solo desde entorno con fallo rápido;
  redacción verificada con tests. Hallazgos críticos/altos en alcance CG14: 0.

## 4. Archivos creados o modificados (todo CG14, sin tracked tocados)

- `cg14_validation/validator.py` (warnings, límites, strip-con-aviso).
- `cg14_validation/resilience.py` (nuevo), `cg14_validation/metrics.py` (nuevo).
- `tests/test_cg14_validation.py`, `test_cg14_regression.py` (nuevo),
  `test_cg14_hardening.py` (nuevo), `test_cg14_metrics.py` (nuevo),
  `test_cg14_nifi_flow.py` (nuevo).
- `tests/fixtures/cg14/` (3 fixtures sintéticas).
- `nifi-flows/cg14_validate.groovy` (nuevo, fuente de verdad del script),
  `nifi-flows/cg14_validation_flow_v0.1.0.json` (nuevo, generado;
  `cnc_fase1_INCOMPLETO.json` intacto).
- `scripts/build_cg14_nifi_flow.py` (nuevo, regenera el JSON).
- `docs/CG14_VALIDATION_CONTRACT.md`, `docs/CG14_VALIDATION_RUNBOOK.md`,
  `docs/CG14_SECURITY_CHECKLIST.md` (nuevo), este informe (nuevo).

## 5. Integración NiFi/Kafka (G06): artefacto listo, vivo BLOCKED

- Flujo versionable generado y blindado con 7 tests estructurales (shape,
  script==fuente, sin secretos, parámetros resolubles, versiones 1.25.0,
  cableado válido/rechazado/reintento).
- Vivo BLOCKED: `kafka` no resuelve por DNS; `docker compose` solo lista
  `scoring-api`; NiFi en 8443 responde 401 a API anónima; sin Groovy/Java
  locales para ejecutar el script. Ninguna prueba real ejecutada ni fingida.
- No se toca el esqueleto del equipo; el despliegue espera a CG03/CG13.

## 6. Dependencias pendientes

CG03 (esquema oficial, `kind`, límites físicos, rango de máquinas), CG13
(topics `cnc.telemetry.validated`/`cnc.rejected` propuestos, grupos,
retención, sobre de error), CG05/CG29 (Filebeat es esqueleto), CG28/CG16
(`/predict`, consumidor de inferencia — sin crear API nueva por restricción).

## 7. Comandos de repetición

```bash
source .venv/bin/activate
python -m pytest -q
python -m pytest -q --cov=cg14_validation --cov-report=term-missing --cov-branch tests/test_cg14_validation.py tests/test_cg14_regression.py tests/test_cg14_hardening.py tests/test_cg14_metrics.py
ruff check cg14_validation tests/; ruff format --check cg14_validation tests/
python -m mypy cg14_validation; python -m pip check; git diff --check
python -m pip_audit; python -m bandit -r cg14_validation -q
```

## 8. Criterios de aceptación de #14

Los 6 checkboxes siguen sin marcar (requieren flujo real, rutas
2xx/422/5xx/timeout, retry, contadores/provenance en NiFi y revisión de
compañero). Cubierto: contrato versionado, reglas deterministas, validación
local probada, diseño documentado. Pendiente: todo lo que exija infra real.

## 9. Recomendación PR

Aún no abrir: código sólido (80/80, 100 % cobertura, estático limpio), pero
G06 y la revisión externa están BLOCKED. Propuesta: commit local tras tu
autorización y PR de propuesta cuando CG03/CG13 confirmen esquema y topics.
