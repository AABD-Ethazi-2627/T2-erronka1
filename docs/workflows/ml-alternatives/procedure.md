# Exploración ML de CNC Guard

Fuente normativa del experimento: issue #83 y sus comentarios actuales; #84–#89
contienen entregables. Antes de reanudar, comprobar main remoto, worktree limpio
o cambios propios conocidos, procesos activos y `state.md`. Nunca repetir una
unidad con resultado o estado incierto sin inspeccionarla.

1. Leer políticas globales del host y AGENTS aplicables. Inventariar hardware,
   cargas, espacio, herramientas y bibliotecas; no cambiar configuración del host.
2. Resolver `scripts/ml_study_requirements.in` en el lock research separado.
   Crear un venv propio; API, `pyproject.toml` y `uv.lock` permanecen separados.
3. Ejecutar `python -m unittest discover -s tests/research -v` y
   `python -m scripts.ml_study smoke --output <raíz-sintética-nueva>`.
4. Sellar con `python -m scripts.ml_study seal --output <raíz-estudio-nueva>
   --smoke <raíz-sintética>/smoke.json`. No inspeccionar scores nuevos antes del
   sellado. El runner verifica fuente, particiones, código y entorno al reanudar.
5. Ejecutar `python -m scripts.ml_study run --output <raíz> --phase pilot`.
   Comparar CPU/GPU sobre iguales filas/parámetros. Resultados diferentes no son
   un error de recarga: implementaciones distintas no prometen scores idénticos.
6. Ejecutar fases `screening`, `nested`, `calibration`, `package`, secuencialmente.
   El núcleo prefijado se completa antes de ampliar la auditoría; el screening
   no modifica ese núcleo. No transferir presupuestos entre etapas.
7. `python -m scripts.report_ml_study --output <raíz> --destination <informe-nuevo>`
   solo lee scores guardados. Auditar las tablas A/B, estados, discrepancias,
   costes hipotéticos, incertidumbre y compatibilidad antes de recomendar.
8. Versionar evidencia compacta y conservar scores, modelos y logs con hashes.
   Actualizar issues con criterio → commit/artefacto → comando → resultado →
   límite → revisión. Publicar PR revisable y registrarlo en T3; no hacer merge
   ni alterar modelo servido. Revisión propia e independiente son estados distintos.

Cada proceso ajusta una sola unidad. Límites de RAM/VRAM/tiempo y CPU acumulada
se fijan en el manifiesto. La contabilidad CPU muestrea todo el árbol y añade un
margen por la cola no observada; GPU contabiliza conservadoramente toda la vida
del proceso que solicita CUDA, aunque parte transcurra en CPU/importación.
La latencia warm de batch1 es en proceso, sin HTTP, concurrencia ni grafo E2E.
Los avisos de convergencia se conservan como diagnósticos, no se suprimen.

Si hay interrupción, un directorio de unidad sin `accounting.json` exige inspección
manual. Los resultados completados se verifican por hash, nunca se sobrescriben.
Un cambio de código sellado exige otra versión/raíz: no retocar un experimento ya
observado para presentarlo como preregistrado. No puntuar validación ni test excluido.
