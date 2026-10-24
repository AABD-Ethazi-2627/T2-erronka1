# CG14 — revisión de ramas y pendientes, 22/10/2026

Estado: **PARTIAL**, RESTORE funcional **NOT_TESTED**, revisión de otro integrante
**pendiente**. Issue #14 permanece abierta. Este documento registra trabajo real;
no acredita aceptación humana, producción ni recuperación ante desastre.

## Versiones y reconciliación de ramas

Base integrada revisada: `3c957235e81e449bace661f8723f91edb02eb3b7`,
`origin/feat/17-maintenance-planner`, después del merge de PR68.
El [inventario JSON](CG14_BRANCH_AUDIT_20261022.json) fija los SHA completos.

Estas seis ramas son ancestros de la base y tienen cero commits exclusivos:

- `feat/14-nifi-validation-flow`: primera validación NiFi/record services.
- `feat/14-nifi-validation` (PR57): validador, laboratorio y herramientas RESTORE.
- `fix/cg14-scoring-compat-offline` (PR59): proyección al contrato de scoring.
- `fix/cg14-pr42-integration` (PR62): identidad, conciliación y gates terminales.
- `feat/durable-pipeline-wiring` (PR65): worker durable, recibos CG15 y ES requerido si se configura.
- `feat/real-kafka-nifi-lab-20261022` (PR68): ensayo real, export staged y persistencia Kafka explícita.

Además se recorrieron todas las referencias remotas buscando commits exclusivos
sobre `cg14_validation`, cliente RESTORE, `deploy/cg14`, exports/tests CG14 y
`docs/CG14*`: ninguna otra rama contiene cambios exclusivos en esas rutas.
No hace falta otro merge de PR57 a la integración para recuperar su código.
Esto no implica que PR42/57 estén fusionadas a main ni acepta automáticamente
el comportamiento de cada rama. Se revisaron los cambios combinados, los gates
y las evidencias PR62/65/68, y se ejecutó la regresión descrita abajo.

## Cambios completados en esta publicación

Se trasladó la mejora local de autenticación a una rama nueva desde la base
integrada. El checkout original y sus seis archivos modificados y `.vscode/`
se conservaron. No se arrastró la versión antigua completa de los scripts sobre
las correcciones de integración.

El cliente compartido consulta únicamente las dos claves NiFi del entorno y,
si faltan valores, `deploy/cg14/.env` relativo al checkout. No ejecuta shell,
expande variables ni imprime credenciales. Sólo pregunta valores ausentes.
Los HTTP 400 de token se clasifican en categorías fijas, leyendo como máximo
16 KiB, sin imprimir cuerpo/cabeceras ni reintentar la autenticación.
Las pruebas aíslan entorno y `.env`, comprueban precedencia y secretos, y
mantienen el preflight sin lectura de credenciales ni red.

Se reconciliaron matriz, handoff y rúbrica: API canónica, identidad de ocurrencia
y worker durable existen en la base actual. Los cortes que afirmaban su ausencia
se preservan como históricos, con la actualización actual por delante.

## Host inspeccionado: evidencia nueva

Consulta autenticada HTTPS con CA local y validación de hostname; HTTP 201 al
obtener token. Se usaron credenciales existentes sólo en memoria. Después se
hicieron lecturas NiFi/Docker, sin upload, modificación de processors, producción
Kafka, arranque/parada de contenedores ni reset de offsets.

- Original `583bcfb5-01a1-1000-de1a-41cdf8ea78fe`: 23 processors, 27 conexiones,
  un servicio ENABLED; 22 processors STOPPED y uno DISABLED, colas 0.
- RESTORE `5d4f0539-01a1-1000-4a08-0a3f4c8946d8`: 23 processors, 27 conexiones,
  un servicio DISABLED; todos los processors DISABLED, colas 0.
- Huella del original antes/después idéntica; valor fijado en el JSON.
- `configuration_guard` bloquea en `ExecuteGroovyScript — CG14 contract validator/Script Body`:
  la copia importada conserva el script anterior a las correcciones integradas.
- `runtime_guard` bloquea al leer `/lab/server.properties`, ausente en el broker
  legacy. Sus mounts incluyen `/tmp/kraft-combined-logs` y un volumen anónimo
  `/var/lib/kafka/data`; falta el bind padre `/var/lib/kafka` que debe conservar
  metadata. Rootfs escribible y entrypoint antiguo, distintos de PR68.

La consulta inicial de configuración tenía un nombre de helper incorrecto en
el script de auditoría; se corrigió a `snapshot` y se repitió. El resultado
anterior no se cuenta como fallo del producto. El preflight del cliente en el
worktree nuevo necesitó `--cert` apuntando al certificado público del checkout
original; el primer intento sin ese archivo falló offline, sin upload.

## Validación reproducida

Python 3.12.14, entorno nuevo creado mediante `uv sync --frozen --extra kafka`.
Se conservan las dependencias y el wheel Kafka fijados por la base.

