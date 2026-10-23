# Pendientes de integración: revisión privada del 23/10/2026

Base exacta: `5005ccde81f16cd2deac6ee3b30085d773e0fc88`.
Checkout: `D:/github/AABD-Ethazi-2627/B-taldea`, rama
`review/pending-20261023`. Repositorio canónico consultado:
`AABD-Ethazi-2627/T2-erronka1`; el remoto local conserva la URL antigua.
Última lectura GitHub: **2026-10-23T16:43:24Z**. Main y los once heads siguen
iguales al primer corte. Este informe no aprueba merges ni cierres.

**Resultado:** tres PR aportan trabajo actual (#73/#91/#92); #39/#40/#41 ya
son ancestros de main. Las otras cinco requieren disposición histórica o
rescate selectivo. Se confirmaron dos defectos mediante probes offline: el
guard de #91 no fija la identidad de entrega y el sincronizador de main
rechaza el nombre canónico. Además, #73 y la continuidad ML contienen estados
anteriores a decisiones e integraciones ya realizadas.

Durante esta revisión el padre localizó el bundle de entrega y preparó una
prueba de corrección del guard. **La ausencia del bundle ya no bloquea este
host Windows**: sus tres hashes se comprobaron independientemente. Este revisor
no transfirió ni cargó modelos. Al cierre apareció evidencia concurrente del
padre: medida en proceso completada y piloto E2E interrumpido, detallados abajo.

## Alcance y evidencia

Se aplicaron las instrucciones del encargo, `review-quality`, `quality-core`,
`unslop` y `workflow-records`, reutilizando el registro existente de
`docs/workflows/ml-alternatives/`. No se encontró otro AGENTS.md en la jerarquía
local inspeccionada ni en los archivos del proyecto. Es un repositorio educativo
AABD; no se aplicó una política MKDL por coincidencia de autor.

Lecturas: Git local, API de GitHub, estado de hilos del proyecto T3 y artefactos
ya existentes. Las únicas escrituras de este revisor son este informe y
`D:/github/_local/t2-review-20261023/integration/` (en adelante, **LOG**).
Se registraron las once PR con `link_pull_request`; la lista final confirma
once enlaces y `watching=false` en todos. No se enviaron comentarios, hicieron
push/merge/cierres, modificaron ramas, instalaron dependencias, arrancaron
contenedores, entrenaron modelos ni contactaron SMB/OT/servicios compartidos.

Captura detallada: `LOG/commands.jsonl`, `summary.json`,
`pr-<N>{,-view,-reviews,-review-comments,-comments,-checks,-status,-files,-compare,-final}.json`,
`pr-<N>-summary.json`, `pr-<N>-original.patch`, `pr-<N>-main-paths.txt`,
`historical-ci-annotations.json` y `final-readback.json`.
Las citas `path:line` siguientes se refieren al SHA expresamente indicado;
`LOG/snapshots/<SHA12>/` conserva los archivos examinados sin cambiar checkout.

## Las once PR y su relación con main

Δ significa archivos del delta `merge-base(main, head)..head`, no diferencias
completas de árboles ni una propuesta de borrar lo que entró después en main.
Los metadatos, rutas y blobs originales de cada PR están separados en LOG.
Las bases apiladas actuales son #38→#39→#40→#41 y #29→#30.

| PR | Head exacto | Δ | CI visible del head | Disposición técnica propuesta |
|---|---|---:|---|---|
| [92](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/92) | `67ee0345aa6bddc4a4c22f8789f4ae9bb0098f35` | 63 | 14 SUCCESS, 0 anotaciones | Vigente: infraestructura, locks y auditoría. No duplicar esta actualización. MERGEABLE/BLOCKED, REVIEW_REQUIRED. |
| [91](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/91) | `c49813df9eb0ee9a4735c1af4372ddc85c01d9e3` | 7 | paths/test SUCCESS, 0 anotaciones | Vigente, draft: herramienta CG32; corregir identidad y completar medidas separadas. MERGEABLE/BLOCKED, REVIEW_REQUIRED. |
| [73](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/73) | `505a8eb4c173b781426cb3db678429b949da664d` | 12 | paths/test SUCCESS, 0 anotaciones | Vigente: autenticación RESTORE, pruebas y diagnóstico del host. Reconciliar documentación con aceptación PM posterior. MERGEABLE/BLOCKED, REVIEW_REQUIRED. |
| [44](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/44) | `8428d7a2e87761860ba50ab32fd7d0d7b354bb1c` | 8 | Sin check-runs | Histórica; el rescate de hardening #70 ya está en main (`006ee4b`). Sus ocho rutas existen hoy, tres con el mismo blob. DIRTY/REVIEW_REQUIRED; no integrar la infraestructura antigua en bloque. |
| [43](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/43) | `a0c33600b99c9af9decb90d8129306244d59b35d` | 14 | Sin check-runs | Adaptada al camino activo de CG04; su split 80/20 y lock no son el candidato de entrega. DIRTY/REVIEW_REQUIRED. |
| [41](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/41) | `84dfb7cd0c1ad7b7392ef69f3696230d12fd51c9` | 0 | test SUCCESS, 1 warning | Head ancestro de main: implementación ya contenida y evolucionada. CLEAN, sin decisión APPROVED. |
| [40](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/40) | `01c196e2663d3a7ee697e64bcaa8095ae5e1f0df` | 0 | test SUCCESS, 1 warning | Head ancestro de main: implementación ya contenida y evolucionada. CLEAN, sin decisión APPROVED. |
| [39](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/39) | `ce06c47a72e1d73113251cd39178f9f5cf8fb44e` | 0 | test SUCCESS, 1 warning | Head ancestro de main: implementación ya contenida y evolucionada. CLEAN, sin decisión APPROVED. |
| [38](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/38) | `9e3a15608f9359f3a74609c1fcfa8f0383ea5b8c` | 9 | test SUCCESS, 1 warning | Casi toda la implementación está incorporada/evolucionada. Quedan cinco archivos exclusivos de gateway LAN mTLS; no habilitarlos por arrastre. DIRTY/REVIEW_REQUIRED. |
| [30](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/30) | `9066c71cdcd1e70f7b346e4ab9fa6e73fe6e863c` | 65 | Sin check-runs | PR apilada: 38 rutas propias respecto a #29. Contratos evolucionados; alias Todo/To do rescatado en #71 (`54d80f4`). Conserva un cambio útil de nombre canónico, todavía ausente en main. CLEAN no equivale a aprobación. |
| [29](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/29) | `4385209783871aaef15d267596364789e287546b` | 33 | Sin check-runs | Histórica: modelos/notebooks/CI alternativos no promovidos; rescatar únicamente el filtro canónico de Projects tras revisión. DIRTY/REVIEW_REQUIRED. |

Ninguna de las once tiene una revisión GitHub `APPROVED` en la captura. Los
comentarios antiguos de #43 revisan otras revisiones. El comentario Copilot de
#73 informa cuota agotada, no una revisión técnica ni aprobación. Las cuatro
anotaciones de #38–#41 son advertencias históricas sobre el action checkout y
Node 20; los checks terminaron SUCCESS. El estado legacy `pending` con
`statuses=[]` aparece en las once: no se interpreta como otro check fallido.
No se descargaron ni reejecutaron las suites históricas completas.

Evidencia de adaptación CG04: `docs/CG04_ENVIRONMENT.md:3` y `:34` en main
describen la adaptación explícita de #43, las particiones 5600/1200/1200 y el
solapamiento histórico 394/1200 del fit 6400. Es evidencia versionada inspeccionada,
no un entrenamiento repetido aquí. Los cinco archivos exclusivos de #38 son
`docker-compose.lan.yml`, `docs/LAN_ACCESS.md`, `lan/haproxy.cfg`,
`scripts/create_lan_certs.sh` y `tests/test_lan_access.py`.

### Actividad de #92 y riesgo de duplicación

La PR fue actualizada por última vez a `2026-10-23T12:10:52Z`; no cambió durante
las dos capturas y sus catorce checks están terminados. `t3_thread_list`, con
subagentes y también hilos settled del **proyecto actual**, no muestra un
implementador vivo propio de #92. Esto **no demuestra inactividad fuera de ese
inventario**. No hay fundamento para crear otra actualización de dependencias;
el siguiente trabajo útil es revisar su head publicado o coordinar su autoría.

El informe de #92 conserva riesgos: `docs/evidence/DEPENDENCY_REVIEW_20261023.md:115`
y `:192` en `67ee0345...` registran hallazgos HIGH/CRITICAL en scans de imágenes
externas y 44 HIGH Debian sin parche en la API final. Se inspeccionó esa evidencia,
sin repetir scanners ni validar explotabilidad/CVE individual. Los jobs verdes
no significan cero hallazgos: parte del modo de scan es informativo. La revisión
independiente citada cubría `41cb66f..0e2a0fd`; la evidencia posterior se verificó
por el autor, según `:136`. No atribuir una revisión independiente del head final.

## Hallazgos accionables

**F1 · IMPORTANT · confianza alta · introducido en #91.** El guard promete
fijar el bundle CG26, pero solo compara archivos con el manifiesto suministrado.
Evidencia: `scripts/cg32_lab.py:730`–`:740` en `c49813df...`; callers de `run`
en `:293` y de `model` en `:950`. Contradice la garantía de rechazo de sustitutos
en `docs/evidence/CG32_STATUS_20261023.md:23`–`:30`.

Probe ejecutado: `LOG/probe_bundle.py` extrae únicamente esas funciones por AST,
usa bytes inocuos y no importa el lab ni deserializa pickles. Un manifiesto
coherente distinto, con el mismo `model_version`, fue aceptado; cambiar después
un archivo sí fue rechazado. Resultado: `LOG/bundle-guard-probe.json`.
La prueba acredita el defecto del guard, no el arranque de un modelo inválido
en la API. Corrección mínima: exigir el hash CG26 del manifiesto y los dos
artefactos **antes** de recursos/carga de modelos, conservando además la
comprobación de coherencia interna; añadir el caso de sustituto coherente.

**Trabajo concurrente ya detectado:** el padre escribió
`docs/evidence/CG32_BUNDLE_PROOF_20261023.json`, con aceptación baseline y rechazo
corregido. No reimplementar ese parche: revisar su candidato/commit y su prueba.
El head remoto auditado todavía contiene F1; este revisor no inspeccionó el
delta de corrección del padre.

**F2 · IMPORTANT · confianza alta · preexistente en main.** Projects rechaza
el repositorio canónico. Evidencia: `scripts/sync_projects.py:9` fija
`AABD-Ethazi-2627/B-taldea`, y `:143` compara exactamente `nameWithOwner`.
El API actual identifica el repositorio como `AABD-Ethazi-2627/T2-erronka1`.
Probe `LOG/probe_project_sync.py`: `plan()` acepta la fixture antigua y rechaza
la canónica con `Source contains content outside B-taldea`; no hizo GraphQL,
lectura de Projects ni `apply`. Resultado: `LOG/project-sync-probe.json`.
Rescatar el cambio puntual presente en #29/#30, conservar el campo de equipo
`Taldea=B-taldea` y los guards de alias/ambigüedad de #71. Añadir regresión con
el nombre canónico y ejecutar los tests específicos; no aplicar el tablero.

**F3 · IMPORTANT · confianza alta · documentación de #73 desactualizada.**
`docs/CG14_ACCEPTANCE_MATRIX.md:15`–`:33` y
`docs/CG14_TECHNICAL_HANDOFF.md:3`–`:10` en `505a8eb4...` presentan #14 abierta,
revisión pendiente y la copia RESTORE como impedimento de aceptación global.
GitHub registra #14 **CLOSED**, `2026-10-22T13:33:36Z`, con
[aceptación PM expresa](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/14#issuecomment-6342057992)
del grafo NiFi→ExecuteStreamCommand→worker, equivalencia de revisión autorizada
por el usuario y límites por ciclo. Un
[seguimiento posterior](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/14#issuecomment-6359261989)
reafirma que no se rehaga con processors nativos ni se reabra esa aceptación.
Actualizar el corte vigente y conservar el informe del host como histórico.
Separar la mejora opcional RESTORE, la aceptación PM ya concedida y la
equivalencia académica aún pendiente en #82. No fabricar una firma de tercero.

**F4 · NOTE · confianza alta · continuidad ML anterior al merge.**
`docs/workflows/ml-alternatives/state.md:27`–`:36` y
`docs/evidence/CG34_EXPLORACION_20261023.md:317`–`:322` dicen que #90 está
abierta y falta integración. Main `5005ccd` es precisamente el merge de #90;
`3a5c3cf4d318ba254b8d461b9a03a8242bb32bd3` está contenido en main.
La issue #83 y comentarios de #85/#87/#88 también conservan aquel corte.
Actualizar continuidad local con merge/head y mantener separado lo que sigue
sin aceptar. No reanudar el estudio sellado ni lanzar fits por esos textos.

## Desbloqueo privado y reversible de CG32

**Identidad ya disponible y verificada en este host, sin entrenamiento:**

| Archivo | SHA-256 exigido y observado |
|---|---|
| manifest.json | `a6cc7a29f0b061e114e046865cf7ac4a3969111a904a0281f1919aff35ea0945` |
| rf.pkl | `803ee2e10e0486aaeb1fb65ed43df9d0069c2d5113d1e1ec45777346a0b6735a` |
| if.pkl | `a12304b474f290841a435ffb7d9caaa65c0843ce537267d28686a9d0f49aae79` |

Fuente de identidad: `docs/evidence/CG26_REHEARSAL_2026-10-21.json:21` y `:27`.
La copia del padre está en
`D:/github/_local/t2-review-20261023/delivery-bundle/`; procedencia en
`docs/evidence/PENDING_BUNDLE_20261023.json`. Este revisor recalculó los tres
hashes: `LOG/delivery-bundle-verification.json`, 16:44:19Z. No cargó modelos.
El paquete research `34a14ab9...` del estudio CG34 y el bundle recién generado
del smoke de #92 **no sustituyen** esta identidad.

Actualización concurrente recibida durante el cierre del informe:
`docs/evidence/CG32_ORIGINAL_MODEL_20261023.json` registra la medición del padre
en WSL/Linux: 600 observaciones RF+IF en proceso, 20 calentamientos excluidos,
p50 **7,467 ms**, p95 **11,073 ms**, máximo **67,721 ms**. Este revisor verificó
el SHA del registro bruto y recalculó sus percentiles, sin ejecutar inferencia
(`LOG/concurrent-model-record-verification.json`). No son latencias HTTP/E2E.
`docs/evidence/CG32_INTERRUPTED_PILOT_20261023.json` registra timeout del ejecutor
a 60 s en `cg32-1ba594f6`, run `original-pilot-r1-7de521`, fuente
`4a6e01a6004e87cc156d3a3944625e82a0855616`: diez jobs completed y diez documentos
ES observados, con driver ausente y parada propia documentada. El piloto **no
es una medición completada**; no reconstruir sus tiempos ni repetirlo con los
mismos IDs. La operación y la parada son evidencia del padre, no reejecutadas
por este revisor. El siguiente intento debe partir de la conciliación conservada
y usar IDs nuevos; no duplicar la medición de modelo ya terminada.

Pasos para el padre, por orden:

1. Revisar el parche privado de F1 ya preparado, fijar su SHA y ejecutar la
   regresión de sustituto coherente más los tests CG32. Componer #91 sobre la
   base acordada sin tocar ramas de autores. Resolver por separado la transición
   de imágenes/dependencias de #92; no mezclar resultados de runtimes distintos.
2. Conservar la copia del bundle, hashes y entorno del manifiesto. Si el ensayo
   se realiza en Linux, copiar **solo esos tres archivos** a una raíz privada
   nueva por un canal ya autorizado y comprobar hashes allí. No se ha hecho esa
   transferencia. El runner actual usa `/proc/meminfo`, `/dev/null` y
   `st_blocks` (`scripts/cg32_lab.py:82`, `:121`, `:718`): no ejecutarlo como
   automatización nativa Windows sin una adaptación verificada.
3. Preparar o continuar, fuera de este encargo de lectura, un lab Linux exclusivo con el
   entorno compatible y recursos de `docs/CG32_LOAD_PROTOCOL.md:77`–`:105`.
   Mantener el bundle RO, destinos y ledger propios. El primer gate ya no es
   buscar/reentrenar el modelo, sino verificar candidato, entorno y recursos.
4. Cuando exista autoridad para ejecutar el lab: init/up/model si aún faltan,
   nuevo piloto tras conciliar el interrumpido, tres
   repeticiones 10/s y 50/s únicamente si lo permiten piloto/presupuesto; pausa
   y kill aparte; Discover del mismo ID; stop propio con datos retenidos.
   Ninguno de esos pasos fue ejecutado por este revisor.
5. Publicar una tabla observado/objetivo y conciliar conjuntos de IDs, pérdidas,
   duplicados, rechazados, pendientes y offsets; distinguir tiempo de modelo,
   HTTP y E2E. El ensayo previo NOT-DELIVERY de #91 no acredita rendimiento de
   entrega. Sus 426 guardados/174 backlog y ~0,31–0,44 ev/s son evidencia previa
   del autor, no medidas repetidas aquí. Si la tasa falla, registrar el fallo;
   comparar únicamente `--max-records` con fixture/tasa constantes según protocolo.

## CG14: qué queda y cómo tratarlo sin operar el broker legacy

La mejora de autenticación y el diagnóstico de #73 siguen siendo útiles. La
evidencia del 22/10 identifica Script Body antiguo y almacenamiento/entrypoint
legacy; es una inspección histórica de ese host, **no una comprobación viva de
este revisor**. Paths: `docs/evidence/CG14_BRANCH_AUDIT_20261022.md:57` y `:106`
en `505a8eb4...`. No es necesario repetir merges de las seis ramas CG14.

Primero corregir F3 y revisar el diff privado de autenticación/tests. Para la
línea RESTORE, el padre puede preparar offline: inventario de IDs/configuración,
comparación del Groovy/export seguro, hashes esperados, directorios y plan de
recuperación; conservar layout y snapshots. El paso operativo menos invasivo
es un laboratorio independiente con destinos propios. Trasladar sus IDs no
puede implicar adoptar o activar el original por nombre; si el runner está
fijado a IDs antiguos, primero requiere una adaptación revisada.

Si se decide trabajar sobre el host legacy, inventariar log **y metadata**,
cluster ID, mounts, topics/offsets y consumidores, y verificar una restauración
del backup antes de sustituir contenedor/volúmenes. Mantener los anteriores
para rollback. Con RESTORE detenido y colas 0, snapshot/revisión optimista y
patch únicamente del validador de esa copia; nunca reimportar el original ni
editar manifiestos de runs antiguos. Estos pasos necesitan el contexto y la
autoridad del operador; no están ejecutados aquí.

Solo después de gates e inventario válidos procede un run nuevo:
plan→apply→verify→test→verify→stop, con 200/422/503/timeout, hasta tres intentos,
cuatro DLQ, offsets 5/5/0 y conciliación terminal/provenance. Es la aceptación
de **ese ensayo RESTORE**; no un requisito nuevo para reabrir #14 ya aceptada
por PM. No usar el runner antiguo dirigido al original para eludir barreras.

## ML: implementación fusionada frente a aceptación pendiente

| Issue | Implementación/evidencia ya en main por #90 | Trabajo pendiente identificado |
|---|---|---|
| [CG34/#83](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/83) | Catálogo 50, 831 unidades, análisis preregistrado y añadido docente, paquete RF research y evaluación posterior del lote | Actualizar continuidad; conclusión/revisión humana y decisión del equipo sobre recomendación/defensa. No más fits para reproducir lo entregado. |
| [CG36/#85](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/85) | 21 configuraciones; 63 screening + 252 nested; CART, casos FN/FP, métricas y costes | Contraste/interpretación de reglas por la persona asignada y aceptación de criterios; las casillas siguen vacías. |
| [CG38/#87](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/87) | 2 EBM + 2 GAM, 12 screening + 48 nested; efectos y contribuciones locales/globales en explanations.json | Revisar unidades, casos TP/FN/FP y límites con una conclusión útil para la defensa; explicación del modelo no acredita causalidad ni explicación humana individual. |
| [CG39/#88](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/88) | 3 MLP + 10 rareza, 39 screening + 156 nested; FN recuperados/FP añadidos y alternativas condicionadas | Interpretar/aceptar límites y avisos. AE2 no converge al límite; se conserva el diagnóstico. Sin verdad independiente de anomalías; TabPFN/TabICL/AutoML/redes mayores no son cobertura ejecutada. |
| [CG40/#89](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/89) | 600 nested + 72 calibración; selección inner, recarga y recomendación conservar RF/0,15/0,70 | El comentario Niistal del 23/10 12:14Z cubre fuga/identidades/recarga; quedan interpretación Angiecrizu, dependencias #85/#87/#88 y conclusión final. No confundir revisión parcial con aceptación total. |

Las cinco issues están **OPEN** en la captura. Los cuerpos y comentarios
permiten distinguir implementación de aceptación; no se cerró ninguna.
Stacking/abstención están explícitamente no ejecutados, con motivo, en
`docs/evidence/CG34_EXPLORACION_20261023.md:223`; no son fits omitidos que deban
lanzarse automáticamente. Las 173 recargas y 27 avisos experimentales son
resultados históricos conservados (`:264`–`:286`), no nueva inferencia aquí.
El lote posterior aporta 2.000 únicos/5.070 emisiones; no multiplica la muestra
independiente ni acredita rendimiento HTTP o industrial.

**Verificación nueva de este revisor:** `LOG/verify_ml_evidence.py` pasa sin
importar estimadores: manifiesto/sello coincidentes; 5600/1200/1200 disjuntos y
cobertura 8000; todos los screening/outer dentro de train y cada inner particiona
su outer.fit; catálogo 50, 831 unidades únicas con estado complete. ZIP original
50.443.554 bytes, 5.350 entradas, SHA/CRC correctos y los 5.349 hashes del índice
verificados; ZIP docente 64 entradas con tamaño/SHA/CRC correctos. No se
recalcularon todos sus hashes internos ni métricas/modelos. Resultado en
`LOG/ml-evidence-verification.json`.

`.github/workflows/ml-study.yml:3`–`:8` se dispara por rutas research y permite
dispatch; `:24`–`:32` crea un entorno separado y ejecuta unittest + smoke
**sintético**. No evalúa AI4I, el lote real, throughput ni aceptación humana.
El pin uv 0.11.19 de main ya está tratado en #92: no crear otro refresh que
duplique esa PR. No se disparó workflow_dispatch en esta revisión.

## Comandos ejecutados y siguiente trabajo útil

Procesos PowerShell independientes con `login=false`, sin pwsh-warm. Collector
`LOG/collect.py`: `gh api` GET para PR/reviews/comments/files/check-runs/status,
issues/comentarios y main; `gh pr view --json ...`; `git cat-file`, `ls-tree`,
`merge-base`, `diff` y `show` sobre objetos ya presentes. `LOG/analyze.py`
clasifica blobs/rutas sin fetch, checkout ni escritura de refs. Lectura final
única mediante `LOG/final_readback.py`: once PR OPEN/heads sin drift y main exacta.

```powershell
py -3 D:/github/_local/t2-review-20261023/integration/probe_bundle.py
py -3 D:/github/_local/t2-review-20261023/integration/probe_project_sync.py
py -3 D:/github/_local/t2-review-20261023/integration/verify_ml_evidence.py
```

Los tres comandos terminaron exit 0; los dos primeros confirman defectos
esperados, no tests del producto superados. La verificación de los tres hashes
del bundle también terminó exit 0. Hubo un comando de presentación con
SyntaxError por quoting y búsquedas con glob Windows inválido/ruta inexistente;
se sustituyeron por scripts/paths exactos. No fueron pruebas del producto y no
se cuentan como validación. `capture-errors.json` está vacío.

Prioridad propuesta: **revisar el parche privado CG32 ya preparado y completar
el rescate puntual de Projects/F2**, reconciliar #73 y continuidad ML, y luego
revisar #92 sobre su head existente. La medición privada CG32 queda para la
fase operativa autorizada con candidato/entorno fijados; el bundle ya está
localizado. No invertir tiempo en reentrenar, rehacer el grafo aceptado o
fusionar íntegramente las PR históricas.

Preservación: HEAD y rama no cambiaron durante las capturas. El padre y otros
agentes escribieron simultáneamente documentos de rúbrica, workflow de revisión
y pruebas de bundle; se identifican como trabajo concurrente y se conservan.
Este revisor no los editó ni los incorporó a un commit. Este informe es una
revisión de alcance fijado, con los hallazgos anteriores; no es aprobación
global de seguridad, CI, operación, tutoría ni aceptación de producto.
