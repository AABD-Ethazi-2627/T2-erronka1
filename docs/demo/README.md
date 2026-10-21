# CG26: demo reproducible y preparación de defensa

Guion para que otra persona reproduzca **un ensayo de la API en proceso** desde
un clon limpio y explique sus límites. No requiere sockets, Docker, SMB, OT ni
servicios compartidos. Es preparación de #26, no una defensa realizada ni prueba
de entrega. La revisión por otro miembro sigue pendiente.

## Cobertura y base deliberada

- [PR38](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/38) conserva evidencia
  histórica del recorrido completo y del panel. No prueba el recorrido completo
  después de la corrección de alcance de PR42.
- [PR42](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/42), base
  `28a77543bfd67a36b96ddc2f4acc103b13f62c2e`, fija AI4I reducido (8.000 filas),
  cinco sensores y `machine_type`, clasificación del estado actual. Sus modelos
  se regeneran aquí sin cambiar entrenamiento, contratos o API.
- [PR48](https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/48) aporta memoria,
  ANEXO4 y comprobación documental. Este guion no los reescribe ni los incorpora
  como si estuvieran integrados. PR40/41 son investigación histórica, fuera de la
  entrega activa. PR45/46/47 siguen sus propias revisiones.

La brecha cubierta es el recorrido reproducible normal → alerta → rechazo →
modelo no disponible, con resultados y versión guardados, más preguntas de
defensa. E2E streaming, panel vivo y explicación del equipo quedan pendientes.

## Procedimiento desde un clon limpio

Entorno completo: Linux, Git, Python 3.11 y uv instalados, acceso a paquetes para
`uv sync`. En Windows nativo el ensayo API funciona, pero la suite completa tiene
errores en rutas previas que requieren semántica POSIX/temporales Unix. La auditoría
CG02 compara rutas con `/` y tampoco coincide allí. No reescribir el inventario
para disimular esa diferencia: ejecutar los comandos completos en Linux/WSL con
una distribución explícita y un entorno Python propio para Linux.
Ejecutar desde la raíz de **un clon propio**; no reutilizar el checkout ni
`outputs/` de otra persona. Anotar la versión con `git rev-parse HEAD`,
`uv --version` y, tras `uv sync`, `uv run --frozen python --version`.

```text
git clone --branch feat/26-isolated-demo --single-branch https://github.com/AABD-Ethazi-2627/T2-erronka1.git cnc-guard-cg26
cd cnc-guard-cg26
uv sync --frozen --python 3.11
uv run --frozen python -m scripts.audit_cg02 --check
uv run --frozen python -m scripts.experiment_rf
uv run --frozen python -m scripts.experiment_anomaly
uv run --frozen python -m scripts.package_model
uv run --frozen python -m scripts.rehearse_cg26 --output outputs/cg26/ensayo-01.json
uv run --frozen python -m unittest discover -s tests -v
git diff --check
```

Estos comandos no arrancan servicios. RF/IF entrenan offline en directorios nuevos;
no cargar pickles descargados ni copiar bundles ajenos. El lock fija paquetes,
pero no garantiza hashes idénticos del pickle entre plataformas/Python: cada
ejecución registra sus propios hashes. No es necesario `build_history`, un
experimento estacional ni `demo_maintenance` para esta demo.

El script termina con código 0 y `CG26 isolated rehearsal PASS` **solo si se
cumplen todas sus comprobaciones**. Un error termina con código distinto de 0;
no se publica un nuevo resultado de éxito. Conservar logs y fallo; no editar el
JSON para obtener PASS. El registro `Model bundle unavailable or invalid` durante
el caso sin modelo es esperado; exige 503, no indica que el bundle principal falló.

El empaquetado, los entrenamientos y el ensayo rechazan sobrescrituras. Para
repetir solamente el ensayo, elegir otro archivo, por ejemplo `ensayo-02.json`.
Para repetir entrenamiento, usar otro clon o los argumentos de salida de esos
scripts, sin borrar resultados previos. La API solo deserializa modelos de origen
propio y confiable: un hash no convierte un pickle ajeno en seguro.

## Casos que se muestran

