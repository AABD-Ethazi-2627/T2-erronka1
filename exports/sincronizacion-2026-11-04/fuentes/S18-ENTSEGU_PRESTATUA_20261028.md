# Ensayo preparado para #26/#27 · 28/10/2026

Preparar este ensayo no significa haberlo realizado: los turnos y tiempos siguientes son propuestas, y el acta, la explicación individual y la entrega se registrarán únicamente después de los actos reales.

Base de consulta: `main` tras PR91, merge `b2186e519e5444dcdb127d9409da105a8fe6d674`. Modo predeterminado: lectura de archivos y capturas archivadas, sin servicios, descargas ni carga de modelos. El resultado de esta sesión será una explicación contrastable del recorrido, sus errores y sus límites. El [handoff vigente](PENDING_HANDOFF_20261028.md) mantiene las puertas humanas; el [procedimiento técnico](README.md) y el [acta existente](ACTA_PENDIENTE_20261022.md) conservan sus funciones. Esta hoja facilita el ensayo y no constituye otra acta.

## Preparación de la mesa y reparto propuesto

Abrir los archivos locales antes de empezar y comprobar que el visor permite ampliar PNG y buscar claves en JSON. Dejar las pestañas en el orden de exposición, con los campos indicados ya localizados. Durante los diez minutos se señalan esos campos; la lectura completa y las fuentes de apoyo quedan para las preguntas. Mantener visible la ruta y la fecha de cada fuente. Las rutas enlazadas son del repositorio; no se necesita acceder a las rutas privadas que aparecen dentro de los recibos.

| Turno provisional | Explica y maneja | Pregunta que hará a otro turno |
| --- | --- | --- |
| A · datos/modelo | Cinco sensores + `machine_type`, split y errores; abre la sesión | A D: ¿qué decisión justificaría una alerta? |
| B · API/persistencia | Respuesta canónica, rechazo, replay y 409/422/503 | A C: ¿cuándo puede confirmarse el offset? |
| C · integración/recuperación | Filebeat, Kafka, NiFi, archivo, ES y reconciliación | A A: ¿por qué la fecha no entra al estimador? |
| D · panel/decisión | Identidad visible, filtros, costes y cierre | A B: ¿por qué un 200 no basta para demostrar entrega downstream? |

Los cuatro turnos son funciones, no nombres ni contribuciones acreditadas. Al inicio, el equipo asigna personas y acuerda quién cronometra y toma notas. En una segunda vuelta, cada persona explica un caso ajeno a su especialidad. Si hay menos personas, se conserva la secuencia y se registra quién cubrió cada turno; no se completan participaciones ausentes.

Plan de ensayo propuesto: 5 min de preparación, 10 min de exposición, 12 min de preguntas cruzadas y 8 min de contraste/registro: **35 min**. La exposición de 10 min sigue la referencia de [«Demo Aurkezpena» del enunciado](../../ENUNTZIATUA.md); A07 todavía debe confirmar duración y condiciones finales. Ese literal pide una demostración live: este recorrido offline sirve como ensayo y respaldo, y no acredita haber satisfecho ese requisito vivo.

## Identidades que se anuncian al cambiar de fuente

| Fuente que se abrirá | Identificación verificable | Uso en este ensayo |
| --- | --- | --- |
| [CG26 del 21/10](../evidence/CG26_REHEARSAL_2026-10-21.json) | Manifiesto `a6cc7a29…`, RF `803ee2e1…`, IF `a12304b4…`; hashes completos en el JSON | Ejemplos históricos de API en proceso, 422 y 503. No es la campaña del 28/10. |
| [CG32 del 28/10](../evidence/CG32_REBUILT_IDENTITY_20261028.json) | `rebuilt_candidate`; manifiesto `b85be76e…`, RF `67c98ff5…`, IF `4354475c…`; `historical_CG26_identity_matches=false` | Campaña con bundle reconstruido autorizado y Discover. El mismo `model_version` no implica los mismos bytes. |
| [CG20 del 22/10](../evidence/CG20_SAME_EVENT_20261022.md) | `synthetic-replay-only`, RiskDouble/AnomalyDouble, hash RF de fixture `aaaa…` | Igualdad completa de un evento API→ledger→worker→ES→panel, rechazo y recuperación de respuesta. Es otro laboratorio. |
| [Paquete research CG34](../evidence/CG34_20261023/packages.json) y [contraste del 28/10](../evidence/CG40_CLOSEOUT_20261028.json) | `rf_reference.joblib`, SHA-256 `34a14ab97a0e1facc4f4eff10b7ed9227516cc853d7400abd351ccef17cffe72`; `exported_research_only` | Comparación científica archivada; no bundle operativo ni modelo promovido a la API. |

