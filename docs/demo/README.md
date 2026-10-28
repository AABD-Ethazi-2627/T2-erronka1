# CG26: demo de la API vigente y preparación de defensa

## Material listo para estudiar y ensayar

1. [Explicaciones completas en castellano](AZALPENAK_20261028.md): cuatro
   bloques, ejemplos y respuestas para comprender y explicar el proyecto.
2. [Guion oral en euskera](DEFENTSA_GIDOIA_20261023.md): texto de exposición,
   actualizado con la campaña del 28/10 y sus resultados.
3. [Ensayo preparado](ENTSEGU_PRESTATUA_20261028.md): orden de archivos y
   capturas, recorrido de casos, preguntas cruzadas y hoja de trabajo.
4. [Consulta docente bilingüe y checklist de entrega](../rubrica/CONSULTA_DOCENTE_PREPARADA_20261028.md):
   mensaje listo para copiar y selección de artefactos con sus fuentes.

Empezar por las explicaciones y usar el ensayo para practicar con las evidencias
ya guardadas. El enunciado contempla una demo live de diez minutos; el recorrido
offline sirve para prepararla y como respaldo, sin sustituir la ejecución viva.
Las condiciones finales se concretan mediante la consulta preparada. La sección
técnica que sigue conserva sus comandos y su base histórica.

Seguimiento vigente: [pendientes humanos del 28/10](PENDING_HANDOFF_20261028.md) y
[matriz de 40 criterios del 28/10](../rubrica/ESTADO_20261028.md). El guion que
sigue conserva su base histórica.

Corte posterior: [preparación de Niistal y bloqueos al 26/10](ESTADO_NIISTAL_20261026.md). Conserva este guion y su base histórica.

Base revisada `f770932d61ff55158bb18c9d89120617e8c5db65`. Este guion prepara una reproducción aislada de contratos actuales, sin infraestructura compartida ni modelos de entrega. El [ensayo del 21/10](../evidence/CG26_REHEARSAL.md) conserva su fecha/alcance; no es una defensa realizada. La [matriz actual](../rubrica/ESTADO_20261022.md) y el [acta pendiente](ACTA_PENDIENTE_20261022.md) separan ejecución técnica de aceptación humana.

## Preparar un worktree propio en D:

Requisitos: checkout existente de confianza con el SHA disponible, Git, Python3.11/3.12 y uv. En Windows usar PowerShell sin perfil. Sustituir las rutas por un checkout/evidencia propios; no clonar ni reutilizar outputs/venv/ledger ajenos. Cada persona anota commit, versiones y códigos de salida. Si ya existe el destino, elegir uno nuevo; no borrar resultados previos.

```powershell
$repo = 'D:/github/T2-erronka1' # sustituir por el checkout existente propio
$work = 'D:/github/_worktrees/t2-demo-companero-01'
$evidence = 'D:/github/_local/t2-demo-companero-01'
New-Item -ItemType Directory -Force "$evidence/process-temp" | Out-Null
$env:TMP = "$evidence/process-temp"
$env:TEMP = $env:TMP
$env:TMPDIR = $env:TMP
$env:UV_CACHE_DIR = "$evidence/uv-cache"
$env:UV_PROJECT_ENVIRONMENT = "$evidence/venv"
$env:PYTHONDONTWRITEBYTECODE = '1'
git -C $repo worktree add --detach $work f770932d61ff55158bb18c9d89120617e8c5db65
# Comprobar exit 0 antes de continuar.
Set-Location $work
git rev-parse HEAD
uv --version
uv sync --frozen --python 3.11 --extra kafka
# Comprobar exit 0 antes de continuar. No entrenar ni empaquetar modelos.
uv run --frozen --extra kafka python -B -m scripts.audit_cg02 --check
uv run --frozen --extra kafka python -B -m scripts.check_cg25_memory
uv run --frozen --extra kafka python -B -W error::ResourceWarning -m unittest discover -s tests -p test_scoring_replay.py -v
uv run --frozen --extra kafka python -B -W error::ResourceWarning -m unittest discover -s tests -p test_cg26_rehearsal.py -v
git diff --check
```

Detenerse ante un código distinto de 0 y guardar comando/salida. Los logs negativos de bundle ausente son esperados cuando el test exige 503; un traceback de unittest no lo es. En WSL seleccionar explícitamente distribución, intérprete/venv Linux propio y temporales en `/mnt/d/.../process-temp`, sin `/tmp`. El informe [Windows PR67](../evidence/WINDOWS_PORTABILITY_20261022.md) registra cuatro entornos del autor; no presentar esas suites como ejecución propia.

