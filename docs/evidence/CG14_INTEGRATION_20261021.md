# CG14: evidencia de composición y regresiones (2026-10-21)

Código final validado por pytest/focales y checks: `1d279e33d2ae34a3a66b9dae819638b9e72ad5cc`.
La matriz general se ejecutó sobre `7bcb53a`, antes del último ajuste de
correlación SEND; ese ajuste sólo afecta al gate pytest y su negativo, cuya
suite completa se repitió en ambas versiones sobre el código final.
Parte de PR42 `9158193`, fusiona PR57
`aace73c` y PR59 `528bcad`, y luego incorpora PR42 `7983beef471dc2de2a9fd977f8596809dc7f665c`
con PR58, CG21 y la corrección de JSON recursivo. El commit posterior añade
únicamente documentación/evidencia. Proyecto educativo AABD, no MKDL.

## Resultado y alcance

Draft para revisión del padre. Las correcciones de gate, dominio térmico,
test TLS/pytest/CI y alias están implementadas y verificadas offline. El
contrato de ocurrencia/replay tiene una primitiva explícita probada que conserva
los IDs legacy. El cableado CG14→auditoría raw→scoring→archivo sigue pendiente;
no se declara CG14 DONE, RESTORE VERIFIED ni E2E funcional.

| Hallazgo original | Disposición en esta rama | Límite que permanece |
| --- | --- | --- |
| P57-GATE-1, IMPORTANT/P2 | Manifiesto previo de 5 entregas, inventario completo, provenance por coordenadas/ID/escenario, orden de intentos y terminales, 4 DLQ por contenido/filename. Negativos y collector completo probados. | Falta ejecutar NiFi real con esta definición. |
| P57-TEST-1, IMPORTANT/P2 | TLS aislado sólo en test406, pytest 9.1.1 dev locked, paso pytest explícito conservando unittest y extra Kafka. | CI remoto no se acredita con estas pruebas locales. |
| P57-TEMP-1, IMPORTANT/P2 | Kelvin>0 Python/Groovy, cinco exports idénticos a la fuente y tests -1/0/positivo por temperatura. | Groovy se comprueba estáticamente; sin NiFi runtime. |
| P59-DOC-1, SUGGESTION/P3 | Alias cg14-lab-kafka y restore-<run> exacto documentados/probados. | No se infiere identidad SMB. |
| P57-ID-1, IMPORTANT/P2 | Binding opt-in por namespace/topic/partition/offset original, event_id común, delivery_id estable en reentrega y sidecar legacy; dos rutas, replay y ocurrencias iguales probados. | No está conectado al grafo activo; no reescribe eventos históricos. |
| P57-INTEGRATION-1, IMPORTANT/P2 | Plan concreto en CG14_PR42_INTEGRATION; reutiliza el adaptador PR58 ya en base, sin duplicarlo. | Destino raw durable, conexión a API real, respuesta canónica y reconciliación E2E pendientes. |
| INHERITED-IDEMPOTENCE-1, IMPORTANT/P2 | Se respeta el frente independiente de respuesta canónica. | Esta rama no corrige scored_at ni cambia API/archivo. |
| INHERITED-KAFKA311-WARN-1, IMPORTANT/P2 de workflow | Hallazgo nuevo al incorporar PR58: import aislado reproduce 218 DeprecationWarning en Python 3.11, 0 en 3.12. Sin filtros ni parches. | OPEN: falla el gate estricto general de 3.11; resolver en el frente Kafka/dependencia antes de afirmar matriz estricta limpia. |

## Reproducción antes y después

Antes de editar, sobre la composición inicial, el contraejemplo de la revisión
con inventario completo y cuatro DLQ vacías devolvió True; Kelvin cero fue válido;
el test406 falló por FileNotFoundError al abrir la CA local ignorada. El fixture
anterior del gate pasó pese a no reconciliar entregas. Se conservan baseline-*.log
y el probe original en el directorio local de evidencia.

Después, las regresiones rechazan esos casos; el test406 pasa sin CA ni
credenciales. La suite focal de la revisión se adapta sólo para apuntar al
checkout compuesto y exigir el rechazo de los dos fallos reparados. Pasa 15
tests por versión (los 14 anteriores más el test de alias exactos).

La revisión propia final añadió un contraejemplo donde el SEND con filename
correcto precedía a la ruta terminal y otro SEND posterior tenía un filename
ajeno. Se reprodujo primero el falso positivo (split-send-before.log) y luego
se exige que el mismo SEND satisfaga orden y filename. Se repite pytest completo
después de la corrección, sin alterar las aserciones para obtener un pass.

## Validación ejecutada

Distribución WSL seleccionada `FedoraLinux-43`; `/etc/os-release` informa
**Fedora Linux 44 (WSL)**. CPython 3.11.15 y 3.12.15. Dos entornos nuevos en el
directorio de tarea, instalados desde cache con `uv sync --frozen --offline
--extra kafka`; no se alteran los entornos de otros agentes. Primero se validó
la composición sobre 9158193 y después se repitió tras incorporar 7983bee.

- En cada versión: **244 pytest +21 subtests**, cero fallos, con conexiones de
  red y Popen bloqueados en el runner hermético tras inicializar NumPy/SciPy.
- En cada versión: **234 unittest por pasada, dos pasadas**, 6 skips,
  cero fallos/errores/unraisables. En **3.11 el runner estricto devuelve 1**:
  primera pasada con **218 warnings**, segunda con 0 porque el import queda
  cacheado. En 3.12 devuelve 0, con cero warnings en ambas pasadas.
  Los skips corresponden al bundle de modelos ausente y Elasticsearch real.
  Logs conservan avisos de bundle no disponible y diagnósticos asyncio de
  tareas lentas; no se confunden con los contadores de warnings Python.
