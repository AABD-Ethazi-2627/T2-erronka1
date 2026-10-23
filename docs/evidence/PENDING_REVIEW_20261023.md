# Revisión y correcciones locales de pendientes — 23/10/2026

Base remota revisada: `5005ccde81f16cd2deac6ee3b30085d773e0fc88`.
Repositorio canónico: `AABD-Ethazi-2627/T2-erronka1`; checkout local `B-taldea`.
Se revisaron las once PR e incidencias abiertas y se incorporaron los materiales
docentes aportados durante el trabajo. Coordinación: diez tareas delegadas
`codex/gpt-6.1-sol`, con razonamiento `xhigh` y servicio `priority`.
No se publicaron cambios, fusionaron PR, cerraron incidencias ni aplicaron Projects.

## Correcciones y trabajo preparado

- CG32: el guard ahora exige el manifiesto y los dos modelos sellados de CG26.
  Corrección local `4a6e01a6004e87cc156d3a3944625e82a0855616`, basada en PR91.
  [Reproducción antes/después](CG32_BUNDLE_PROOF_20261023.json); doce pruebas pasan.
- Projects: filtro exacto del repositorio canónico, manteniendo `Taldea=B-taldea`
  y los guards de estados/fechas/equipo. Catorce tests pasan con `-W error`;
  las sondas independientes confirman rechazo antes de `apply`. No se aplicó al tablero.
- Investigación: fixture `rpm` flotante antes de inyectar infinito; veintidós
  tests y smoke sintético 50/50 pasaron en el entorno separado, sin avisos.
- PR92: composición local con PR91 corregida y el fix anterior, más una fixture
  de exportación escrita como bytes para conservar LF en Windows. Candidato
  `0ab771d7867315d2aa85776cb16b1bf7bfdbb048`, árbol
  `2696fd42e5441e4b12887712bad33255650cd2cd`: 652 tests principales y 303 subtests,
  tres skips ES, cero warnings con `-W error`. No es un merge remoto ni CI nueva.
- Los tres tests ES omitidos se ejecutaron aparte sobre ES9.5.4 privado:
  [3/3 pasan, cero skips, warnings como errores](CG19_REAL_ES_TESTS_20261023.json).
- [Matriz de cuarenta criterios](../rubrica/ESTADO_20261023.md),
  [aclaraciones preparadas](../rubrica/ACLARACIONES_20261023.md) y planificación
  actualizadas, preservando los cortes docentes históricos.
- [CG14 vigente](../CG14_STATUS_20261023.md): #14 está cerrada por aceptación PM;
  RESTORE opcional y valoración académica se documentan por separado.
- [Conclusiones ML para cinco issues](ML_DECISION_REVIEW_20261023.md) preparadas
  para sus responsables, sin nuevos fits. Conservan los 27 avisos históricos y
  los límites de generalización. La continuidad ya reconoce #90 fusionada.

Revisiones independientes: [integración y PR](PENDING_INTEGRATION_20261023.md),
[requisitos](PENDING_REQUIREMENTS_20261023.md) y
[cierre local](PENDING_CLOSEOUT_REVIEW_20261023.md). Esta última encontró F5:
el README modificado requería actualizar su hash CG25. La
[revisión posterior](PENDING_HASH_REVIEW_20261023.md) confirma F5 resuelto:
ocho hashes actuales reconciliados, 191 rutas y snapshot histórico conservados.

## Material docente incorporado después de la revisión técnica

El usuario aportó dos mensajes atribuidos a Aitor Aretxaga Agirre, una guía oral
y una captura del curso. [Procedencia, copias privadas y hashes](ACADEMIC_INPUTS_20261023.json).
Son fuentes aportadas en esta conversación; no se accedió a Moodle ni se
verificaron de forma independiente cuentas financieras industriales.

- Foro del 21/10, 14:51: clasificación tabular de snapshots, sin series ni
  timestamps como entrada del estimador. Aclara el alcance del ejercicio; no
  acredita por sí solo la evaluación literal de G62. El bundle actual añade
  `machine_type` a los cinco sensores del ejemplo: esa diferencia queda visible.
- Foro del 22/10, 18:52: FN 5.000 €, FP 200 €, TP 300 €, TN 0 €. Coincide con el análisis
  económico ya guardado. Recuperar un FN como TP reduce 4.700 € en ese escenario;
  compensa 23,5 FP adicionales. El 25 del foro es la razón bruta 5.000/200.
- Guía oral: seis páginas, estructura, tres/cuatro ideas principales, apoyo
  visual sencillo y ensayo. No fija duración oficial, fecha o canal final.
- Captura y comentario del usuario: documentación y presentación en clase son
  una interpretación de trabajo todavía provisional. Las fechas visibles
  corresponden a entregas anteriores, no a la entrega final.

La conciliación concreta queda en [respuestas docentes aportadas](DOCENTE_FORO_20261023.md).
Quedan preparados [guion en euskera](../demo/DEFENTSA_GIDOIA_20261023.md),
[aplicación de la guía](../demo/ORAL_GUIDE_APPLIED_20261023.md) y
[cuaderno económico complementario](COST_NOTEBOOK_20261023.md). Su estado de
ejecución y revisión se registra en esos documentos. El guion propone cuatro
bloques y diez minutos orientativos, con revisión humana y ensayo pendientes.
El cuaderno ejecutó sus diez celdas y conserva dos PNG embebidos; se inspeccionaron
HTML y figuras. Recalcula costes sobre scores archivados, sin entrenar, elegir
un nuevo corte o cambiar modelos. No se atribuye participación real del equipo
ni una presentación ya celebrada.

## Ensayo ejecutado con el bundle original

El bloqueo de disponibilidad se resolvió localizando y comprobando los tres
hashes históricos, sin reentrenar: [identidad y copia](PENDING_BUNDLE_20261023.json).

