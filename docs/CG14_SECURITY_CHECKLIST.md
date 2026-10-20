# Checklist de seguridad CNC Guard (propuesta CG14, reutilizable en CG15–CG18)

Estado: **propuesta local**. Cada punto indica su gate y cómo verificarlo.
Un gate bloqueado no cuenta como aprobado.

## Entradas no confiables

- [ ] Validación estricta de tipos antes de parsear (GATE 1).
  Verificar: `INVALID_TYPE` en `tests/test_cg14_regression.py` y
  `tests/test_cg14_hardening.py`.
- [ ] Presupuesto de tamaño configurable (`CG14_MAX_LINE_BYTES`,
  `CG14_MAX_FIELD_CHARS`) con rechazo `MESSAGE_TOO_LARGE` (GATE 1/5).
- [ ] Sin relleno silencioso con cero: ausente/inválido → rechazo (GATE 1).
- [ ] Excepciones contenidas: ninguna entrada produce traceback sin capturar;
  los fallos devuelven códigos estables (GATE 2).

## Veneno y reintentos

- [ ] Rechazos de validación clasificados como permanentes, sin reintento
  (`is_permanent_rejection`), para evitar bucles de mensajes venenosos
  (GATE 6).
- [ ] Solo señales de transporte admiten reintento acotado (`should_retry` +
  `retry_delays` con techo); después, retry/dead-letter, nunca descarte
  silencioso (GATE 6).

## Secretos y logging

- [ ] Sin credenciales hardcodeadas en código ni flujos (GATE 5).
  Verificar: `grep -rniE "password|api[_-]?key|BEGIN .*PRIVATE" cg14_validation`.
- [ ] Configuración Kafka solo desde entorno (`kafka_config_from_env`);
  TLS exige CA, SASL exige mecanismo y credenciales; fallan rápido si faltan
  (GATE 5).
- [ ] Logs y sobres de error redactados (`redact_for_log`,
  `redacted_config_for_log`): sin passwords, tokens Bearer ni PEM (GATE 5).
- [ ] Recomendación: `SASL_SSL` + ACL de privilegios mínimos por
  consumer-group; `enable.auto.commit=false` con commit tras publicación
  verificada (pendiente de ratificar en CG13).

## Dependencias y tipos

- [ ] `ruff check` + `ruff format --check` en verde (GATE 4).
- [ ] Tipos verificados (`mypy`) en el paquete de referencia (GATE 4).
- [ ] `pip check` sin rupturas; `pip-audit`/`bandit` ejecutados y hallazgos
  clasificados, no silenciados (GATE 5). Las deps de otros módulos
  (p. ej. `starlette` de scoring/CG28) no se actualizan desde CG14.

## Idempotencia y trazabilidad

- [ ] `event_id` estable en replay e independiente por `source_kind`;
  eventos distintos (máquina/timestamp) dan IDs distintos (GATE 6).
- [ ] Original preservado en cada veredicto para auditoría y reprocesado
  (GATE 1/8).
- [ ] Versión de esquema y de artefactos registradas en cada cambio (GATE 8).
