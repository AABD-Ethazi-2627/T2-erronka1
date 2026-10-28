# Integración técnica local — 26/10/2026

## Alcance y fuentes

Worktree asignado: `C:/Users/unaiu/.t3/worktrees/B-taldea/t3-6a929eaa`, rama
`kali/integrate-branch-readiness`. Sin subagentes, publicación, push, PR, merge
remoto, cambios en ramas autoras ni cambios en otros checkouts. Proyecto educativo
AABD; no se añade política MKDL. Rendimiento y aceptación corresponden al padre.

Fuente no comprometida leída sin modificar:
`D:/github/AABD-Ethazi-2627/B-taldea/docs/workflows/pending-review/runs/20261026-branch-readiness.md`.
Procedimiento y estado anteriores leídos antes de actuar. Se aplicaron las skills
unslop, code-quality, security-quality, quality-core y workflow-records.

## Composición

`git fetch --all --tags`: exit 0. Heads revalidados:

| Fuente | SHA exacto | Acción |
| --- | --- | --- |
| Consolidada local | `06510ad85c4e3d392d6e9e9f255a7ae8c57ab23c` | Ancestro completo, deltas conservados |
| PR91 | `b8b4ff5a8e71aac77603f0fb0d7e9a9653b5e170` | Merge local `c90ec22`; árbol `6afad174fd0996968851c6ece8c47f55752ad255` |
| PR93 | `4ff97684a0e0deb51b639daf30ca0c751a1652b4` | Merge local `5c6a413`; filtro canónico preservado |
| PR95 | `b02e620edc732ee1758d40a377f98bbdad65c3b6` | Ya ancestro; no cherry-pick duplicado |
| PR96 | `716c940daf820e530e32f2d5b33610bdfd9f5c2d` | Solo inspección del diff y documento; excluida |

Ambos merges fueron limpios. El primer árbol coincide con el merge-tree previo.
El guard y las cuatro pruebas CG26 permanecen; el arreglo Windows `82ae770` ya
está en la historia remota integrada. No se reentrena ni sustituye identidad.

## Entorno y evidencia en curso

Artefactos propios: `D:/cnc-guard-integration-20261026`.
Runner reproducible: `run_checks.py`, comandos/exit codes/duración en
`checks.jsonl`, logs por check en `logs/`. `outputs/` del worktree es una junction
ignorada a `D:/cnc-guard-integration-20261026/outputs`. Temporales, cachés de
Python/matplotlib y resultados nuevos se dirigen a D:.

Entornos compartidos usados solo para ejecución, sin instalar ni actualizar:
aplicación `D:/cnc-guard-review-20261023/venv-t3-2fccec37/Scripts/python.exe`
(3.11.9); research `D:/cnc-guard-research/venv-20261023/Scripts/python.exe`
(3.12.10). Ambos `uv pip check`: exit 0. Pines directos/dev/kafka de aplicación
verificados contra metadatos instalados antes de ejecutar.

Bundle de `D:/github/_local/t2-review-20261023/delivery-bundle` comprobado antes
de copiar a outputs/api en D:, contra `CG26_REHEARSAL_2026-10-21.json`:

- manifest: `a6cc7a29f0b061e114e046865cf7ac4a3969111a904a0281f1919aff35ea0945`
- rf.pkl: `803ee2e10e0486aaeb1fb65ed43df9d0069c2d5113d1e1ec45777346a0b6735a`
- if.pkl: `a12304b474f290841a435ffb7d9caaa65c0843ce537267d28686a9d0f49aae79`

Docker Desktop Linux no disponible (named pipe ausente). FedoraLinux-43 tiene
Docker 29.9.2, sin imágenes/volúmenes/contenedores; data-root `/var/lib/docker`
en VHD de C:. No se construye ni descarga en ese motor para respetar D:.
Se investigan escaneos remotos con caché propia en D:. Los tres casos ES siguen
pendientes hasta disponer de un runtime aislado con almacenamiento autorizado.

## Correcciones reproducidas

1. Las suites iniciales fallaron (exit 1) en cinco subcasos negativos de Projects:
   esperaban `outside B-taldea`, pero PR93 devuelve `outside T2-erronka1`.
   `fb97061` alinea solo el mensaje esperado. Conserva las cinco entradas
   rechazadas, el filtro exacto y la identidad de equipo. No se llama a GraphQL.
2. El gate remoto `enforce_image_scan.validate("api", {})` y su variante
   `{"Results": []}` devolvían `[]`: ausencia de cobertura tratada como limpio.
   `ae0d3bb` rechaza informes sin identidad Trivy de imagen, sin targets o con
   targets no identificados. La regresión cubre cinco formas de informe inválido;
   los informes reales de las tres imágenes pasan. No se añaden supresiones ni
   se cambian las excepciones remotas Filebeat/Kibana.

## Validación final

Código validado: `ae0d3bb5e2a01246193de0ae9fb4d5ec922932c7`, árbol
`259573a450c5d5683fdfdfdd1079ca6631b9a919`. El commit posterior añade únicamente
continuidad y recibos. [Comandos, exit codes y hashes de logs](20261026-integration-checks.json).