El merge PR91 está fijado por el SHA anterior. Los **20 checks del head `36797200d9517a3005f32faf1d2adebf9da707f1`** son el estado comunicado en el encargo del padre; esta preparación no los vuelve a consultar ni los atribuye a una nueva CI de `main`. La [reparación CI documentada](../evidence/CI_REFRESH_20261028.md) y las pruebas locales de sus informes son evidencias separadas. Las imágenes reparadas después de la campaña no convierten las medidas archivadas en una campaña nueva.

## Exposición de diez minutos, lista para ensayar

### 00:00–01:15 · A abre y fija el problema

> «CNC Guard clasifica el estado actual de una fila de sensores y conserva su recorrido hasta el panel para apoyar una decisión humana de mantenimiento. Hoy recorreremos evidencias archivadas; indicaré su fecha y si usan modelos reales o dobles. No estamos mostrando un sistema vivo. Trabajamos con el CSV reducido de 8.000 filas: 5.600 para ajuste, 1.200 de validación reutilizada y 1.200 excluidas del test antiguo ya inspeccionado. Cinco sensores y el tipo de máquina entran al estimador; ID, origen y fecha sirven para trazabilidad. No obtenemos ETA, RUL ni una predicción de avería a 24 horas.»

Abrir la [matriz vigente](../rubrica/ESTADO_20261028.md) y localizar E01/E02 y las puertas #37/#26/#27. Señalar el [alcance del modelo](../evidence/CG17_CURRENT_STATE_SCOPE.md) si se pregunta por las entradas. Para mostrar una inferencia RF histórica, abrir `cases.failure_fit_example.prediction` del JSON CG26: `failure_score=0.8024801587301588`, `alert_level=CRITICA`, `anomaly_alert=false`. Es un ejemplo FIT, no evaluación independiente; RF e IF no tienen por qué alertar juntos.

> «Pasamos de la interpretación de una fila a cómo conservamos su identidad durante el transporte.»

### 01:15–03:30 · C y D muestran evento válido → panel

**Primero, candidato reconstruido actual.** C abre [el informe CG32 del 28/10](../evidence/CG32_CAMPAIGN_20261028.md), después [es-query.json](../evidence/CG32_CAMPAIGN_20261028/es-query.json), [discover-receipt.json](../evidence/CG32_CAMPAIGN_20261028/discover-receipt.json) y [discover.png](../evidence/CG32_CAMPAIGN_20261028/discover.png). D compara:

- `event_id=003c2794002ec083e995ce56f882cd03ce3fd32f72209f3e9db471bda89e1542`.
- `source.record_ref=cg32-batch32-base-3-r10-4d8d8b/0/16`, hash RF `67c98ff5…`, índice `cnc-alerts-cg32-batch32-base-3-r10-4d8d8b` y `total.value=1`.
- `alert_level=OK`, `failure_score=7.076830454075572e-05` y `scored_at=2026-10-28T10:09:39.459080Z` en `_source`; en la captura, Documents (1), ID y hash RF visibles según el recibo. No afirmar que todos los campos JSON se leen en esa captura.

> «Esta captura corresponde a un evento del candidato reconstruido en la tercera repetición de carga. La consulta devuelve uno y el recibo documenta la inspección visual. Para enseñar la igualdad completa hasta el panel utilizaremos ahora otro ensayo, del 22 de octubre, con dobles deterministas.»