| Comprobación | Resultado observado | Límite |
| --- | --- | --- |
| RF+IF en proceso, 600 filas y 20 calentamientos previos | p50 7,467 ms; p95 11,073 ms | No mide HTTP ni E2E |
| Piloto completo, 10 eventos a 1/s | 10 ofrecidos = 10 Kafka = 10 jobs = 10 documentos ES; 0 pérdidas, rechazos, pendientes y duplicados | Un ensayo nominal privado |
| ACK y backlog del piloto | offset 10/end 10, lag final 0 | No prueba apagado del host o durabilidad distribuida |
| HTTP del piloto | diez respuestas 200; p95 60,320 ms | Cumple el objetivo de 100 ms solo en este piloto |
| E2E del piloto | p95 55.748,094 ms; throughput observado 0,157/s | **Incumple el objetivo de p95 ≤ 1.000 ms** |
| Discover | un documento con el mismo ID y hash del RF original | Vista privada; no aceptación operativa o accesibilidad global |

Fuentes: [modelo](CG32_ORIGINAL_MODEL_20261023.json),
[piloto completo](CG32_ORIGINAL_PILOT_20261023.json) y
[comprobación Discover](CG32_ORIGINAL_DISCOVER_20261023.json).
La configuración fue trigger de 2 s, `max_records=1`, `max_polls=3`, un solo propietario
del offset. Son medidas del candidato CG32 basado en PR91 y su entorno registrado;
no se atribuyen al runtime actualizado de PR92.

El primer piloto fue interrumpido por el límite de 60 s del ejecutor. Se inspeccionó
su estado, se conservaron los diez jobs/documentos y se detuvo solo su grafo.
No se reconstruyeron tiempos: [intento interrumpido](CG32_INTERRUPTED_PILOT_20261023.json).
El segundo intento utilizó IDs nuevos y completó la contabilidad. El primer
intento de ES desechable también se conserva en su propio recibo; se diagnosticó
el puerto no publicado y se usó la dirección verificada de su red interna.

Los contenedores de ambos laboratorios quedaron detenidos, con datos, redes,
volúmenes y registros conservados. No se contactaron brokers, SMB ni OT compartidos.
No se exportó un PNG independiente de Discover: AX y captura se inspeccionaron
en el historial de herramientas; el recibo lo indica expresamente.

## Pendientes materiales

- **CG32/#81:** corregir o acordar el rendimiento E2E observado; la campaña
  de tres repeticiones a 10/s, pausa/kill con el bundle original y 50/s condicionada
  no se ejecutaron.
  Encontrar el bundle y completar el piloto no cierran ese objetivo.
- **Imágenes de PR92:** la auditoría versionada conserva 44 hallazgos HIGH
  Debian en la API y HIGH/CRITICAL en otras imágenes. No se han repetido los
  scanners ni verificado aquí la explotabilidad. Sus checks verdes no significan
  cero hallazgos; no se declara aceptada la entrega global.
- **CG33/#82:** la afirmación inicial de ausencia de respuesta quedó parcialmente
  superada por los dos posts aportados. Costes y alcance tabular están aclarados
  según esa copia. Siguen pendientes vigencia/pesos de rúbrica, equivalencia
  académica G49/G62, el ejemplo de cinco sensores frente a `machine_type` y
  canal/fecha/hora/duración definitivos de entrega y defensa.
- **#80/#83/#85/#87/#88/#89:** matriz y decisiones propuestas listas para revisión;
  ninguna aprobación PM/docente se ha suplido con el trabajo de los agentes.
- **#37/#26/#27:** explicaciones reales de cuatro integrantes, ensayo, defensa,
  entrega y justificante requieren los actos y registros correspondientes.
- PR73 y las ramas históricas conservan la disposición detallada en el informe
  de integración. No se promueven accesos LAN ni infraestructura antigua en bloque.

## Candidato final y verificación

Rama local `review/pending-20261023`. El código combinado se validó en
`55cfd63d71c848acbd7647eab7b69bec768b646d`; los cambios posteriores son
documentación, recibos y el cuaderno de análisis complementario, sin cambios
de inferencia, locks o umbrales.

[Validación del candidato combinado](FINAL_VALIDATION_20261023.json):

- Pytest: **653 passed, 308 subtests, 3 skips ES**, con `-W error` y cero avisos emitidos.
- Unittest: **361 pruebas, 3 skips ES**, con `-W error`.
- Los tres casos ES se ejecutaron aparte: **3/3 pasan**, UUID y recurso propio verificados.
- CG02, layout, CG25, CG20 offline, export runtime, inventario y diff: exit 0.
- CG25: **40 criterios, 90 enlaces, 191 hashes actuales y 18 históricos**.

Los recuentos se solapan y no se suman como pruebas independientes. El entorno
local Windows/Python 3.11.9 y su bundle original están identificados en el recibo;
no equivalen a una nueva CI o a la imagen de despliegue.
[Lectura remota final](FINAL_REMOTE_READBACK_20261023.json): main y los once
heads no cambiaron; once PR e incidencias siguen abiertas. Los once enlaces T3
están registrados, sin watchers. No hubo publicación, merge remoto ni cierres.

El cuaderno económico y los documentos posteriores tienen
[comprobaciones propias](FINAL_DOCUMENT_CHECKS_20261023.json); no se les atribuye
la ejecución anterior de las suites de aplicación. Estas comprobaciones incluyen
las cuarenta filas, destinos y anclas locales y la igualdad de los dos PNG
embebidos con las exportaciones inspeccionadas. Las fuentes de aplicación se
mantuvieron iguales al commit probado. Todo queda como candidato local revisable;
la entrega global conserva los bloqueos anteriores.
