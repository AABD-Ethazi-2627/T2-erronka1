# CG26: registro del ensayo aislado — 21/10/2026

Estado: avance técnico de #26, **defensa y revisión humana pendientes**.
Procedimiento repetible: [guion de demo](../demo/README.md).
Resultado bruto del ensayo: [JSON versionado](CG26_REHEARSAL_2026-10-21.json).

## Objetivo, alcance y versión

Otro miembro debe poder reproducir casos y explicar entradas, salidas, errores y
límites. Este avance cubre el ensayo de la API en proceso y prepara preguntas de
defensa. No acredita que otro miembro lo haya ejecutado o entendido, ni una demo
de streaming/panel actual, una entrega o aceptación del tutor.

Se comprobó actividad remota antes de clonar y antes de preparar publicación:
#26 seguía abierta, sin comentarios, actualizada el 16/10/2026; PR45–48 ya tenían
sus avances del día. No había otra rama/PR abierta de CG26 en las consultas.
La revisión de PR38/42/48 detectó evidencia histórica E2E, alcance actual y memoria,
pero ningún guion ejecutable de CG26 con estos casos. PR48 no se incorpora ni se
modifica; PR40/41 quedan fuera de la entrega activa.

Base deliberada: PR42, `28a77543bfd67a36b96ddc2f4acc103b13f62c2e`.
Implementación ensayada: `ae14eec148a9ae47f4c317276cc443a81050dc7e`.
El commit posterior solo añade este registro y el JSON de ejecución. Los hashes
del script, API y lock materializados están en `execution_files_sha256` del JSON.
El guion y los dos tests nuevos se revisaron por el propio implementador; no se
presenta como revisión independiente ni como revisión de un compañero.

Clon exclusivo bajo `D:/github/_local/t2-babysit-20261021/cg26-demo-0915`,
sin checkout compartido. Se aplicaron `unslop`, `workflow-records`, `code-quality`,
`quality-core` y `review-quality`. Se reutiliza el sistema de evidencia en
`docs/evidence/`; el procedimiento está en `docs/demo/README.md`.

## Operaciones y resultados reales

Entorno completo: WSL, distribución explícita `FedoraLinux-43`, Python 3.11.15,
uv 0.12.22, paquetes de `uv.lock`. Se usaron caché y venv propios bajo `outputs/`;
no se alteraron servicios compartidos. Los modelos proceden del entrenamiento
local sobre el CSV autorizado, nunca de pickles descargados.

```text
uv sync --frozen --python <Python 3.11.15 local>
uv run --frozen python -m scripts.audit_cg02 --check
uv run --frozen python -m scripts.experiment_rf --output outputs/cg26-linux-complete/rf
uv run --frozen python -m scripts.experiment_anomaly --output outputs/cg26-linux-complete/if
uv run --frozen python -m scripts.package_model --output outputs/cg26-linux-complete/api --rf-dir outputs/cg26-linux-complete/rf --anomaly-dir outputs/cg26-linux-complete/if
uv run --frozen python -m scripts.rehearse_cg26 --manifest outputs/cg26-linux-complete/api/manifest.json --output docs/evidence/CG26_REHEARSAL_2026-10-21.json
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scripts/check_repository_layout.py
```

Los comandos se ejecutaron con `UV_PROJECT_ENVIRONMENT=outputs/venv-linux`,
`UV_CACHE_DIR=outputs/uv-cache-linux` (rutas absolutas del clon) y
`UV_PYTHON_DOWNLOADS=never`. El ejecutor local está conservado en
`outputs/cg26-linux-check.sh` y `outputs/cg26-final-check.sh`, ignorados por Git;
el guion público no depende de esos archivos ni de rutas privadas del equipo.

- Auditoría: `CG02 inventory verified offline: source bytes, quality, labels and time coverage match`.
- Entrenamiento RF/IF y paquete propio v4: completados en directorios nuevos.
- Ensayo final sobre `ae14eec`: código 0, `isolated_rehearsal_passed`.
  `/health` 200; ejemplo normal `OK`, score RF `0.004264675232657996`;
  ejemplo de fallo `CRITICA`, score RF `0.8024801587301588`.
  IF no alertó en ninguno; no se equipara anomalía con fallo.
- Diez entradas inválidas: diez respuestas 422. Variante con ID/fecha distintos:
  mismos scores/alertas. Instancia sin bundle: health/predict 503.