**Después, cadena completa archivada.** Abrir [same-event.json de CG20](../evidence/CG20_SAME_EVENT_20261022/same-event.json): localizar `raw_utf8`, `canonical`, `canonical_ledger`, `worker_response`, `es_hit` y `equality`. Señalar que la línea original conserva etiquetas, mientras la petición al estimador y la respuesta canónica excluyen esas etiquetas y el CSV crudo. Comparar el ID `279947a017e5d70adba2a83e5eb319c0c7495260ebac7259de1954bb834c6b8b`, `source`, `scored_at`, hash de fixture y scores `0.8/0.5`. Abrir [valores del panel](../evidence/CG20_SAME_EVENT_20261022/dashboard-verified-values.json) y [panel capturado](../evidence/CG20_SAME_EVENT_20261022/dashboard-verified.png). Los valores del panel deben corresponder a ese ID, no al evento CG32 anterior.

Mostrar [Discover con el ID](../evidence/CG20_SAME_EVENT_20261022/discover-same-event.png), [filtro negativo](../evidence/CG20_SAME_EVENT_20261022/discover-negative.png) y [restauración](../evidence/CG20_SAME_EVENT_20261022/discover-restored.png): secuencia archivada **1→0→1**. No clicar una imagen como si fuera interactiva. El panel conserva UTC; Discover puede presentar Europe/Madrid. Explicar el rango temporal y el índice antes de atribuir un cero a pérdida de datos.

### 03:30–05:00 · B muestra rechazo y replay

Abrir [el lote normal.csv de CG20](../evidence/CG20_SAME_EVENT_20261022/lab-01/input/normal.csv): contiene cuatro filas válidas iguales y una quinta línea `bad,csv`. Después, abrir [final.json de CG20](../evidence/CG20_SAME_EVENT_20261022/lab-01/final.json), campos `accounting`, `offset`, `canonical_response_count` y `worker_response_count`: **5 observados = 4 guardados + 1 rechazado + 0 pendientes**, offset **5**, cuatro respuestas canónicas y cuatro del worker. El [informe CG20](../evidence/CG20_SAME_EVENT_20261022.md) explica ese balance. Líneas iguales en coordenadas Kafka diferentes son ocurrencias distintas; no llamarlas replay del mismo evento. El rechazo de ingesta tampoco prueba por sí solo una respuesta HTTP 422.

Para el replay real de ese ensayo, volver a `same-event.json`, campos `http_response.risk_calls=0`, `canonical_ledger` y `attempts`. Leer el apartado «Alcance del ensayo y fallos conservados» del informe: la instrumentación devolvió 500 después del commit, el worker retuvo el registro sin ACK y, tras reparar el registro del stub, obtuvo la respuesta canónica sin otra inferencia.

> «El 200 confirma la respuesta en el ledger local. Todavía hay que comprobar los destinos y el ACK del flujo. Tras una respuesta perdida conservamos la misma petición y el mismo ID: recuperamos también el mismo scored_at. Cambiar el ID para esconder un conflicto impediría demostrar esta propiedad.»

Como apoyo del contrato actual, abrir [tests/test_scoring_replay.py](../../tests/test_scoring_replay.py), método `test_lost_http_response_restart_and_archive_replay`: señalar igualdad de cuerpos, contador de inferencias, reinicio y `stored=1/duplicate=1`. Es lectura de aserciones; la prueba no se ejecuta en este recorrido. El [contrato canónico](../SCORING_REPLAY_CONTRACT.md) explica la garantía y su límite local.

### 05:00–06:30 · B presenta 409/422/503 y cómo actuar