```bash
uv run --frozen --extra kafka python -m pytest -q tests/test_cg14_*.py tests/test_durable_receipts_http.py -W error
uv run --frozen --extra kafka python -m unittest discover -s tests -v
uvx --from ruff==0.17.1 ruff check --select E,F,I,PLW1510 cg14_restore_upload.py deploy/cg14/scripts/run-restore-e2e.py tests/test_cg14_restore_e2e.py tests/test_cg14_restore_upload.py
uv run --frozen --extra kafka python deploy/cg14/scripts/run-restore-e2e.py --plan --run-id cg14audit20261022
uv run --frozen --extra kafka python cg14_restore_upload.py --cert /home/admin/Projects/B-taldea/deploy/cg14/secrets/nifi-local.crt
uv run --frozen --extra kafka python scripts/check_repository_layout.py
uv run --frozen --extra kafka python scripts/check_cg25_memory.py
git diff --check
```

Resultados: pytest **296 passed, 91 subtests passed**, warnings como errores;
unittest **304 tests, OK, 6 skipped**. Los skips de unittest no se presentan
como cobertura de Kafka/NiFi vivo; los casos HTTP/durable seleccionados sí se
incluyeron en pytest con las dependencias completas. Ruff y formato correctos,
plan offline `STATIC_PLAN_ONLY`, cliente offline sin red/importación, layout y
CG25 correctos tras actualizar únicamente hashes de archivos cambiados.
El check CG25 detectó inicialmente los hashes anteriores, como corresponde.

La ejecución preliminar con el entorno del checkout antiguo dio 274 passed,
2 skipped y un warning de Starlette. Se sustituyó por el entorno locked anterior;
la cifra preliminar no es el gate final. Los números históricos 209/113 no son
el resultado actual. No se ejecutó `--test` ni se lanzó CI remota manualmente. El workflow
`pull_request` existente puede ejecutarse automáticamente al publicar la PR.

## Pendientes concretos para completar CG14

1. **Operador del laboratorio + responsable CG13:** inventariar configuración
   efectiva, mounts reales, cluster ID, topics, offsets y consumidores del broker
   legacy; realizar backup consistente de datos **y metadata** con verificación
   de restauración antes de sustituirlo. El bind antiguo no acredita contener
   todo el log. Mantener el contenedor/volúmenes previos para rollback; no hacer
   `down -v`, formatear, borrar topics ni recrear desde Compose sobre datos sin
   reconciliar. Alternativamente, preparar un laboratorio independiente con
   inventario y destinos propios; no adoptar recursos ajenos por nombre.
2. **Responsable CG14:** con RESTORE detenido y colas 0, conservar snapshot y
   revisiones, comparar el Groovy antiguo con el export integrado y actualizar
   únicamente la copia RESTORE bajo revisión optimista. La copia segura vigente
   tiene SHA256 `60048fc426b25d57dd4bb6f9c8c5c99a48a80e906865d3d49a210e7659f43f52`.
   No reimportar ni modificar el original para conseguir que el gate pase.
   Volver a comprobar inventario, bundles, configuración y huella del original.
3. **Responsable CG14:** una vez ambos gates pasen, elegir run nuevo y recursos
   exclusivos y ejecutar plan → apply → verify → test → verify → stop según
   [el procedimiento RESTORE](../CG14_RESTORE_E2E.md). El antiguo run conserva
   una preparación fijada a otra definición; no editar su manifiesto para
   reutilizarlo. Exigir 200/422/503/timeout, tres intentos máximos, cuatro DLQ,
   offsets 5/5/0 y conciliación de cada entrega terminal/provenance. Un receipt
   o un contador aislado no es prueba de entrega completa.
4. **Otro integrante del equipo:** revisar artefacto/commit, comando, resultado,
   límites y registrar identidad, conclusión y fecha. La revisión técnica por
   IA y el estado de una PR no satisfacen este criterio oficial.

Riesgo principal: recrear el broker legacy sin haber preservado su almacenamiento
real puede perder log/metadata y offsets. Trigger: cualquier cambio del Compose
que sustituya ese contenedor. Mitigación: inventario/backup/reconciliación previos;
contingencia: conservar contenedor y volúmenes anteriores y restaurar sólo tras
verificación. Dueño: operador de laboratorio/CG13; revisión: antes del paso 1.
Decisión de esta publicación: conservar el host y registrar el bloqueo exacto,
sin bajar las barreras ni ejecutar una migración sobre datos no respaldados.

El ensayo [PR68](REAL_KAFKA_NIFI_20261022.md) acredita su laboratorio propio,
API con modelos sintéticos y driver staged externo. No es la copia RESTORE local
ni un ConsumeKafka del producto con commit posterior a todos los destinos.
[La recreación Kafka](KAFKA_VOLUME_RECREATE_20261022.md) también pertenece a otro
broker propio; no migra el broker local inspeccionado. No se proclama exactly-once,
RESTORE VERIFIED, cierre de CG14 ni aprobación de contratos externos.
