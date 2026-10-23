# Revisión de requisitos y evidencia pendiente — 23/10/2026

Revisor: agente documental, sin delegación adicional. Ámbito: las 11 issues
abiertas, 40 criterios de rúbrica, planificación y aceptación; cambios limitados
a `docs/rubrica/*`, `docs/planificacion/*` y este informe. Sin commit, push,
comentarios, cierres, merge, servicios compartidos, SMB ni red OT.

## Base, fuentes y método

- Checkout compartido: `D:/github/AABD-Ethazi-2627/B-taldea`, rama
  `review/pending-20261023`, HEAD/base exacta
  `5005ccde81f16cd2deac6ee3b30085d773e0fc88`, árbol
  `bc532b8a0f76a4ec15bfed278b0217eac84663f6`.
- `gh api repos/AABD-Ethazi-2627/T2-erronka1` confirma el nombre canónico;
  `origin` conserva la URL antigua `AABD-Ethazi-2627/B-taldea.git`.
- [Fuente exacta](../rubrica/fuente.json): copia local del Excel, hoja Zereginak,
  40 descriptores G; SHA-256 de origen registrado
  `e3e05d6fe408e163f6f8247cd7054f2a4ce4de6aa5757048ba432cd682139463`.
  No se ha confirmado versión online con el docente ni se altera su texto.
- Se leyeron `unslop`, `review-quality`, `quality-core`, `workflow-records` y
  `code-quality`; instrucciones globales suministradas y ausencia de AGENTS.md
  adicionales en las rutas examinadas. No se aplica política MKDL por autoría.
- Procedimientos consultados: [revisión de pendientes](../workflows/pending-review/procedure.md),
  [grafo automático](../workflows/automatic-graph/procedure.md) y su
  [ejecución anterior](../workflows/automatic-graph/runs/20261022.md),
  [estudio ML](../workflows/ml-alternatives/procedure.md) y
  [lote](../workflows/ml-alternatives/runs/20261023-batch.md).
  Se inspeccionaron los informes/artefactos de esta base; no se reejecutan sus
  entrenamientos, inferencias o laboratorios por leer sus resultados.

## Hallazgos y correcciones documentales

1. **IMPORTANT, confirmado: estados históricos presentados como actuales.**
   `docs/rubrica/SEGUIMIENTO.md` encabezaba «corte documental actual 22/10» y
   conservaba #24 abierto/revisión normativa pendiente; su añadido CG20 indicaba
   #20 abierto. `ESTADO_20261022.md` mantiene #10/#11 y otras issues abiertas,
   con grafo/integración aún pendientes al corte. GitHub confirma cierre de #10,
   #11, #20 y #24 el 23/10; #25 ya estaba cerrado el 22/10. Se añade el
   [corte actual](../rubrica/ESTADO_20261023.md), enlazado desde el índice, y se
   explicita la precedencia de decisiones PM posteriores. Los informes sellados
   y sus cuatro hashes CG25 permanecen intactos.