| Caso | Archivo y punto concreto que abrir | Esperado y acción que se explica |
| --- | --- | --- |
| **409**, mismo ID con otro contenido válido | [test_scoring_replay.py](../../tests/test_scoring_replay.py), `test_same_id_different_valid_payload_conflicts_before_inference`; [contrato](../SCORING_REPLAY_CONTRACT.md), «Identidad y conflictos» | Cambiar rpm, timestamp u origen conservando el ID da 409 antes de otra inferencia. Conflicto terminal: conciliar contenido/configuración; no reintentar como 503 ni inventar otro ID. La aserción define el esperado actual, no es un recibo HTTP de CG32. |
| **422**, entrada inválida | [JSON CG26](../evidence/CG26_REHEARSAL_2026-10-21.json), `rejected_422`; ejemplo de entrada vigente en [telemetry.json](../../contracts/examples/valid/telemetry.json) | Diez rechazos archivados: etiquetas, ETA/RUL, rpm negativo y `raw_record`. Retirar campos prohibidos o corregir el dato en origen, conservando la trazabilidad de la corrección. No puntuar una etiqueta de fallo suministrada como feature. |
| **503**, bundle ausente/inválido | Mismo JSON, `missing_bundle.health/predict`; [test_scoring_replay.py](../../tests/test_scoring_replay.py), `test_unready_bundle_does_not_serve_previously_cached_success` | Health y predict 503 en CG26; contrato actual: tampoco servir éxito cacheado cuando la API no está preparada. Conservar petición y reintentar solo tras restauración verificada de la configuración; no generar score alternativo. |

> «Un 409 exige reconciliar una identidad; un 422 exige corregir una entrada; un 503 exige recuperar disponibilidad. El código distingue esas situaciones para evitar que un reintento transforme un error en datos aparentemente válidos.»

### 06:30–08:15 · C muestra fallo y recuperación del 28/10

Abrir [batch32-pause.json](../evidence/CG32_CAMPAIGN_20261028/batch32-pause.json) y [batch32-kill.json](../evidence/CG32_CAMPAIGN_20261028/batch32-kill.json). En cada uno, mostrar `identity_kind`, `pause`, `pause_observed`, `nifi_exit_status`, `reconciliation` y `kafka_committed`.

- Pausa: `for_s=20`, observación de parada/reanudación, 20 ofrecidos/guardados, cero pendientes/pérdidas/duplicados finales y lag final 0.
- SIGKILL: `nifi_exit_status` incluye **137**, observación del kill, 20 ofrecidos/guardados y los mismos balances finales. `http_repeated_posts=0`: esta corrida acredita recuperación del proceso y drenaje, no replay HTTP observado ni corte justo entre HTTP y commit.
- Abrir [summary-10.json](../evidence/CG32_CAMPAIGN_20261028/summary-10.json) y la tabla del informe: tres corridas de 600 eventos, siete corridas en total y 1.860 guardados. Las bases tienen p95 HTTP servidor 14,958/15,116/14,365 ms, pero p95 E2E 82,747/83,859/78,135 s. La oferta 10/s acumula backlog; el throughput con drenaje ronda 4,1–4,3/s. HTTP ≤100 ms y E2E ≤1 s son metas distintas; la segunda falla.

> «Se recuperaron los eventos de estas incidencias concretas. El balance final no demuestra baja latencia, HA ni resistencia a pérdida de host o disco. Hemos mostrado el instante observado, sin atribuir el SIGKILL a una ventana que no quedó probada.»

### 08:15–10:00 · D propone una decisión y cierra

Volver al panel CG20 `CRITICA` y plantear inspección humana, contraste del dato y priorización según riesgo; no una orden automática a la CNC. Abrir [business-costs.json](../evidence/CG34_20261023/business-costs.json) y [business-cost-curves.png](../evidence/CG34_20261023/business-cost-curves.png). Los parámetros del ejercicio son FN 5.000 €, FP 200 €, TP 300 €, TN 0 €. Recuperar FN→TP reduce 4.700 € de coste hipotético y TN→FP añade 200 €: equilibrio marginal 23,5 FP/TP adicional. La [procedencia docente](../evidence/DOCENTE_FORO_20261023.md) documenta el aporte posterior al estudio.

