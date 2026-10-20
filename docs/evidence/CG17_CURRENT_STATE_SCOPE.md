# Alcance corregido — AI4I reducido, estado actual y ausencia de fugas

Confirmación del usuario20Oct2026: el generador del profesor usa el AI4I completo,
pero el entrenamiento debe usar exclusivamente el CSV reducido suministrado. Las
etiquetas presentes en el stream se retiran antes de `/predict`. Queda desactivado
el objetivo de predecir fechas, ETA, RUL y evolución estacional para esta entrega.
Esta decisión sustituye las propuestas de datasets alternativos y pronóstico temporal;
los experimentos históricos se conservan fuera del modelo/API desplegados.

## Correcciones

- `scoring/scope.py`: huella exacta del CSV reducido,8000filas. Se leen los mismos bytes
  para verificar y cargar, evitando cambios de archivo entre ambos pasos. RF/IF entrenan
  solo con cinco sensores y `machine_type`; el target sirve como supervisión o filtro de
  normales, nunca como predictor. Las variables físicas derivan solo de esos sensores.
- RF/IF reentrenados en directorios nuevos; se conserva el split anterior:5600fit,
  1200validación ya observada y1200test previamente inspeccionado excluido. No se usa
  el dataset UCI completo, SMB ni datos sintéticos como entrenamiento operativo.
- Empaquetado v4 verifica procedencia de ambos informes y hashes de modelos propios.
  El manifiesto exige `AI4I_CURRENT_STATE_ONLY`, `temporal_prediction_enabled=false`,
  seis entradas exactas y score contemporáneo no calibrado. API y preflight rechazan
  paquetes antiguos o incompatibles; no basta con que el pickle tenga un hash correcto.
- NiFi construye la petición mediante lista permitida y ya no incluye `source.raw_record`:
  la fila cruda contenía etiquetas aunque el pipeline las descartaba. Los campos
  `machine_failure` y `failure_*` no pasan al cuerpo del predict. CSV original se conserva
  en la fuente/archivo de captura y evidencia de errores; no se incorpora al modelo.
- Contrato/Pydantic rechazan etiquetas, raw CSV y campos temporales. `/health` y la
  respuesta declaran alcance/semántica. El DataFrame entregado a cada estimador contiene
  exactamente las seis variables; fecha/ID/procedencia solo son trazabilidad.
- Se conservan `OK/AVISO/CRITICA` a0.15/0.70 y el aviso F2 ajustado de desarrollo como
  señales distintas. Isolation Forest sigue siendo anomalía, no probabilidad de fallo.

## Aplicación local

Paquete nuevo: `outputs/api-current-state-20261020/`. El enlace `outputs/api` apunta a
ese paquete verificado; anterior conservado en `outputs/api-before-scope-20261020/`.
La API Docker local se reconstruye con el nuevo código y se inicia en127.0.0.1:18001.
No se reentrena online ni se modifica ningún equipo industrial.

El normalizador y `nifi-flows/cnc_lab_completed.json` contienen el mismo script corregido.
NiFi local estaba parado: se preservó su configuración original en copia privada0600
fuera de Git y se parcheó el script persistido, verificando contenido y propietario.
No se ha arrancado/reprocesado Kafka/Filebeat/NiFi/Elasticsearch/Kibana en esta corrección.
Las colas con peticiones antiguas que contengan raw CSV serán rechazadas por la nueva
API; se deben tratar como migración/reproceso explícito, nunca como riesgo cero.

## Verificación

- Suite completa:104tests pasan, incluidos7 específicos de alcance y regresiones.
- Groovy de producción ejecutado con los callbacks de sesión en memoria usando el
  runtime Groovy4/Java de la imagen NiFi: cambiar las seis etiquetas0→1 deja idéntica
  la petición y no quedan etiquetas ni raw CSV. No es una afirmación de E2E streaming.
- Payload generado por ese script aceptado por API real:HTTP200. Ocho entradas con
  etiquetas/ETA/RUL y una con `source.raw_record` recibenHTTP422. No devuelve fechas
  previstas, ETA ni vida restante. Variar timestamp/ID no altera scoreRF ni anomalía.
- Comparación con modelos anteriores sobre la validación reutilizada: diferencia máxima
  RF0.0 e IF0.0. La selección de variables anterior ya evitaba fuga dentro del estimador;
  se corrigen además los límites del contrato y la procedencia del artefacto.
- Auditoría de fuente inmutable y preflight pasan. Ruff check/format en Python cambiado.
  Persisten ResourceWarning anyio de tests API conocidos sin fallos; no se afirma una
  prueba independiente nueva ni se valida precisión/anticipación industrial.

Detalles/hashes en [CG17_CURRENT_STATE_SCOPE.json](CG17_CURRENT_STATE_SCOPE.json).

Reproducción desde checkout nuevo:

```sh
uv run --frozen python -m scripts.experiment_rf
uv run --frozen python -m scripts.experiment_anomaly
uv run --frozen python -m scripts.package_model
uv run --frozen python -m unittest discover -s tests
uv run --frozen python -m scripts.audit_cg02 --check
uv run --frozen python -m scripts.integration_preflight
```

En un checkout con salidas anteriores, usar `--output` nuevos y los argumentos
`--rf-dir/--anomaly-dir` de empaquetado. No sobrescribir evidencia ni cargar pickles
externos. El harness Groovy está en `tests/verify_nifi_current_state.groovy` y requiere
Groovy4+groovy-json y Java21, disponibles en la imagen NiFi de laboratorio.

Los experimentos temporales no se copian a la imagen de scoring ni tienen rutas en
la API; no se incluyen como entregables ni recomendaciones de mantenimiento por fecha.
La tarea activa es clasificación contemporánea y revisión priorizada por condición.
