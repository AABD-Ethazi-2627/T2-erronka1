# Estado de publicación de ramas locales — 26/10/2026

## Alcance y resultado

Encargo: revisar las cinco ramas locales, publicar y abrir PR de las aptas;
investigar qué falta en las restantes. Sin autorización ni operación de merge
remoto, despliegue, cierre de issues o cambio de infraestructura compartida.

Se actualizaron referencias mediante `git fetch --all --tags`. Base remota:
`5005ccde81f16cd2deac6ee3b30085d773e0fc88`. Los cuatro worktrees estaban limpios.
No se modificaron sus fuentes ni se cambiaron sus HEAD. Este registro y su fila
de índice se añaden localmente a la rama consolidada, sin commit ni publicación.

| Rama | HEAD | Disposición |
| --- | --- | --- |
| `kali/ml-alternatives-kalista-study` | `3a5c3cf4d318ba254b8d461b9a03a8242bb32bd3` | Ya publicada e integrada en main por PR90; no necesita otra PR. |
| `kali/review-and-fix-validation` | `b02e620edc732ee1758d40a377f98bbdad65c3b6` | Publicada con upstream y PR95 en esta ejecución. |
| `kali/review-composition-findings` | `0ab771d7867315d2aa85776cb16b1bf7bfdbb048` | Composición antigua; no publicar como candidato vigente. El arreglo Windows ya está publicado por separado en PR92, commit `82ae770`. |
| `review/cg32-bundle-identity-20261023` | `4a6e01a6004e87cc156d3a3944625e82a0855616` | Guard de identidad sellada útil y probado, pero basado en CG32 anterior a sus correcciones remotas; falta integrarlo con la PR91 actual. |
| `review/pending-20261023` | `06510ad85c4e3d392d6e9e9f255a7ae8c57ab23c` | Contiene las otras cuatro ramas; conserva 20 commits sobre main. No se publica su composición antigua. |

## Publicación realizada

[PR95](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/95), base `main`,
head `b02e620edc732ee1758d40a377f98bbdad65c3b6`:
`test: corregir fixture RPM para valores no finitos`.
Solo cambia a float la columna RPM de una fixture antes de asignarle `np.inf`.

- En su propio worktree y con el entorno research existente de Python 3.12.10:
  22 pruebas con `-W error`, exit 0.
- Smoke de los 50 adaptadores con datos sintéticos: todos completos,
  todos con `warnings: []`, exit 0. No se repitió el estudio ML sellado.
- `uv pip check`, `actionlint`, CG02, estructura y diff pasan.
- Push con `git push -u origin kali/review-and-fix-validation`, exit 0.
- El conector GitHub rechazó crear la PR con 403
  `Resource not accessible by integration`. Se creó mediante la sesión `gh`
  existente y se vinculó a este hilo T3.
- Lectura de CI posterior a la creación: `synthetic-research`, `paths` y `test`
  en SUCCESS. `mergeable=MERGEABLE`, `reviewDecision=REVIEW_REQUIRED`,
  `mergeStateStatus=BLOCKED`. No se fusionó ni se solicitó una aprobación propia.

## Qué falta en las composiciones antiguas

Hallazgo IMPORTANT, confianza alta: las ramas auxiliares de composición y la
consolidada no contienen las correcciones remotas posteriores. El hecho de que
pasen sus tests actuales no demuestra cobertura de esas correcciones.

1. **CG32:** incorporar la PR91 actual, head
   `b8b4ff5a8e71aac77603f0fb0d7e9a9653b5e170`.
   Faltan, entre otros, `45eeb11` (certificado NiFi fijado), `ef9685b`
   (contención de rutas y conservación de fallos) y `b8b4ff5`
   (runtimes remediados). El candidato local conserva `verify=False` en
   `scripts/cg32_lab.py:204`, `:217` y `:270`, y usa `args.label` directamente
   para construir el directorio en `:296`–`:299`. La rama remota contiene las
   protecciones posteriores. No se ensayó un ataque ni se contactó con NiFi.