- Suite completa Linux: **106 tests, 18.585 s, OK**, sin omisiones en el resumen.
  Se ejecutó antes de crear `ae14eec`, sobre los mismos bytes de código/tests.
  Sus pruebas API estándar usan `outputs/api`, generado previamente en este
  mismo clon con Python 3.11.9/Windows y sklearn 1.5.0. El ensayo JSON final usa
  el bundle entrenado en Linux y registra sus propios hashes.
- Ruff 0.17.1: `ruff check scripts/rehearse_cg26.py tests/test_cg26_rehearsal.py`
  y `ruff format --check` pasan. `git diff --check` y el diff staged pasan.
- Layout: `Repository layout OK: tracked files, ignore rules and Compose paths`.
  Es configuración estática de Compose; no arranca contenedores.
- `scoring.alert_policy.cost(2, 1, 50, 2)` ejecutado: `2500`.
  Es coste hipotético de errores, sin ahorro empresarial medido.

Los logs completos quedan en el clon: `outputs/cg26-linux-tests.log`,
`outputs/cg26-linux-complete-rf.log`, `outputs/cg26-linux-complete-if.log` y
los logs Windows `outputs/cg26-tests.log`, `outputs/cg26-rehearsal-2.log`.
Los mensajes de bundle no disponible durante la prueba negativa son esperados;
la suite también emite advertencias ResourceWarning de AnyIO/TestClient.
Un resumen OK no se presenta como consola sin advertencias.

## Intentos fallidos y límites de portabilidad

- Windows nativo, Python 3.11.9/uv 0.11.19: entrenamiento, empaquetado y ensayo
  pasan. Los dos tests nuevos de CLI pasan. Suite completa: 106 ejecutados,
  **12 errores** en código no modificado: seis por `fcntl` ausente, tres por
  `os.O_NOFOLLOW` ausente, dos por reapertura de temporales y uno por permisos
  POSIX del archivo env. No se afirma que la suite funcione en Windows.
- `audit_cg02 --check` en Windows falla porque el inventario utiliza separadores
  `/` y el cálculo produce `\`. Se identificaron diferencias en `training` y
  `batches`; no se regeneró el inventario ni se relajó la comprobación.
- Primer intento Linux: el ejecutor PowerShell agotó 60 s mientras entrenaba RF.
  Se verificó que no quedaban procesos de ese intento; había un `rf.pkl` parcial
  sin informe en `outputs/cg26-linux/rf`. Se conserva y **no se empaqueta**.
  Se reanudó con un ejecutor sin ese límite, en `outputs/cg26-linux-complete`,
  sin sobrescribir el intento anterior. Solo el segundo terminó y es evidencia.

## Trazabilidad para revisión

- **G5/G23/G24 →** guion, `scoring/score_api.py`, `scoring/alert_policy.py` y
  CG30 → ejecutar ensayo y explicar offline/inferencia, IA estrecha y reglas/ML
  → comportamiento técnico observado; explicación propia pendiente.
- **G72/G105 →** guion, export Kibana y CG19 → contrastar evento/fuente/rango y
  justificar inspección propuesta → preparación documental, sin nuevo panel vivo
  ni validación de utilidad por operador.
- **G104 →** guion, función `cost`, CG10 y respuestas del JSON → ejecutar coste
  hipotético y discutir falsos positivos/negativos → 2.500 € en ese escenario;
  sin pérdidas ni ahorros industriales observados.
- **#26 →** versión + comandos + JSON + límites enlazados; otro miembro,
  revisor/fecha y conclusión humana: **pendientes**. No marcar Eginda/aceptado.

## Estado y siguiente acción

Validación local terminada dentro de este alcance. Publicación prevista como
draft acotado; CI remoto no se acredita con estas pruebas locales. No se ha
lanzado ningún workflow manual ni modificado triggers. Sin merge, cierre de
issues, cambios Project, despliegue, acciones SMB/OT ni aceptación humana.

Siguiente paso humano: reproducir el guion en un clon propio, completar el
registro del compañero y revisar la decisión del panel. El E2E posterior a PR42
necesita un ensayo separado, autorizado y reconciliado; no extrapolar la
evidencia histórica de PR38. No hay ETA, RUL ni forecast24h en esta entrega.