## Qué demuestra cada caso

Los tests de replay usan dobles deterministas etiquetados `synthetic-replay-only`, SQLite/archivos reales y fixtures temporales propias. Los tests CG26 incluyen pequeños fits de 24 filas sintéticas; no entrenan modelos de entrega ni consumen el test final. Revisar también `contracts/examples/valid/telemetry.json`, `scoring/score_api.py`, `scoring/response_ledger.py` y el [contrato](../SCORING_REPLAY_CONTRACT.md).

1. **200/replay:** `test_lost_http_response_restart_and_archive_replay` repite la petición válida sin cambiar event_id; exige respuesta idéntica byte a byte, mismo scored_at y sin segunda inferencia, incluso tras reinicio. Archivo concilia1stored+1duplicate y recibo anterior alACK.
2. **409:** `test_same_id_different_valid_payload_conflicts_before_inference` conserva event_id y cambia payload válido; rechaza antes de inferir. No resolverlo inventando un ID nuevo. `test_configuration_reuse_conflicts_and_new_archive_identity_succeeds` comprueba cambio de configuración/identidad de policy.
3. **422:** campos/valores inválidos se rechazan. `test_rehearsal_uses_new_identity_for_trace_variant` y los tests CG26 cubren etiquetas, ETA/RUL, rpm negativo y source.raw_record. Esos campos no son inputs vigentes de `/predict`.
4. **503:** `test_unready_bundle_does_not_serve_previously_cached_success` exige fallo cerrado aun con respuesta antigua en ledger; no score alternativo. Health/predict sin bundle no acreditan disponibilidad.
5. **Trazabilidad:** cambiar ID/fecha para una ocurrencia distinta permite comprobar invariancia del score. Reutilizar el mismo ID con fecha distinta es409; no usar el ejemplo antiguo que esperaba200 para esa mutación.

El CLI `scripts.rehearse_cg26 --manifest ... --output ...` sigue disponible para un bundle propio ya validado y compatible. Requiere modelo RF/IF local de confianza y crea/persiste un ledger; no ejecutarlo sobre modelos de entrega ni reentrenar como parte de este guion. Su variante de trazabilidad ya usa un ID nuevo. Usar salida nueva sin sobrescritura.

## Panel y explicación de 10 minutos

- Minutos0–2: fuente 8000 / split 5600/1200/1200. En validación reutilizada, el umbral F2 `>=0,19082281465428477` produce TP32/FN9/FP9/TN1150; el umbral de AVISO `>=0,15` produce TP32/FN9/FP12/TN1147. Son puntos distintos sobre las mismas predicciones, no un test final independiente. Véase [la auditoría de precisión](../evidence/CG10_PRECISION_20261022.md). Solo cinco sensores+machine_type al estimador, metadatos para trazabilidad.
- Minutos2–5: mostrar los resultados guardados de 200/replay,409,422,503 y explicar ledger/ACK, error transitorio frente a conflicto terminal y recuperación de proceso Windows sin powercut.
- Minutos5–8: abrir [Kibana real del autor](../evidence/ISOLATED_RUNTIME_20261022.md) y [página20/DOM](../evidence/CG19_SVG_ARIA_20261022.md). Distinguir fixtures online de offline fijo; filtros 0/1/31/100, total frente a muestra, Kelvin/UTC y páginas. Son evidencias del autor, no panel levantado por el compañero. Para reproducción viva preparar lab propio con el padre, sin tocar servicios compartidos.
- Minutos8–10: proponer inspección humana de una alerta y comparar FP/FN. El escenario histórico de 1200 €/h es un supuesto de coste de parada, no un coste fijo por FN ni ahorro observado; la [matriz docente posterior](../evidence/CG34_20261023/business-costs.json) usa otros importes por resultado. Explicar IA estrecha, reglas 0,15/0,70 frente a risk_threshold y rareza IF. No ETA/RUL/forecast24h ni acción sobre CNC.

Preguntas: ¿qué confirma un 200 y qué falta hasta elACK? ¿Por qué no reintentar 409 como 503? ¿Por qué cuatro mensajes SMB y 35 estadosDOM no prueban SLA o lectura audible? ¿Qué cambia entre mononodo y clúster? ¿Qué dato haría falta para probar beneficio de mantenimiento? Registrar la respuesta del compañero, sin escribirla en su nombre.
