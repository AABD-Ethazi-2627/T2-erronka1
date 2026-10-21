# CG04 — evidencia de revisión (2026-10-21)

Código validado: `ca7162681482347640eab215accc82f8d6e275c2`, derivado exclusivamente
del head remoto PR43 `b2940bf88fc8d10d0397166f31706ad365a9c76f`.

Revisión atendida: [2026-10-21, comentario 6309526290](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/43#issuecomment-6309526290).
Se confirmaron las tres brechas antes de corregirlas. El import desde notebooks
ya estaba reparado. Los conteos 13/14/15 correspondían a estados anteriores;
esta evidencia los sustituye para el código indicado.

- Entorno nuevo: Python 3.12.14, `uv sync --frozen --python 3.12 --group notebook`: OK.
- `uv lock --check`: OK.
- `uv run --locked python -m pytest -q`: **27 passed**, sin warnings, 32.09 s.
- Kernel cnc-guard registrado dentro de .venv; argv apunta al Python del proyecto.
- nbconvert ejecutó todas las celdas desde notebooks sin PYTHONPATH, con ese
  kernel, y guardó `.venv/cg04-executed.ipynb`: OK, sin warnings tras añadir IDs.
- Reejecución con modelo existente: FileExistsError; SHA-256 sin cambios.
- Paridad de columnas, transformación del Pipeline y predicción sin target:
  cubierta por regresión. Rangos, no finitos, tipos, columnas ausentes/extras,
  etiquetas y campos temporales: rechazo controlado con ValueError.

Notebook: 8.000 filas, seis predictores, división estratificada 6.400/1.600,
RandomForest 200 árboles, class_weight=balanced, semilla 42, accuracy **0.97875**.
Dependencias y versiones exactas en uv.lock. Modelo local ignorado por Git;
ningún artefacto binario se publica. La cuota de /tmp bloqueó inicialmente
instalación y exportación; el flujo final se verificó en /home y exporta a .venv.

Justificación Python/G52, módulos/G55, instrucciones del kernel y frontera
CG03/CG28: [CG04_ENVIRONMENT](../docs/CG04_ENVIRONMENT.md).
PR42 consultada en `28a77543bfd67a36b96ddc2f4acc103b13f62c2e`; no modificada.
No se completa CG28 ni se valida el sobre de telemetría en esta PR.
La accuracy es de desarrollo sobre AI4I simulado: sin evaluación final independiente,
sin predicción temporal, sin operación industrial. Revisión por otro miembro
humano y aceptación de rúbrica pendientes. No merge ni cierre de #4.
