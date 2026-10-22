# Guard de capa Kafka independiente del orden de Docker

PR68, corrección focal posterior a la revisión de `49800d7633257c45f962578383b211eae755c217`.
La base PR42 con el arreglo ARIA de PR69 es
`f770932d61ff55158bb18c9d89120617e8c5db65`, integrada mediante merge normal
`af95524da29d66bd6b8615c6d40b9d1d66a46ae5`, sin conflictos.

## Fallo anterior y cambio

La revisión independiente conservada en
`D:/github/_local/t2-babysit-20261021/kafka-runtime-review/REPORT.md`
reprodujo persistencia correcta, offset3 retenido, commit6 y replay exacto.
Después, el runner original terminó con exit1 al comparar literalmente:

```text
A /lab
A /lab/runtime
A /lab/server.properties
A /lab/start.sh
```

con las mismas entradas, pero `/lab/runtime` al final. La excepción
`Unexpected write into the container layer` fue un falso diagnóstico de
cambio de capa por orden. El ensayo original sigue siendo fallido: no llegó
al probe read-only ni generó su resultado final. Su continuación independiente
no se convierte retrospectivamente en un PASS del runner.

El guard inicial y el guard posterior usan ahora el mismo parser. Sólo LF
separa entradas; cada una conserva tipo A/C/D y ruta absoluta exacta. Se
ordenan las entradas sin deduplicar, recortar espacios, normalizar Unicode
ni filtrar por prefijos. La salida de `docker diff` se conserva sin `strip`.
Las entradas malformadas se rechazan incluso si baseline y lectura coinciden.
La salida Docker orientada a líneas no ofrece una representación inequívoca
de nombres que contengan LF; no se acredita compatibilidad con esos nombres.

## Regresión focal

Taskroot de esta corrección:
`D:/github/_local/t2-babysit-20261021/kafka-diff-order-fix/`.
La comparación original se extrajo sin cambiar su expresión a `check_layer`
para poder ejercitar el mismo guard sin Kafka. El snapshot
`runner-before-normalization.py` y `red-windows312.log` conservan el rojo:
**3 failed, 18 passed**, exactamente los tres casos de reordenación.

Tras la corrección, **36 passed por combinación**: Python3.11/3.12 en Windows
y FedoraLinux-43 (Fedora44), con warnings como errores y sin caché pytest.
Se aceptan las reordenaciones del caso real, de rutas con espacios/Unicode y
de entradas duplicadas. Se rechazan entradas adicionales A/C/D, ausentes,
cambio de tipo, multiplicidad diferente, prefijos parecidos, espacio final,
Unicode de distinta composición y salida malformada idéntica.
`test_docker_diff_does_not_strip_path_whitespace` protege también la captura
de stdout, no sólo el comparador.

La selección por defecto de Ruff0.17.1 detectó además tres concatenaciones
implícitas sin paréntesis y la captura genérica de readiness, presentes en
`49800d7`. Se parentizan los argumentos sin cambiar sus valores y se limita
el retry de readiness a KafkaError/OSError. Tres tests comprueban retry de
esos errores y propagación de un error de programación inesperado.

Los JSON y logs históricos de
[`KAFKA_VOLUME_RECREATE_20261022.md`](KAFKA_VOLUME_RECREATE_20261022.md) y
[`REAL_KAFKA_NIFI_20261022.md`](REAL_KAFKA_NIFI_20261022.md) permanecen intactos.
No se regeneran sus sellos ni se reutilizan como ejecución nueva.

## Ensayo final del runner corregido

`recreate-final/results.json`, exit0, label `t2-volume-af4dfa503045`:

- Primer ID `3f36e86691743af53d48a14da60c3f3f67742224b0c59003008b5d33694ccfe1`:
  produce0–5, consume0–2 y confirma3; parada completa y eliminación sólo de
  ese ID recién creado.
- ID recreado `58c1705d539a767367818b218b679d97d064d32acb6f9a724a050816a10f0018`:
  mismo bind, metadata idéntica, offset3 retenido, lectura3–5, commit6 y replay
  exacto0–5. El guard de capa corregido termina sin excepción.
- Probe read-only `600c96c3e96ce20b016d96c5f819efa57283ac4cc70c0bea51eb9e6b820d44b6`:
  exit1 con `Read-only file system`, metadata conservada.

Imagen existente oficial Kafka3.7.2 por ID, `--pull=never`, loopback y todos
los mounts verificados como binds explícitos de D:. Contenedores finales
detenidos y datos conservados. El Kafka antiguo sigue detenido: inspect y
sus volúmenes son idénticos; sus entradas completas de capa también, aunque
Docker vuelve a variar su orden textual. Los 97 contenedores anteriores a
este encargo siguen presentes. El taskroot conserva un intento interrumpido
por timeout del lanzador, sus recursos sin arrancar y otro ensayo focal
correcto anterior al ajuste de readiness; no cuentan como prueba del SHA final.

## Checks y límites

Ruff0.17.1, selección por defecto y E/F/I/PLW1510 sobre Python rastreados;
formato de los ocho Python del diff completo; CG02, CG25, layout, lock offline,
actionlint, sintaxis bash y diff del rango base/candidato: exit0.
`uv audit --locked --output-format json`: 57 paquetes, cero vulnerabilidades
y cero adverse statuses. Los avisos experimentales de la CLI se conservan.
Las comprobaciones de bytes protegen los cambios ARIA entrantes, XML, export
NiFi, helpers Windows y evidencia histórica; no se cambia el manifiesto CG25.

Sólo un broker y parada controlada; no caída de host, pérdida de disco,
multinodo ni capacidad sostenida. No se repiten NiFi/ES ni las doce tandas de
capacidad. Sin modelos de entrega, entrenamiento, testfinal o infraestructura
externa. Validación local, CI, revisión del padre, merge y aceptación docente
son estados separados. Los logs, SHA/tree finales y la única captura CI quedan
en el informe durable del taskroot; este documento no declara aprobación.
