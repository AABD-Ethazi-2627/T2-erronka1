# CG40: auditoría de ejecución reproducida el 26/10/2026

Parte Niistal de #89, base `aa38a7d5effddc0bff21d009a5266b6a9334769d`.
Amplía la auditoría de particiones de #96. **Corrección del límite anterior:**
#90 sí publica `CG34_20261023/raw-evidence.zip`, que contiene tareas, scores,
contabilidad y bytes de modelos. No hace falta pedir el archivo privado para
estas comprobaciones. Esto no aporta el bundle operativo que requiere #81.

## Procedimiento ejecutado

1. Comparar SHA-256 del ZIP con `CG34_20261023/archive.json`: coincide,
   `640d75114324df4d8bafa20461cccf20da3850552c3bd6fa48080b9584e97896`.
2. Inspeccionar las rutas y rechazar enlaces simbólicos o escapes; extraer en
   directorio nuevo de `/tmp`, separado del checkout. Comprobar CRC de todas
   las entradas. No ejecutar código del ZIP ni deserializar modelos.
3. Ejecutar el auditor existente del repositorio con Python estándar:

```bash
python -m scripts.audit_ml_study \
  --root <extraccion-aislada> \
  --summary <extraccion-aislada>/analysis-v2/summary.json \
  --destination <resultado-nuevo.json>
```

4. Contrastar además las listas completas `fit` y `held` de cada tarea inner,
   outer y calibración con el fold exacto del manifiesto sellado. La comparación
   incluye orden, no solo pertenencia; sin leer datos de validación/test.

Comprobación adicional reproducible (sustituir la ruta de extracción):

```python
import json
from collections import Counter
from pathlib import Path

root = Path("<extraccion-aislada>")
manifest = json.loads((root / "manifest.json").read_text())
counts = Counter()
for path in (root / "units").glob("*/task.json"):
    task = json.loads(path.read_text())
    phase = task["phase"]
    if phase not in {"inner", "outer", "calibration_inner", "calibration_outer"}:
        continue
    fold = task["fold"]
    expected = manifest["outer"][fold[0] if isinstance(fold, list) else fold]
    if phase.endswith("inner"):
        expected = expected["inner"][fold[1]]
    if any(task[key] != expected[key] for key in ("fit", "held")):
        raise ValueError(f"Task differs from sealed fold: {path.name}")
    counts[phase] += 1
print(dict(counts))
```

[Resumen y procedencia](CG40_EXECUTION_AUDIT_20261026/summary.json), incluido
hash del auditor y del resultado completo de esta reproducción. Los 5.163
hashes detallados son regenerables con el comando; se publica el agregado
para evitar duplicar el índice ya disponible en #90. El directorio temporal
local de esta ejecución es `/tmp/cg40-execution-audit-a3bbpcrw` y no es un
requisito portátil de reproducción.

## Resultados reales

- Sello del manifiesto correcto: `d881aa24…`; código sellado y 5.163 entradas
  de evidencia verificadas por bytes, incluidos los modelos como archivos.
- 40 modelos supervisados: matriz TP/FP/FN/TN y coste por 1.000 recalculados
  para corte optimizado y políticas 0,15/0,70; AP con empates recalculada.
  Población outer completa de 5.600 filas por modelo; no son test independiente.
- Correspondencia exacta de tareas: 450 inner + 150 outer, y 54 inner de
  calibración + 18 outer de calibración. La auditoría rechaza fuga declarada
  y scores desalineados respecto al held de cada tarea.
- Contabilidad archivada: 831 unidades `complete`, 10 `complete_analysis`,
  2 `complete_reserve`, 1 `complete_preflight`. Presupuestos comprobados:
  CPU screening 716,04 s, nested 2.857,98 s, secondary 262,87 s,
  benchmark 1.175,23 s; GPU 138,81 s; RSS muestreado máximo 856.993.792 bytes.
  Son consumos históricos contrastados, no consumo de esta auditoría.
- CRC correcto en 5.350 entradas. Descomprimido observado: **164.309.031 bytes**.
  `archive.json` registra 163.236.931: diferencia de 1.072.100 bytes en ese
  metadato. El SHA-256 completo sí coincide; no se cambia ni vuelve a sellar
  el histórico. No se presenta ese campo de tamaño como reconciliado.
- 27 avisos históricos conservados: 26 `UserWarning` y 1 `ConvergenceWarning`.
  El resultado PASS no significa ausencia de avisos. No se silencian ni se
  consideran un experimento nuevo.

## Alcance y cierre

Esta ejecución verifica evidencia archivada, no vuelve a ajustar estimadores,
calibradores, umbrales ni un modelo servido. Los resultados de recarga nativa
siguen atribuidos a la ejecución original: aquí se comprueban bytes y el valor
archivado de tolerancia, sin `joblib.load`. Tampoco se demuestra que ningún
proceso accediera jamás a datos fuera de los declarados; se auditan registros,
proveniencia y consistencia disponibles.

Revisión de esta reproducción: **SELF_REVIEW / NOT_INDEPENDENT**, principal
Codex gpt-6.1-sol; no se atribuye a otra persona ni a Luna/Claude. La aprobación
humana de #96 pertenece a su alcance previo, no aprueba automáticamente este
informe. Mantener #89 abierta: #85/#87/#88 y decisión/interpretación conjunta
siguen pendientes. No cambiar responsables ni sus entregables. #81 continúa
requiriendo el bundle original operativo y mediciones reales; RF research no
lo sustituye. No se promueve ningún candidato.