2. **Dependencias e imágenes:** incorporar la PR92 actual, head
   `785744bab36fc3901d408761ef37ab2c5aa8abb2`, ya contenida en la PR91 citada.
   Faltan `c9eba2f` (origen PyPI HTTPS restringido), `dfb14b8` (gate de todas
   las vulnerabilidades), `1709186`, `ebf259e` y `aca55e6` (runtimes remediados).
   La rama local conserva el antiguo `urlopen` en
   `scripts/audit_dependencies.py:29`, la base Debian antigua de la API y el
   gate limitado a HIGH/CRITICAL corregibles en la API. Esto es un desfase
   comprobado de código y política, no un nuevo recuento de CVE.
3. **Conservar los deltas locales útiles:** guard de bundle sellado y sus cuatro
   tests, documentación/evidencias de cierre y fixture ML. El guard sellado
   todavía no está en la PR91 remota. No eliminarlo al actualizar.
   El arreglo Windows `path.write_bytes(render(ROOT).encode("utf-8"))` ya está
   en PR92 mediante `82ae770`; no abrir otra PR duplicada con toda su historia.
4. **Revisar Projects:** la PR93, head
   `4ff97684a0e0deb51b639daf30ca0c751a1652b4`, publica el filtro canónico.
   Comparar el resultado combinado para preservar ese comportamiento sin
   sobrescribir los cambios nuevos de dependencias.
5. **Validar el nuevo árbol:** suites de aplicación y research, checks de
   integridad CG25 tras cualquier cambio de archivos inventariados, lock,
   export runtime, Compose/flow/inventario y auditorías de dependencias e
   imágenes. Después publicar una composición coherente, evitando PR duplicadas
   de #91/#92/#93 y describiendo expresamente sus dependencias.

Prueba de integración sin cambiar el checkout:

```text
git merge-tree --write-tree review/pending-20261023 origin/perf/cg32-graph-load-20261023
exit 0; árbol 6afad174fd0996968851c6ece8c47f55752ad255
```

No produjo conflictos mecánicos. Solo creó objetos Git; no creó commit, movió
refs ni aplicó el árbol. Ese árbol nuevo no fue ejecutado ni auditado y no se
declara apto. La regresión ejecutada abajo corresponde al árbol local antiguo.

## Validación ejecutada del candidato local existente

Intérprete: `D:/cnc-guard-review-20261023/venv-t3-2fccec37/Scripts/python.exe`.
HEAD: `06510ad85c4e3d392d6e9e9f255a7ae8c57ab23c`.

- Pytest con `-W error`: **653 passed, 3 skipped, 308 subtests passed**,
  60,87 s, exit 0. JUnit: `outputs/branch-readiness-20261026/pytest.xml`.
- Unittest con `-W error`: **361 pruebas, 3 skips**, 46,003 s, exit 0.
  Sus logs incluyen fallos de inicialización simulados por pruebas negativas;
  no se interpretan como fallos de la suite.
- Los skips ES no se ejecutaron contra un servicio real en esta ronda.
- Once checks con exit individual registrado: lock, actionlint, diff, CG02,
  layout, CG25, CG20 offline, export runtime, inventario, flow y Compose: 0.
  Recibo y logs locales: `outputs/branch-readiness-20261026/checks.json`.
- Guard de bundle en el worktree propio de `4a6e01a`: 4 pruebas pasan con
  `-W error`, exit 0. No establece aceptación del resto de esa rama antigua.

La CI de las PR remotas #91 y #92 tiene 17 checks SUCCESS por PR;
#93 tiene 16 SUCCESS. #91 es draft y #91/#92 requieren revisión humana.
Esos resultados pertenecen a sus heads remotos, no al candidato local.

## Límites y siguiente acción

No se repitió un escaneo de imágenes ni de secretos de todas las ramas/historia.
Las auditorías históricas no se convierten en evidencia actual por este informe.
Tampoco se resolvieron rendimiento E2E, valoración docente, ensayo o entrega:
son pendientes de aceptación del proyecto separados de publicar código en PR.

La siguiente acción técnica para las tres ramas antiguas es integrar sus deltas
útiles con las correcciones remotas enumeradas y validar ese árbol nuevo. Esta
ejecución completa la alternativa de investigación solicitada; no publica esos
candidatos antiguos, ni fusiona las PR existentes, ni modifica sus estados.
