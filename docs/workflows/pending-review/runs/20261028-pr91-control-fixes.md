# PR91: correcciones del control del laboratorio — 28/10/2026

Revisión de partida: `0fdf7efdbe176af05bf7c315ba10fa4776305bc9`.
[Hallazgos independientes F1–F4](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/91#pullrequestreview-5682305250).
Alcance autorizado: laboratorio/productor, pruebas y documentación. La reparación
de CI, imágenes y dependencias corresponde a otro agente. Sin autoaprobación,
merge de la PR, servicios compartidos, campaña nueva ni cambios del bundle o umbrales.

## Cambios

- F1 (P2): el controlador usa un `Future`; su excepción llega al hilo principal.
  STOPPED/RUNNING se comprueban consultando NiFi, y SIGKILL debe devolver éxito
  antes del plazo de 30 s. La cancelación por presupuesto no acredita una
  inyección no realizada. El cleanup espera al controlador, conserva el error
  principal y guarda las observaciones y la oferta parcial.
- F2 (P2): reserva exclusiva de `run.json` con identidades planeadas antes de la
  preparación; registro en `state.runs` antes de crear recursos externos.
  Actualizaciones atómicas del recibo y callback de las identidades NiFi antes
  de descubrir/validar sus procesadores. Los fallos de topic, índice, parada de
  grupos o upload dejan recibo fallido; solo se paran servicios intentados.
- F3 (P2): presupuesto antes de la primera fila y comprobación cooperativa antes
  de cada escritura, también tras la espera de temporización. Las consultas de
  disco se separan al menos 0,5 s y lag usa las muestras de 2 s; la parada es
  cooperativa. La oferta devuelve los registros
  escritos, incluidos cero; la reconciliación y métricas admiten esa oferta vacía.
- F4 (P3): `container_mem_usage_max_mib` nombra el máximo muestreado de Docker
  CLI `MemUsage`, con caché descontada en Linux. Se aclara el campo histórico
  `rss_max_mib` en la documentación. Ningún JSON/ZIP crudo de campaña se reescribe
  ni se presenta como nueva medición.

## Validación local

Intérprete existente `D:/cnc-guard-pr91-20261027/Scripts/python.exe` (Python 3.11).
TEMP/TMP, pycache, caché Ruff y evidencia de esta ejecución en
`D:/reviews/pr91-fixes-20261028/`. No se instalaron dependencias.

Comandos ejecutados desde el checkout administrado por T3:

```text
python -m pytest -W error -q -p no:cacheprovider --basetemp=D:/reviews/pr91-fixes-20261028/verified-tmp --junitxml=D:/reviews/pr91-fixes-20261028/verified.xml
718 passed, 14 skipped, 361 subtests passed; exit 0
python -m unittest discover -s tests -v
Ran 430 tests; OK (skipped=14); exit 0
python -m scripts.audit_cg02 --check
CG02 inventory verified offline; exit 0
python scripts/check_repository_layout.py
Repository layout OK; exit 0
ruff check scripts/cg32_lab.py scripts/cg32_load.py tests/test_cg32_control.py tests/test_cg32_cleanup.py tests/test_cg32_load.py tests/test_cg32_observability.py
All checks passed; exit 0
python scripts/check_cg25_memory.py
PASS: 40 criteria, 90 local links/anchors, 241 current and 18 historical hashes; exit 0
git diff --check
exit 0
```

Los 14 skips de pytest son siete controles POSIX/O_NOFOLLOW en Windows, tres
consultas ES opt-in, tres pruebas que requieren el bundle de entrenamiento y una
rotación TLS opt-in. No equivalen a aceptación de esas rutas. La suite usa sus
fixtures temporales propios; no se cargaron pickles aportados externamente.

La primera ejecución general se interrumpió por el límite de 60 s del ejecutor;
no se contó como aprobada. Se amplió el plazo a diez minutos. Una pasada posterior
del candidato previo dio 717 pruebas aprobadas; los 718 anteriores corresponden
a la revisión final con la regresión adicional del upload parcial.

La revisión local del diff y las regresiones resuelven F1–F4 en este alcance;
no sustituyen una revisión independiente del nuevo SHA, CI ni aceptación humana.
Los hashes CG25 se actualizan solo en entradas vivas de archivos modificados;
el snapshot histórico y los crudos de campaña se conservan. El estado remoto
se consulta y reconcilia antes de publicar, sin force-push.

Los logs completos, JUnit y el recibo final con SHA quedan en el directorio de
evidencia exclusivo indicado arriba. El estado remoto exacto se informa en el
handoff, sin atribuir a este cambio los checks de otro SHA.

## Reconciliación antes del push

La comprobación remota detectó el commit concurrente de CI
`ea6cf843f0a81e16f2a7f8e3b1b7c49b7f00616f`. Se integró sin conflictos. Frente a
ese commit, los workflows, imágenes, gate y test del gate quedan idénticos.
Sobre su manifiesto se conservaron todos los hashes ajenos y se comprobaron
solo las tres entradas vivas propias (laboratorio, protocolo y aclaración de
campaña); no cambió el snapshot histórico ni ningún crudo archivado.

El árbol combinado repitió pytest: **718 passed, 14 skipped, 361 subtests passed**
(60,41 s, exit 0), y unittest: **430 tests, OK (skipped=14)** (46,71 s, exit 0).
CG25 pasó con **40 criterios, 90 enlaces, 260 hashes vivos y 18 históricos**.
Logs `merged.log`, `merged.xml`, `merged-unittest.log` y `merged-cg25.log` en el
directorio exclusivo de evidencia. Los tiempos corresponden a estas ejecuciones
locales, no a una campaña de rendimiento ni al CI remoto.