1. `/health` responde 200 con `AI4I_CURRENT_STATE_ONLY`.
2. Fila 1386 (índice de datos desde cero) del fit: ejemplo normal; se exige
   `OK` y `risk_alert=false`. Los sensores y tipo son las únicas seis entradas
   del estimador; identidad/fecha/procedencia son trazabilidad.
3. Fila 679 del fit: ejemplo de fallo docente; se exige `risk_alert=true`.
   No es una avería física observada ni una predicción de cuándo ocurrirá.
4. Diez peticiones inválidas: las seis etiquetas, ETA, RUL, rpm negativo y
   `source.raw_record` deben responder 422. Las etiquetas sirven para entrenar o
   describir los ejemplos, nunca viajan a `/predict`.
5. Cambiar solo ID/fecha deja iguales scores y alertas. La fecha de fixture es
   metadato inventado explícito, no una serie temporal observada.
6. Otra instancia de la misma API sin manifiesto responde 503 en health/predict;
   no emite un score de respaldo ni toca el bundle válido.

Se usan dos ejemplos **del fit conocido**, sin buscar nuevos casos en validación
o test y sin ajustar umbrales. Sirven para explicar comportamientos, no para
estimar rendimiento. El JSON guarda respuestas, rechazos, hashes, versión Python,
HEAD de ejecución y límites. La repetición puede cambiar fecha y `scored_at`.

## Guion de defensa y decisión propuesta

Otra persona debe abrir los artefactos, explicar entrada → transformación →
salida → error y contestar con sus palabras. No rellenar la revisión por ella.

- **G5:** enseñar `scoring/score_api.py` y los informes offline. ¿Qué cambia al
  inferir y qué exigiría un bucle cerrado? Aquí se informa a una persona, sin
  aprendizaje online ni órdenes a una CNC. Ver [CG30](../evidence/CG30.md).
- **G23:** ¿Por qué es IA estrecha? Aprende una tarea de clasificación sintética;
  no tiene comprensión general ni autonomía de mantenimiento.
- **G24:** distinguir el score aprendido de RF de las reglas fijas
  `OK/AVISO/CRITICA` (0,15/0,70). `risk_alert` usa otro umbral ajustado en
  desarrollo; IF señala rareza, no probabilidad de fallo. Ver
  `scoring/alert_policy.py`, manifiesto y [alcance](../evidence/CG17_CURRENT_STATE_SCOPE.md).
- **G72/G105:** abrir el [export del panel](../../kibana/acceptance-export.ndjson)
  y [CG19](../evidence/CG19.md). Propuesta: filtrar rango y fuente, localizar el
  evento con alerta, contrastar sensores y pedir inspección humana contextual.
  El scatter por evento evita fingir continuidad entre IDs simulados. Los KPI
  históricos 43/4 pertenecen al ensayo anterior; no esperar esos contadores en
  este ensayo en memoria. No hay panel vivo nuevo ni prueba de utilidad por operador.
- **G104:** ¿Cuánto cuesta un falso positivo y un falso negativo? Mostrar
  `scoring/alert_policy.py:cost` y [CG10](../evidence/CG10.md). Por ejemplo,
  2 inspecciones a 50 € y 1 omisión con 2 h hipotéticas a 1.200 €/h suman
  2.500 €. Es un escenario docente, sin ahorro observado. Preguntar cómo cambian
  la decisión el desbalance, la calibración pendiente y los errores por régimen.

Para enseñar el panel vivo y streaming hace falta otro ensayo autorizado, aislado
y con reconciliación posterior a PR42. No usar el procedimiento de laboratorio
del README como autorización para acceder a infraestructura compartida.

## Registro humano pendiente

Copiar y completar solo tras el ensayo real de cada compañero:

```text
Persona que reproduce / fecha:
Commit y hashes del JSON:
Comandos ejecutados y códigos de salida / archivo de resultados:
Explicación propia de datos, modelo, integración y panel:
Decisión propuesta y justificación / límites:
Preguntas no resueltas:
Revisor distinto / fecha / conclusión:
```

No hay nombres, firmas, asistencia ni aceptación preasignados. La matriz mantiene
sus seis criterios en estado parcial. El [registro técnico](../evidence/CG26_REHEARSAL.md)
separa ejecución local, CI y publicación; no cerrar #26 por disponer de este guion.