> «Una alerta propone revisar la máquina; la decisión sigue siendo humana. Un falso negativo deja pasar un fallo y un falso positivo consume una inspección. La matriz facilitada permite comparar costes del ejercicio, no afirmar ahorro observado. Conservamos RF y niveles 0,15/0,70; risk_threshold es otro campo y rareza IF es otra señal. La conclusión técnica es un recorrido trazable con recuperación acotada y una limitación E2E medida. Las siguientes acciones del equipo son contrastar la explicación propia, resolver la consulta docente y fijar el paquete y recibo reales.»

## Si falta el entorno o un archivo

| Situación al ensayar | Sustitución concreta | Qué se registra |
| --- | --- | --- |
| No hay servicios o bundle local | Seguir íntegramente los archivos anteriores. No abrir las URLs privadas de los recibos ni ejecutar helpers históricos. | «Lectura offline de evidencia archivada», archivos y versión usados. |
| El visor no abre una captura | Mostrar el JSON/recibo asociado y describir qué comparación permite; solicitar después revisión de la imagen con un visor disponible. | Vista visual no comprobada en esa sesión; no convertir consulta ES en inspección visual. |
| Falta un archivo de la copia | Localizarlo en otro checkout de confianza del mismo SHA, comprobar hash y usarlo como copia identificada; si no está disponible, explicar el caso desde contrato/informe. | Ruta/fuente ausente y caso explicado sin comprobación directa. Sin descarga improvisada. |
| El equipo dispone ya de un lab propio autorizado | Acordar antes otra sesión de reproducción: entorno, bundle exacto, ledger/salida nuevos en D:, presupuesto y recogida de evidencias. El [guion técnico](README.md) es referencia, no una orden de ejecución dentro de esta hoja. | Separar ejecución nueva de lectura; comparar sus propios resultados con los esperados y conservar fallos. |

No hay comandos de arranque, entrenamiento, descarga o deserialización en este recorrido. Una divergencia entre archivo y explicación se anota y corrige antes de seguir; no se sustituye silenciosamente por otro laboratorio.

## Preguntas cruzadas con solución de contraste

El facilitador formula la pregunta sin leer primero la solución. Después pide señalar el archivo que la sostiene y reformularla con palabras propias.

| Pregunta para otro turno | Respuesta de contraste y remedio ante la confusión |
| --- | --- |
| ¿Por qué 8.000 filas no significan 8.000 filas de entrenamiento ni un test final nuevo? | 5.600 fit, 1.200 validación reutilizada y 1.200 excluidas. Mostrar la [membresía](../evidence/CG04_split_membership.json); no sumar validación al ajuste ni llamar independiente a lo ya inspeccionado. |
| ¿Una fecha de fixture demuestra historia por máquina? | No aporta trayectoria física observada. Timestamp identifica la ocurrencia; la clasificación es contemporánea. Mostrar alcance v4 y A04. |
| ¿Son lo mismo `alert_level`, `risk_alert` y `anomaly_alert`? | Son salidas distintas: nivel por cortes 0,15/0,70, comparación RF con `risk_threshold` de policy y comparación IF con su umbral. Buscar campos separados en CG26; justificar cada señal sin inventar calibración. |
| ¿Qué falta después de un 200? | Confirmación durable de destinos y ACK/offset del flujo. Mostrar contrato y `accounting`/offset CG20. Si la respuesta se pierde tras commit, repetir identidad recupera el cuerpo canónico. |
| ¿Cuatro líneas iguales son cuatro duplicados? | Son cuatro ocurrencias si sus coordenadas/IDs difieren. Un replay repite una misma identidad inmutable. Contrastar `source.record_ref` y `event_id`. |
| ¿Por qué no arreglamos 409 cambiando el ID? | Ocultaría la divergencia de una ocurrencia. Conciliar payload/manifiesto; un nuevo ID corresponde a otra ocurrencia legítima asignada por ingesta. |
| ¿Podemos sumar p95 modelo + HTTP + E2E o mezclar corridas? | No: son poblaciones/ventanas distintas. E2E incluye refresh/polling. Mostrar la definición de la campaña y leer un percentil por corrida. |
| ¿Balance cero pérdidas y lag final cero implica sostener 10/s? | No: se drenó después y el backlog creció. Mostrar duración/oferta/drenaje y p95 E2E de las bases del 28/10. |
| ¿El SIGKILL probado demuestra replay HTTP o caída eléctrica? | No: hay exit 137 y recuperación 20/20, pero cero POST repetidos en esa corrida. Replay de respuesta se muestra aparte en CG20 y en las aserciones actuales. |
| ¿Mismo model_version permite intercambiar CG26, rebuilt y research? | No. Comparar hashes/recibos; research está exportado solo para investigación. Restaurar una configuración validada requiere su identidad, no una etiqueta igual. |
| ¿Por qué no usar directamente 0,040816 como nuevo corte? | Es un umbral teórico bajo probabilidad calibrada y costes/efectos específicos. El score actual no acredita esos supuestos. Mantener contrato vigente y distinguir estudio de promoción. |
| ¿Ya se ha entregado porque PR91 está en main? | Merge, checks del head, ensayo, defensa y recibo son hechos diferentes. Mostrar handoff y acta; registrar únicamente actos observados. |