- **15 focales** adaptados de la revisión, en ambas versiones, OK.
- Ruff **0.17.1**, lint y formato de **127 archivos Python
  versionados, OK. No se relajan reglas. Los helpers untracked preexistentes
  de `.audit/` quedan fuera de ese alcance y se conservan sin editar.
- Actionlint, `uv0.13.1 lock --check`, CG02 `--check`, layout y diff completo
  desde 7983bee, OK. Layout sólo resuelve configuración Compose; no arranca servicios.
- `uv0.13.1 audit --locked`: **57 paquetes**, sin vulnerabilidades conocidas
  ni estados adversos; aviso experimental del comando conservado.
- `run-restore-e2e.py --plan --run-id restoretest001`: STATIC_PLAN_ONLY,
  network_used=false, mutations=false, functional=NOT_TESTED.
- Diff contra 7983bee vacío para score_api, archive_consumer, sus tests de
  profundidad, adaptador Kafka y sus tests. Sus hashes se guardan en el JSON.
  La rama original PR59 permanece en 528bcad; PR57 no se modifica/publica.

Delta propio del lock: pytest, colorama, iniconfig, pluggy y pygments; sólo
cambia la metadata dev del paquete raíz, todos los registros de paquetes
preexistentes permanecen idénticos. Se conserva revisión 5 y kafka-python 3.0.11
de la base. El workflow difiere de esa base sólo por el paso pytest añadido;
sin cambios en triggers/permisos. Se corrige lint/formato heredado de PR57,
incluidos nombres no usados y catches operativos explícitos con diagnóstico
de cleanup redactado. No se silencian fallos para fabricar un pass.

## Pines y prerrequisitos

Export RESTORE nuevo: `60048fc426b25d57dd4bb6f9c8c5c99a48a80e906865d3d49a210e7659f43f52`.
Mock fuente: `f45dfc70a95e86e71b5800213ce9eaccbec8e4db122f4e72b320de9268fd1bcc`;
su cambio sólo elimina dos noqa ya innecesarios. Ambos pines se actualizan
explícitamente y siguen rechazando bytes diferentes. La copia antigua del
host requiere revisión/migración; no se modificó ni ensayó durante este trabajo.

No se ejecutaron upload, producer, RESTORE host, servicios compartidos, SMB/OT,
modelos de entrega ni test final. Las pruebas existentes que entrenan usan
artefactos temporales; no se ejecutan los scripts de generación del bundle de entrega.
No hubo CI manual, comentarios, Copilot ni merge remoto. La revisión del padre
y del equipo, el CI del SHA publicado y el ensayo runtime autorizado permanecen
separados de estos resultados. El hijo no vigila ni sondea PRs.

## Repetición y evidencia durable

En cada entorno Linux 3.11/3.12 bloqueado, ejecutar:

```bash
uv sync --frozen --extra kafka --python 3.11
uv run --frozen --extra kafka python -m pytest -q tests/test_cg14_*.py
uv run --frozen --extra kafka python tests/run_strict_resources.py
uv run --frozen --extra kafka python -m scripts.audit_cg02 --check
uv run --frozen --extra kafka python -m scripts.check_repository_layout
```

Los comandos pytest del trabajo real se ejecutan mediante un
wrapper con guards de red/procesos; la invocación directa anterior coincide con
el paso CI, sin atribuirle ese bloqueo adicional. Cambiar a entorno 3.12 para
la segunda matriz. No ejecutar experiment/package_model para repetir CG14.

[Resumen JSON y hashes](CG14_INTEGRATION_20261021.json).
Logs, scripts de reproducción, resultados completos y diff están en
`D:/github/_local/t2-babysit-20261021/cg14-integration-evidence/`:
`current-validation-results.json`, `current-*.log`, `focused-review-*.log`,
`final-checks.json`, `final-*.log`, `baseline-*.log` y `state.md`.
Fallos iniciales conservados: pytest ausente del entorno antiguo; pin export
desactualizado tras el cambio; sync Windows offline sin SciPy en cache (no se
descargó SciPy). Se usó uv0.13.1 temporal de 14.7MiB para lock/audit y caches
Fedora existentes; no se descargaron imágenes ni modelos.

## Hallazgo residual reproducible: Kafka en Python 3.11

Un proceso limpio con `warnings.simplefilter("always"); import kafka`, sin
importar código del repositorio y con red/procesos bloqueados, produce 109
avisos read_text y 109 open_text en 3.11; en 3.12 produce 0. Origen primario:
`kafka/protocol/schemas/load_json.py:14`, que llama a la API legacy de recursos.
La versión 3.0.11 ya estaba fijada en PR42/PR58 y permanece byte-equivalente en
el lock. El código/test del adaptador tampoco cambia en esta rama.

Es deuda de compatibilidad de la base incorporada, no un fallo funcional de
CG14 ni una vulnerabilidad demostrada. Aun así, **el gate estricto 3.11 falla**;
no se declara verde. Se preservan `kafka-warning-probe-311.json`,
`kafka-warning-probe-312.json`, `kafka_warning_probe.py` y los logs completos.
El alcance del usuario reserva ese frente y limita el lock a pytest: no se
actualiza/parchea Kafka, no se filtran warnings ni se precarga para ocultarlos.
El padre debe coordinar una corrección y repetir el gate antes de aceptar esa
matriz. Esta PR sigue draft para revisar los arreglos CG14 y la brecha conocida.