2. **IMPORTANT, confirmado: planificación original incompleta para el estado
   restante.** El plan solo recogía CG01–CG30 y 86,5 persona-días brutos
   originales. La [actualización de planificación](../planificacion/README.md#seguimiento-restante-del-23102026)
   recoge las 11 issues vigentes y separa ese total histórico del esfuerzo restante
   aún sin medir. No cambia el JSON original ni el Project remoto.
3. **NOTE, límite académico verificable.** No consta en las fuentes inspeccionadas
   una respuesta docente que confirme versión/pesos, interpretación G49/G62 ni
   canal/hora/modalidad efectivos de entrega. [Registro preparado CG33](../rubrica/ACLARACIONES_20261023.md)
   incluye pregunta, evidencia, propuesta, responsable y estado PENDIENTE; no se
   ha enviado ni rellenado por el docente. Las equivalencias SMB/worker ya
   aceptadas PM se conservan.
4. **NOTE, límite humano confirmado.** La aceptación técnica/documental PM
   sustituye reservas genéricas de revisión de issues cerradas. No sustituye la
   explicación real de cuatro personas, ensayo, defensa ni entrega que mantienen
   abiertas #37/#26/#27. El [acta existente](../demo/ACTA_PENDIENTE_20261022.md)
   sigue sin celebrar; se conserva intacta, con su fecha histórica.
5. **NOTE, evidencia ML actualizada.** #90 está integrada en la base; #84 y #86
   están cerradas. Las frases «integración pendiente» de informes/comentarios ML
   previos son históricas. Ya existen screening/nested, explicaciones y lote
   adicional; no falta ejecutar de nuevo la búsqueda para empezar su revisión.
   #85/#87/#88/#89 aún requieren las interpretaciones/decisiones concretas de
   sus responsables. Se conservan 27 avisos del estudio, entre ellos AE2 sin
   convergencia; no se declara que todos los candidatos convergieron.

La matriz nueva contiene exactamente las 40 celdas, con objetivo/origen,
artefacto inmutable y comando documental, resultado/límite, aceptación/alcance,
responsable y fecha. No asigna una nota ni acepta #80 en nombre de sus responsables.
La fuente y las evidencias selladas siguen siendo el registro de sus ejecuciones.

## Acciones restantes por issue

Consulta remota de estados/comentarios el 23/10/2026; corte base conservado.
Cada estado abierto es un hecho remoto, no una recomendación automática de cierre.

| Issue / estado | Evidencia ya disponible | Acción restante realizable y dependencia humana | Responsable / fecha objetivo |
|---|---|---|---|
| [#80 CG31, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/80) | Corte nuevo 40/40, registro de aceptaciones por enlace y checks documentales de esta revisión | Revisar/aceptar esta propuesta local; reconciliar después de ensayo/cambios finales. El agente no cierra la issue | Angiecrizu, tears-mysthrala; 26/10 y 05/11 |
| [#82 CG33, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/82) | Preguntas/alternativas/fuentes y campos pendientes preparados en el registro CG33 | Portavoz canaliza consulta; registrar respuestas o ausencia explícita, autor/fecha/evidencia/efecto. Confirmar versión/pesos, G49/G62 y canal/hora/defensa; no respuesta inventada | petiteiker, Angiecrizu; soporte Niistal/tears-mysthrala; 27/10 |
| [#37 CG30, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/37) | Comparación conceptual, decisiones técnicas, ampliación research y preguntas de defensa | Los cuatro explican entrada/modelo/alerta/decisión humana, error/límite y pregunta fuera de especialidad; registrar personas/fechas/conclusión reales. Más texto/modelos no completa aprendizaje | tears-mysthrala contenidos, Angiecrizu registro, los cuatro participan; 28/10 y 05/11 |
| [#81 CG32, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/81) | Protocolo remoto; E2E #20 aceptado con dobles; microbenchmark #23 aceptado aparte. [Padre: identidad/copia del bundle original](PENDING_BUNDLE_20261023.json), evidencia local concurrente fuera del SHA base | Con presupuesto y lab propios acordados, ejecutar piloto/carga viable con bundle exacto, repetir tres veces, medir inferencia/HTTP/E2E/lag/CPU/RSS/bytes, sets de IDs y recuperación; publicar observado aunque falle meta. No declarar capacidad con el doble ni sustituir bundle por reentreno | petiteiker carga; Niistal grafo; tears-mysthrala identidad; viabilidad 27/10, informe 30/10 |
| [#83 CG34, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/83) | 831 unidades train, 50 configuraciones, 173 recargas declaradas; lote posterior sin ajustes; RF recomendado. Código/agregados integrados #90 | Consolidar interpretaciones #85/#87/#88/#89 y decisión atribuida de conservar RF; separar estudio, lote, bundle servido y carga. No repetir fits sellados ni usar test excluido | tears-mysthrala, Angiecrizu; 03/11 |
| [#85 CG36, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/85) | 21 configuraciones: 63 screening +252 nested; tablas, dummies, ablaciones y CART en `CG34_20261023/explanations.json` | Contrastar checklist con tablas/reglas y explicar FN/FP/rendimiento/complejidad; interpretar avisos QDA sin ocultarlos. Aceptación de responsables pendiente, ejecución disponible | tears-mysthrala, Angiecrizu; 27/10; #84 cerrada |
| [#87 CG38, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/87) | Cuatro EBM/GAM: 12 screening +48 nested; efectos/global/local y log-odds en `explanations.json` | Revisar interpretación con unidades/ejemplos TP/FN/FP y si claridad compensa coste; trasladar síntesis a defensa sin causalidad industrial inventada | Angiecrizu, tears-mysthrala; 28/10; #84 cerrada |
| [#88 CG39, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/88) | 13 configuraciones: 39 screening +156 nested; umbrales rareza inner; FN recuperados/FP añadidos; AE2 sin convergencia conservado | Confirmar interpretación de normal-proxy, presupuesto de avisos y alternativas condicionadas/no ejecutadas. Stacking/abstención no ejecutados; no declarar verdad de anomalía ni otro IF servido | tears-mysthrala, petiteiker; 29/10; #84 cerrada |
| [#89 CG40, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/89) | Nested/calibración, recargas, costes y decisión research; [Niistal: parte fuga/identidad/recarga](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/89#issuecomment-6364629784) ya registrada | Completar #85/#87/#88 e interpretación de Angiecrizu; contrastar materialidad/coste y conservar RF/0,15/0,70. #86 cerrada. Promoción, paquete compatible, CI e integración operativa serían pasos separados, sin asumir que se necesitan | tears-mysthrala, Niistal, Angiecrizu; 03/11; candidato listo 04/11 o RF |
| [#26 CG26, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/26) | Guion y justificación de panel aceptados PM; ensayo histórico API propio e indicaciones 200/replay/409/422/503 | Realizar ensayo/defensa de 4/4, caso válido trazado, rechazo, recuperación y decisión simulada; acta solo después. Recibo solo tras entrega; no falta otra aceptación PM genérica | Angiecrizu coordina; participan los cuatro; 05/11; defensa objetivo 06/11 |
| [#27 CG27, OPEN](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/27) | Índice/memoria/ANEXO4 preparados; nuevo corte y planificación; feedback PM enlazado | Fijar SHA/árbol del paquete final y pendientes, completar explicación/ensayo, confirmar canal/hora/modalidad con #82; efectuar entrega y archivar justificante real. Sin firma/Moodle/nota inventados | Equipo; petiteiker canal, Angiecrizu paquete/recibo; objetivo 06/11 sin hora confirmada |

## Decisiones remotas que sustituyen reservas históricas

| Issue | Estado/fecha remota verificados | Decisión y alcance |
|---|---|---|
| #10 | CLOSED, 23/10 06:18:04Z | [Aceptación PM](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/10#issuecomment-6358780983), PR78 integrada `92c9c363…`; coherencia CSV/métricas/costes resuelta |
| #11 | CLOSED, 23/10 06:18:10Z | [Aceptación PM](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/11#issuecomment-6358782365), hito CG02–CG10; sin reproducción humana añadida |
| #20 | CLOSED, 23/10 06:30:18Z | [Aceptación PM](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/20#issuecomment-6358954102), PR79 `77ff3063…`; mismo evento hasta panel, dobles sintéticos |
| #24 | CLOSED, 23/10 06:51:44Z | [Aceptación PM](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/24#issuecomment-6359264997), PR77 `41cb66f0…`; análisis normativo aceptado, sin conformidad/certificación académica o industrial |
| #25 | CLOSED, 22/10 13:34:27Z | [Aceptación PM documental](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/25#issuecomment-6342076669); no acredita defensa o entrega |
| #84 | CLOSED, 23/10 11:45:34Z | [Revisión registrada Niistal](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/84#issuecomment-6363876786), protocolo/folds/smoke; #90 ya integrada en base |
| #86 | CLOSED, 23/10 12:14:34Z | [Cierre Niistal](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/86#issuecomment-6364627006), boosters y decisión de no promoverlos |

Las aceptaciones de SMB, NiFi/worker, API, ES, panel, archivo y microbenchmark,
con sus enlaces/fechas/alcances, están en la
[tabla PM de la matriz](../rubrica/ESTADO_20261023.md#aceptaciones-y-alcances).
La [evaluación global de targets en #27](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/27#issuecomment-6359282684)
permanece referencia de planificación, sin convertir metas de ingeniería en requisitos docentes.

## Comprobaciones de esta revisión

Ejecutadas desde este checkout con PowerShell `login=false`, procesos separados,
sin `pwsh-warm`. Python documental: `py -3`, 3.12.10, modo `-B` para no crear
bytecode. Los scripts elegidos usan biblioteca estándar; no se instala ni altera
el entorno del proyecto.

| Comando / comprobación | Resultado propio |
|---|---|
| `git branch --show-current`, `git rev-parse HEAD`, `git rev-parse 'HEAD^{tree}'`, `git remote -v`, `git status --short` | Rama/base/árbol anteriores; cambios concurrentes del padre identificados y preservados |
| `gh api repos/AABD-Ethazi-2627/T2-erronka1/commits/main --jq .sha` | Base exacta confirmada antes y durante edición |
| `gh issue list --repo AABD-Ethazi-2627/T2-erronka1 --state open --limit 100 --json number,title,state,body,updatedAt,assignees,url` | Exactamente 11 abiertas, enumeradas arriba |
| `gh issue list --repo AABD-Ethazi-2627/T2-erronka1 --state all --limit 100 --json number,state,closedAt,title` | Cierres actuales contrastados, incluidos #24/#84/#86 |
| `gh api graphql -f query=<consulta issues/comments>` | Lectura de decisiones PM, feedback y revisiones enlazadas, sin escrituras remotas |
| `py -3 -B scripts/check_cg25_memory.py` antes de editar | PASS: 40 criterios, 90 enlaces/anchors, 191 hashes actuales y 18 históricos |
| `py -3 -B -m scripts.check_cg20_same_event` | PASS: ID `279947a017e5d70adba2a83e5eb319c0c7495260ebac7259de1954bb834c6b8b`, HTTP=ledger=worker=ES, panel/Discover, filtro negativo y 5=4+1+0 |
| `py -3 -B scripts/check_cg25_memory.py` después de editar | PASS: 40 criterios, 90 enlaces/anchors, 191 hashes actuales y 18 históricos; sin alterar manifiesto |
| Auditor stdlib mediante `py -3 -B -c <código inferior>` | PASS: 40/40 filas completas, 129 enlaces/anchors locales en cinco ficheros, 18 evidencias idénticas a blobs de la base y cinco ficheros sellados intactos; referencia del manifiesto del bundle coincide con CG26 |
| `git diff --check` | Exit 0, sin errores; los tres Markdown nuevos también se comprobaron para espacios finales mediante el auditor |

Auditor complementario reproducible desde la raíz, con `py -3 -B -c` y este
código en un here-string de PowerShell. Solo lee archivos y objetos Git:

```python
import json, re, subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit
from scripts.check_cg25_memory import anchors

root = Path.cwd().resolve()
base = "5005ccde81f16cd2deac6ee3b30085d773e0fc88"
names = ["docs/rubrica/README.md", "docs/rubrica/ESTADO_20261023.md",
         "docs/rubrica/ACLARACIONES_20261023.md", "docs/planificacion/README.md",
         "docs/evidence/PENDING_REQUIREMENTS_20261023.md"]
source = json.loads((root / "docs/rubrica/fuente.json").read_text(encoding="utf-8"))
expected = {"Zereginak!" + item["advanced_cell"] for item in source["descriptors"]}
state = (root / names[1]).read_text(encoding="utf-8")
rows = re.findall(r"^\| (Zereginak!G\d+) \| (.+)$", state, re.M)
assert len(rows) == 40 and {cell for cell, _ in rows} == expected
for cell, row in rows:
    fields = [item.strip() for item in row.rstrip("|").split("|")]
    assert len(fields) == 6 and all(fields), cell
    assert fields[0].startswith("L:"), cell
    assert re.search(r"E\d{2}", fields[1]) and re.search(r"P\d+", fields[2]), cell
links = 0
for name in names:
    path = root / name
    data = path.read_text(encoding="utf-8")
    assert all(line.rstrip() == line for line in data.splitlines()), name
    for target in re.findall(r"\]\(([^)]+)\)", data):
        parts = urlsplit(target)
        if parts.scheme or parts.netloc:
            continue
        linked = (path.parent / unquote(parts.path)).resolve() if parts.path else path
        assert linked.is_relative_to(root) and linked.is_file(), (name, target)
        if parts.fragment:
            assert linked.suffix == ".md", (name, target)
            assert unquote(parts.fragment) in anchors(linked.read_text(encoding="utf-8"))
        links += 1
prefix = "https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/" + base + "/"
paths = re.findall(r"^\| E\d{2} \| \[[^\]]+\]\(" + prefix + r"([^\)]+)\)", state, re.M)
assert len(paths) == 18
protected = ["docs/rubrica/SEGUIMIENTO.md", "docs/rubrica/ESTADO_20261022.md",
             "docs/rubrica/OBJETIVOS_Y_ETAPAS.md", "docs/rubrica/fuente.json",
             "docs/memoria/manifest.json"]
for name in paths + protected:
    assert subprocess.check_output(["git", "show", f"{base}:{name}"]) == (root / name).read_bytes(), name
bundle = json.loads((root / "docs/evidence/PENDING_BUNDLE_20261023.json").read_text())
cg26 = json.loads((root / "docs/evidence/CG26_REHEARSAL_2026-10-21.json").read_text())
assert bundle["sha256"]["manifest.json"] == cg26["manifest_sha256"]
print(f"PASS: 40/40 rows; {links} local links/anchors; 18 evidence blobs; 5 sealed files; bundle reference")
```

Una consulta inicial demasiado grande de cuerpos/comentarios GitHub quedó
truncada y no se usó como fuente completa; se repitió con selección acotada de
campos/comentarios y parseo correcto. Una búsqueda de `explanations.md` no encontró
archivo; el artefacto real es `CG34_20261023/explanations.json`, inspeccionado.

## Límites y traspaso

No se ejecutaron nuevas suites ML/API, entrenamiento, inferencia, HTTP vivo,
Kafka/NiFi/ES, carga, SMB, migraciones, despliegue, envío de consultas o entrega.
Los dos checks offline anteriores verifican documentación/evidencia guardada;
no reproducen el laboratorio ni acreditan CI de estos cambios.

El padre ha añadido evidencia local de identidad/copia del bundle histórico;
este agente solo contrastó su referencia con el registro CG26 y no ejecutó
la carga. La integración/rendimiento de ese bundle requiere su validación propia.
Los avisos experimentales conservan su severidad/confianza originales; esta
revisión no aplica un gate MKDL de cero hallazgos a un repositorio educativo.

Ficheros propios: `docs/rubrica/README.md`, `ESTADO_20261023.md`,
`ACLARACIONES_20261023.md`, `docs/planificacion/README.md` y este informe.
No se editan fuente.json, texto docente, manifiesto CG25, informes sellados,
acta ni archivos de otros agentes. Sin commit en el checkout compartido.
