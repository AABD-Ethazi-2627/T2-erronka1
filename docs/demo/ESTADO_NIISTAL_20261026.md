# Preparación de Niistal y bloqueos de entrega — 26/10/2026

Corte técnico sobre `main` **5005ccde81f16cd2deac6ee3b30085d773e0fc88**.
No es acta de defensa ni justificante de entrega. Conserva el
[guion de reproducción](README.md), el [acta sin celebrar](ACTA_PENDIENTE_20261022.md)
y las aceptaciones previas. No sustituye la actualización de las 40 celdas de
la rúbrica encargada a #80 ni registra decisiones por otros miembros.

## Responsabilidad y próximo paso verificable

| Issue | Trabajo técnico de Niistal disponible | Condición pendiente para cerrar | Fecha objetivo |
|---|---|---|---|
| [#37](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/37) | [Justificación ML](../evidence/CG30.md), diagrama, guion y resultados research de #90 | Cada miembro explica con sus palabras y se registra una revisión real; el agente no puede acreditar esa participación | 26/10 |
| [#81](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/81) | [PR #91](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/91), laboratorio/herramientas aisladas y bloqueo explícito | Bundle original identificado por tears-mysthrala; mediciones y Kafka con petiteiker, mismo ID en panel | Informe 30/10; Project 04/11; revisar viabilidad 27/10 |
| [#89](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/89) | Auditoría pública repetible de identidades, abajo; reutiliza #90 sin nuevos fits | #85/#87/#88 abiertas; decisión metodológica de tears-mysthrala e interpretación de Angiecrizu; congelar candidato/hashes o conservar RF | 03/11 |
| [#26](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/26) | Reproducción automatizada de contratos de #50 repetida en entorno bloqueado | Ensayo por miembros reales y prueba efectiva de entrega; guardar comandos, fecha, observaciones y revisión | Ensayo 05/11 |
| [#27](https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/27) | Este corte, enlaces de evidencia y checklist de entrega | #26 y confirmación real de canal/formato/hora por #82; recibo después de entregar | 06/11 |

#86 está cerrada. Las dependencias restantes no se modifican ni se marcan
completadas por disponer de resultados research. Ninguna fecha de planificación
acredita ejecución. Las cinco issues continúan abiertas.

## Auditoría reproducida de #89

```bash
python -m scripts.audit_cg40_partitions
python -m unittest discover -s tests/research -p test_cg40_partitions.py -v
```

[Resultado](../evidence/NIISTAL_READINESS_20261026/partitions.json): sello SHA-256
`d881aa24d43a1f44e98956c37a4e88cacb21989a1fe0c205ed9e8d67aa72187b`
correcto; 5.600/1.200/1.200 identidades originales únicas y disjuntas;
screening 3, outer 3 e inner 3 por outer. Cada fit/held particiona exactamente
su población, cada fila held aparece una vez y cada inner queda dentro de
outer-train. Cinco mutaciones negativas detectan duplicación, fuga outer,
inclusión del test excluido, repetición de fold y fold ausente.

Esto verifica las identidades **declaradas** en el manifiesto publicado, no
que el proceso ejecutado las respetara. No abre CSV, ZIP, pickles ni modelos;
no puntúa validación ni test. Las 173 recargas y la calibración 75/25 siguen
siendo evidencias del autor de #90, no recargas nuevas de este host. Ampliación posterior: el ZIP público de #90 permite repetir la auditoría de
unidades, scores y hashes. Véase la [auditoría de ejecución reproducida](../evidence/CG40_EXECUTION_AUDIT_20261026.md); corrige la afirmación anterior de que
era necesario obtener un archivo privado. La recarga nativa no se repite.
No se promueve ningún modelo. Se conserva RF y política 0,15/0,70 conforme
al informe integrado, sin presentar la recomendación como aceptación PM nueva.

## #81: entrada que permite reanudar sin sustituir el bundle

Usar la rama de #91 y su protocolo; mantener `main` y servicios compartidos
sin cambios. No ejecutar `experiment_rf`, `experiment_anomaly` ni un paquete
research para reconstruir el bundle operativo. Requeridos:

- `manifest.json`: SHA-256 `a6cc7a29f0b061e114e046865cf7ac4a3969111a904a0281f1919aff35ea0945`.
- `rf.pkl`: SHA-256 `803ee2e10e0486aaeb1fb65ed43df9d0069c2d5113d1e1ec45777346a0b6735a`.
- `if.pkl`: SHA-256 `a12304b474f290841a435ffb7d9caaa65c0843ce537267d28686a9d0f49aae79`.

El historial de búsqueda del host/volúmenes no encontró ese bundle; en este
corte no apareció en los archivos del checkout. No se repite una exploración
indiscriminada de imágenes ni se ejecutan modelos desconocidos. No hay medida
nueva del modelo de entrega. Al recibirlo: verificar bytes y procedencia antes
de cargar pickle, presupuesto del lab, piloto, tres repeticiones por tasa
viable, recuperación y reconciliación de IDs, mismo evento en Discover.
Conservar tasas omitidas y límites; el humo de #91 no acredita entrega.

## Validación, CI y dependencias

Entorno propio `/tmp/cnc-niistal-20261026-venv`, Python 3.12.14, creado con
`UV_PROJECT_ENVIRONMENT=/tmp/cnc-niistal-20261026-venv uv sync --frozen --python 3.12 --extra kafka`.
No se reutiliza el `.venv` preexistente para el resultado final.

```bash
/tmp/cnc-niistal-20261026-venv/bin/python -m pytest tests/research/test_cg40_partitions.py tests/test_scoring_replay.py tests/test_cg26_rehearsal.py -q
python -m scripts.check_cg25_memory
```

Los tests CG26 ajustan modelos pequeños sintéticos para comprobar contratos;
no son el bundle operativo, una carga E2E ni una defensa humana. Resultado y
advertencias: [log](../evidence/NIISTAL_READINESS_20261026/locked-tests.log).
CG25: PASS, 40 criterios, 90 enlaces/anclas, 191 hashes actuales y 18 históricos.

#91, head `b8b4ff5a8e71aac77603f0fb0d7e9a9653b5e170`: las 17 comprobaciones
publicadas pasan al consultar el 26/10, incluido
[escaneo de imágenes](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/40145579428).
El comentario anterior de Trivy no representa este último head; tampoco se
extrapola el resultado a `main`, otras ramas o futuras bases de vulnerabilidades.
No se rebaja ningún gate ni se fusiona #91/#92.

El workflow de sincronización falla por ausencia de `PROJECTS_SYNC_TOKEN`:
[run observado](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/40270755905).
Su reparación requiere una credencial dedicada del administrador, conforme a
[PROJECTS_SYNC](../PROJECTS_SYNC.md); no copiar OAuth de `gh`. Este fallo es
administrativo, no una prueba funcional fallida de la API. No se ha configurado
ningún secreto ni cambiado el workflow para ocultarlo.

Revisión de esta ampliación: **SELF_REVIEW / NOT_INDEPENDENT**, agente principal
Codex gpt-6.1-sol. El catálogo T3 ofrece Claude Opus 5.5 y GPT 5.6 Luna, pero no
anuncia `runtimeModes` para sus proveedores: la política exige comprobar
`full-access`, por lo que no se inició una delegación. No hay uso acreditado de
Claude, Luna ni MultiAgent Sync; ninguna herramienta con ese último nombre está
expuesta. Esta limitación no se confunde con cuota agotada.

## Actualización de Project #2

Las cinco issues recibieron comentario con esta evidencia y PR #96. Se intentó
poner #26/#27/#37/#81 en `Blokeatuta` y #89 en `Berrikusten`, sin cambiar
responsables ni fechas. GitHub rechazó la primera mutación: `authentication
token is missing required scopes [project]`. No se escribió ningún estado;
la relectura confirma las cinco en `Egiteke`. El cambio de Project queda
pendiente de una sesión autorizada con permiso `project`; no se amplió la
autenticación ni se solicitaron/copiaron tokens. Los comentarios de las
issues son el registro actual accesible.

## Checklist para el acto real

1. Resolver #82: canal, formato, fecha/hora y modalidad; mientras no haya
   respuesta atribuible, **PENDIENTE**. No inventar Moodle ni una URL de subida.
2. Fijar SHA de entrega tras revisión autorizada; ejecutar CG25 y comprobar
   CI de ese SHA. Incluir memoria, ANEXO1/4, índice y exportaciones previstos.
3. Cada miembro reproduce/explica su parte y registra su evidencia en el acta;
   otro miembro registra conclusión y fecha. Reutilizar #50 y #90 atribuidos.
4. Registrar pendientes de la tabla y su efecto; no transformar desarrollo
   sintético, dobles o ensayos del autor en prueba industrial o evaluación final.
5. Entregar por el canal confirmado y conservar recibo con fecha, archivo/SHA
   y persona que entrega. Solo entonces comprobar los criterios humanos y
   actualizar #26/#27; la preparación de esta lista no los satisface.