| Check | Resultado | Exit |
| --- | --- | --- |
| `python -W error -m pytest -q` | 666 passed, 3 skipped ES, 324 subtests passed; 46,34 s | 0 |
| `python -W error -m unittest discover -s tests -v` | 374 pruebas, 3 skips ES; 43,914 s | 0 |
| `uv lock --check`, `actionlint`, `git diff --check` | Los tres pasan | 0 cada uno |
| `scripts.audit_cg02 --check`, `scripts.check_repository_layout` | Ambos pasan | 0 cada uno |
| `scripts.check_cg25_memory` | 40 criterios, 90 enlaces, 191 hashes actuales, 18 históricos | 0 |
| `scripts.check_cg20_same_event` | Verificación offline de evidencia archivada; no ejecución live | 0 |
| `scripts.export_runtime --check`, `scripts.image_inventory --check` | Ambos pasan | 0 cada uno |
| `scripts.build_refreshed_lab_flow --check`, `scripts/check_lab_compose.py` | Ambos pasan; Compose es estático | 0 cada uno |
| Research `-W error -m unittest discover -s tests/research -v` | 22 pruebas | 0 |
| Research `-W error -m scripts.ml_study smoke --output D:/cnc-guard-integration-20261026/smoke50` | 50 adaptadores completos, todos `warnings: []` | 0 |
| `scripts.audit_dependencies --latest --output .../dependency-audit.json` | 90 filas inspeccionadas, sin errores ni grupos de avisos activos | 0 |

Los comandos completos con intérprete y argumentos están en el recibo. Se
conservan los intentos fallidos y los logs posteriores, sin sobrescribirlos.
Al preparar el recibo, `git diff --cached --check` detectó CRLF como whitespace
(exit 2); se escribió el JSON con bytes UTF-8/LF y el mismo check pasó (exit 0)
antes del commit. No se cambió la configuración de Git para omitir el error.
Los errores de inicialización simulados por tests negativos no se interpretan
como fallos de la suite final. Las cuatro pruebas del guard CG26 pasan dentro de
ambas suites. Los 31 pines research coinciden con el entorno compartido.

CG25: ninguno de los archivos inventariados cambió; su manifiesto es idéntico
byte a byte al de `06510ad`. No procede regenerar hashes. Los 18 históricos,
el alcance y `human_review=pending` se conservan. La comprobación incluye el
contenido actual y la lectura histórica mediante Git, no solo metadatos.

Dependencias: JSON inspeccionado, cobertura de 58 filas de `uv.lock`, 31 pines
research y una herramienta uv. Estados: 88 registry, un proyecto y una rueda
local con cobertura upstream. La ausencia de avisos en PyPI no demuestra la
seguridad de la modificación local de Kafka; sus regresiones pasan en la suite.

## Imágenes y límites de ejecución

Trivy 0.76.1 descargado desde su release oficial y verificado contra el checksum
publicado. Binario, temporales y caché propios en D:. Base de avisos actualizada
`2026-10-26T07:15:18Z`. Escáner `vuln`, plataforma `linux/amd64`, todas las
severidades, sin omitir no corregibles; origen `remote`, sin usar Docker C:.

| Referencia inmutable del inventario | Targets / registros de paquetes | Avisos en JSON | Scan / gate final |
| --- | --- | --- | --- |
| uv | 2 / 1.026, binarios Rust uv y uvx | 0 | 0 / 0 |
| haproxy | 1 / 24, Alpine 3.24.3 | 0 | 0 / 0 |
| go | 11 / 27, Alpine y binarios Go | 0 | 0 / 0 |

Son registros de paquetes por target, no paquetes únicos. uv es una imagen sin
OS identificado; la cobertura ejecutada es de sus dos binarios Rust. Los JSON,
digest exacto de imagen, ImageID, targets, hashes y comandos constan en el recibo.
No se afirma cero vulnerabilidades para el conjunto del despliegue.

**Pendiente, sin PASS:** las nueve builds `api`, `elasticsearch`, `filebeat`,
`kafka`, `kibana`, `mock-python`, `nifi`, `python` y `wolfi`; su escaneo vigente,
las pruebas de backports y la comprobación binaria de alcanzabilidad Filebeat.
El motor disponible escribe en C: y no tiene imágenes reutilizables; faltan
`mkfs.ext4`/`mke2fs` para preparar un filesystem Linux propio en D: sin instalar
herramientas de sistema. No se cambia su configuración ni se usa su data-root.

Los tres casos ES quedan **skipped**, no pasan en esta ejecución. Requisito:
motor Linux de build/runtime con data-root propio en D:, o runtime corregido
propio ya almacenado en D:. Para retomarlos, construir la imagen ES actual,
crear un contenedor propio con etiqueta de pertenencia, publicar solo loopback,
leer y fijar `CG19_ES_UUID`, ejecutar los tres casos en índices nuevos y verificar
etiqueta/ID antes de detenerlo. No se ha creado ni parado ningún contenedor.

## Estado y continuación

Composición local revisable, con checks estáticos y regresiones pasando; no se
declara completa la validación dinámica de imágenes/ES. No se atribuyen los
PASS del 23/10 al árbol nuevo. El estado del 23/10 queda como histórico en su run
y en `git show 06510ad:docs/workflows/pending-review/state.md`; sus resultados
live y de rendimiento no se han repetido. El informe fuente del 26/10 sigue
siendo evidencia del candidato antiguo, no certificación de esta composición.

El padre debe revisar estos commits y cerrar los requisitos de imágenes/ES antes
de afirmar validación técnica completa. Rendimiento y aceptación mantienen sus
agentes de solo lectura; PR96 no se integra. CI, aceptación docente, ensayo,
entrega, estudio ML sellado e integración industrial no se ejecutan ni se
declaran. No hubo push, PR, merge remoto, Projects aplicado o watchers.