## Checklist de explicación propia

Cada persona lo contrasta con un revisor durante el ensayo; las casillas quedan sin marcar hasta entonces.

- [ ] Explico una entrada, su transformación y salida, localizando campos reales.
- [ ] Identifico mi fuente y fecha; separo CG26, rebuilt, research y dobles CG20.
- [ ] Sigo un solo ID hasta su destino y distingo captura de vista viva.
- [ ] Explico rechazo, replay, 409/422/503 y la acción correcta en cada caso.
- [ ] Explico quién conserva el offset y por qué el ACK espera a los destinos.
- [ ] Distingo medición de rendimiento, evaluación ML y aceptación humana.
- [ ] Justifico una decisión humana y sus FP/FN con la matriz del ejercicio.
- [ ] Respondo una pregunta fuera de mi turno sin leer el texto literalmente.
- [ ] Expreso una limitación concreta y la comprobación que haría falta.

## Hoja de trabajo vacía para usar después

Esta hoja recoge notas auxiliares. Tras la sesión real, trasladar la conclusión y sus evidencias al [acta existente](ACTA_PENDIENTE_20261022.md), sin duplicar acuerdos ni completar respuestas de otra persona.

```text
Fecha/hora/zona y lugar de la sesión:
SHA/árbol documental usado:
Modo observado (lectura offline / ejecución propia identificada):
Personas presentes y turnos realmente cubiertos:
Facilitación / cronometraje / registro:
Inicio / fin / duración de la exposición:
Archivos/IDs/hashes efectivamente contrastados:

Persona | Entrada-transformación-salida explicada | Fallo/límite explicado | Pregunta cruzada y respuesta observada | Revisor
        |                                         |                        |                                        |
        |                                         |                        |                                        |
        |                                         |                        |                                        |
        |                                         |                        |                                        |

Caso | Esperado consultado | Observación propia | Fuente/comando/exit/log si se ejecutó | Diferencia y siguiente acción
     |                     |                    |                                     |
     |                     |                    |                                     |
     |                     |                    |                                     |

Dudas no resueltas y responsable acordado:
Correcciones acordadas / evidencia / plazo real:
Referencia al acta donde se registró la conclusión real:
```

La congelación y entrega se preparan con el [inventario y checklist de consulta](../rubrica/CONSULTA_DOCENTE_PREPARADA_20261028.md). Los objetivos existentes siguen siendo reconciliación 04/11, ensayo 05/11 y entrega 06/11, sujetos a la respuesta docente sobre las condiciones finales.

## Control documental de esta preparación

El 28/10 se contrastaron los destinos de los enlaces de las dos hojas con los archivos del checkout, las identidades CG26/rebuilt/research, los siete balances CG32, los costes citados y las aserciones de replay referenciadas mediante lectura de JSON y fuentes, sin importar código de producto. También se inspeccionaron las capturas archivadas `discover.png` de CG32 y `dashboard-verified.png` de CG20. Esta comprobación documental no ejecuta pruebas de producto, campaña, consulta remota de CI ni ensayo humano.
