# Benten: validación local atribuida a sus bytes — 06/11/2026

Estado: **regresión local de `12ca2fa` y builds/escaneos reales comprobados; el
gate NiFi anidado falla con 15 hallazgos**. La corrección posterior Maven `92ff99e`
tiene prueba focalizada propia. No se concede aceptación de servicios, campaña
completa, modelo, CI protegido, merge ni rúbrica humana.

Este informe concilia documentos y hashes; no vuelve a ejecutar las suites,
Docker, Maven, servicios ni red. El [registro JSON](BENTEN_VALIDATION_20261106.json)
fija rutas locales, tamaños, SHA-256, cobertura, códigos de salida y límites.
Las exportaciones son evidencia local conservada, sin publicación nueva.

## Identidades y resultados

| Objeto | Fuente y resultado exacto | Límite |
| --- | --- | --- |
| Regresión completa | `12ca2fa95c0e6e94665dc75923f3cbdaa2468b24`: Python 3.11/3.12, cada uno 1107 pytest + 485 subtests, 4 omisiones y 2 warnings intencionales; unittest 577 con 4 omisiones; auditorías correctas. Dashboard 29 con `-W error`. | Precede a `92ff99e`. Tres ensayos ES y uno TLS opt-in omitidos. Compose 5.6.1 oficial; uv 0.13.7 frente a 0.13.6 en CI. No es CI ni prueba de esos servicios. |
| Guardas Maven | Parser final `fbeaeb85…7f9dc9`, tests `7bd5a21e…55de3`, integrados en `92ff99e`: 36 tests + 27 subtests por intérprete. Ocho cierres Jackson y 13 coordenadas RabbitMQ iguales al Maven 3.9.11 offline real. | Ejecución en scratch fijado por hash; clon `12ca2fa` sin cambios. No es una suite completa nueva ni implementación general de Maven. |
| P1 stock original | `06e7e46`, imagen oficial NiFi por digest: verify 19,46 s e install 20,47 s, 22 objetivos/16 NARs como UID/GID 1000. | Confirma la variante stock original. Sin Java/NiFi/servicios iniciados. Intentos 01/02 fallidos conservados. |
| P1 Wolfi/root y build NiFi | Build de `12ca2fa`, imagen `sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5`; Docker RUN instala 22 objetivos/16 NARs en 25,82 s. | Cierra esa variante de instalación y permisos. No prueba arranque, despacho de NAR ni compatibilidad en servicio. |
| NiFi normal | Scanner y gate sin cambios: exit 0; 80 paquetes OS, 107 JARs y dos secciones Rust de 513 paquetes, cero vulnerabilidades. | Su cobertura no reemplaza la auditoría de archivos anidados. |
| NiFi anidado | Imagen de auditoría `sha256:c3513d44e8f1eef6596e73f8845b2cd2c83afe11dd541b8d43d797a67d1db8d1`; scanner exit 0, **gate exit 1**, 1191 paquetes JAR y 15 hallazgos/tuplas distintas. | Continúa bloqueado. No se añade excepción ni se omite ningún hallazgo. |
| API | `12ca2fa`, imagen `sha256:0b3f1dab2896b16e595623067e6eea7ff8e70d58f2f236c1bec7db9018c133f2`: build/scan/gate exit 0; 34 OS, 34 Python, 513 Rust; cero vulnerabilidades. | La build y el scan no prueban el recorrido funcional. |
| Dashboard | `12ca2fa`, imagen `sha256:307debae49122fd9d273533faf6e4004318bf529757ac5b3af05bd11096b66a2`: build/scan/gate exit 0; 34 OS, 49 Python, 513 Rust; cero vulnerabilidades. | El resultado no es aceptación por navegador. |
| Kibana | Se conserva la prueba ya versionada de `06e7e46`, imagen `15d5723a…91e64`: gate 0, solo las dos excepciones extract-zip existentes. | No es una nueva ejecución ni aceptación runtime. |

El resultado histórico `6d67bc2` conserva **63 registros / 59 tuplas distintas**.
Los 15 nuevos son medición de otra imagen exacta, no una reescritura del informe
histórico ni una proyección. El JSON enumera los 15: siete Jackson, dos Guava,
dos RabbitMQ, tres Wire y uno OpenTelemetry. Las nuevas carpetas de cualificación
sin integrar quedan fuera de este inventario y no cuentan como remediación.

## Maven: controles válidos y errores conservados

La [revisión archivada](CLAUDE_FINAL_GUARDS_MM114_RECHECK_20261106.md) examinó
`12ca2fa` frente a `a098a86`: no halló Critical/High/Medium en el diff de producción
del candidato fijado. Sus hipótesis Maven para futuros repins eran inferencias,
no resultados ejecutados. El [informe de la corrección](MAVEN_H_GUARDS_20261106.md)
atribuye la medición y el cambio posterior a su ámbito propio; la revisión antigua
no aprueba automáticamente esos bytes nuevos.

Las formas originales H1/H1b/H1c omitían `packaging=pom` en el padre. Se conservan
íntegras, separadas de los controles que añaden solo esa declaración. Con padres
válidos, H1/H1b/H1c y H2 divergen en la base; H2b es un control igual. La versión
final rechaza las cinco formas explícitamente. La primera corrección rechazó por
exceso una dependencia nativa clasificada, solo de test, de RabbitMQ/Netty; ese
fallo v1 sigue visible. V2 distingue ese caso y reproduce los ocho cierres Jackson
y las 13 coordenadas RabbitMQ. Los 44 POMs Jackson no tienen esas formas;
los 33 POMs Rabbit sí tienen 51 flags GA y 3 de tipo/clasificador gestionado.
No se afirma que Rabbit carezca de propiedades ni que futuros repins sean seguros.

El `sha256.json` inicial Maven se creó mientras crecía `driver.log`; se conserva
su discrepancia conocida. La autoridad es `final-manifest.json` del export **02**,
cerrado después de terminar procesos y logs: **419 ficheros verificados**, cero
faltantes/discrepancias. La exportación inicial queda histórica.

## Integridad comprobada y límites de aceptación

Se verificaron los 27 miembros del manifiesto de regresión y los 1347 hashes de
fuente contra los objetos Git de `12ca2fa`; fuente before/after idéntica. Los nueve
artefactos públicos de modelo/prueba proceden de `a098a86`, comprobados en `12ca2fa`,
sin reevaluación final ni modelo aceptado. Los 104 ficheros de prueba referenciados
por este registro existen y tienen hash calculado; no faltan artefactos referenciados.

| Exportación conservada | SHA-256 |
| --- | --- |
| Regresión `full-regression-12ca2fa-01-export.tgz` | `876df215c057510778d6494bfa431fe3714e9c81d3faddff53c5896a24a505ad` |
| Maven `maven-H-final-20261106-export-02.tgz` | `9eb24ccb23570300f449f9dd9bcaa74b48f95477327e727ae673668d643502fe` |
| P1 `P1-evidence-03.tar.gz` | `6296fba5a44e0171c58fa38012b47d02ad123f2eae600a7f97da50cb6e2271bf` |
| NiFi `nifi-build-scans-12ca2fa.tgz` | `35e25b63a4186880ecc8658a83d4d14e36a537970772ea631a651e499dd69b9d` |
| API/dashboard `api-dashboard-build-12ca2fa.tgz` | `dfa63763b52ab888883cc96c18531645e46e249430782d9c7c3b02394e49105a` |

## Smoke offline y HTTP sintético acotado

El export `api-dashboard-rehearsal-12ca2fa-v2.tgz`, SHA-256
`4f185a6ebec6f46b782da0bc46aa02581b597251568363b7b8e6bf573a733007`,
conserva logs, manifests y hashes de modelos; excluye los bytes PKL públicos.
Las dos imágenes de `12ca2fa` pasan smoke offline, exit 0: red `none`, rootfs
solo lectura, UID 65532, 512 MiB, tmpfs 64 MiB, una CPU, 64 PIDs, sin capacidades
y con `no-new-privileges`. API importa DuckDB 2.0.0, PyArrow 23.0.1 y HTTPX 0.28.1;
consulta JSON builtin con instalación/autoload deshabilitados y verifica UTC/null
con Arrow. Dashboard importa Streamlit 1.66.1 y Requests 2.34.2. Los imports no
cargan modelo ni inician servicios. El RSS de `time -v` es del cliente Docker;
no se presenta como memoria medida del contenedor o servicio.

`http-smoke-02/result.json` confirma después el arranque de ambos servicios,
en bridge interno propio, sin puertos host ni listener externo. Un cliente stdlib
dentro del contenedor API realiza TCP real: health ready/200 con modelo público
de desarrollo, POST 200, replay HTTP idéntico, conflicto 409 y health Streamlit
`ok`. GET `/api/makinak` devuelve el 404 esperado porque la lectura opt-in queda
deshabilitada: no prueba GET. Tampoco hay render UI, datos del dashboard,
navegador, ES, Kafka, CG15, NiFi, SMB ni campaña completa. El ensayo utiliza
clasificación contemporánea de desarrollo, sin aceptación del modelo.
Los dos contenedores y su red propios se retiran; `cleanup_errors=[]`.

Permanecen los errores previos del harness: orden de configuración DuckDB,
`relation.fetchone` ausente en esa API y lookup de puertos host deshabilitados en
bridge interno Docker 29. Se corrigió el harness, conservando los intentos fallidos;
no se cuentan como éxito ni como fallos del producto.

Persisten los límites MM11.4 declarados: truncación positiva upstream P1,
presupuesto finito y disponibilidad no general. Siguen pendientes NiFi en servicio,
NAR/classloaders, campaña actual ES/Kafka/navegador/SMB, CG32 completo, aceptación
del modelo, revisión humana de las 40 celdas, CI protegido y merge. No cambia el
preflight 6 GiB/20 GiB, ninguna excepción ni el alcance contemporáneo AI4I2020.

## Preparación posterior del ZIP de fuentes

Sobre `92ff99e`, el coordinador añade únicamente cuatro entradas explícitas al
allowlist de `scripts/integration_bundle.py`: este informe MD/JSON, el informe
Maven y la revisión Claude archivada. SHA-256 anterior
`af39c4e4fa7732c70aed7b35a33ff3ceb646fcc859ade153e27efc63f09813b1`;
actual inspeccionado
`7d737f47f58d69c5c6427acd077aa2be83685274a5cf0c4d0fe2f4df6f8ffe0b`.
Es inclusión preparada en el working tree. La prueba focalizada de restauración/
tampering y la comprobación de miembros tras incorporar los documentos a Git
corresponden al coordinador; no se atribuye aquí su resultado. No se declara ZIP
final publicado, suite completa nueva ni aceptación de entrega/runtime/humana.

## Corte posterior: VM de 10 GiB, recorrido de seis eventos y navegador real

Este corte amplía los resultados anteriores, que conservan su fuente y sus
limitaciones históricas. Se inspecciona código `e4c5751`; **las imágenes y el worker
que sirvieron la prueba siguen siendo `12ca2fa`, con Kibana `06e7e46`**. Las nuevas
cualificaciones de dependencias son preparación posterior, sin imagen reconstruida
ni nueva aceptación. Los gates normales de las imágenes y el gate anidado NiFi
son puertas diferentes: este último sigue rojo con 15 hallazgos y ninguna excepción
nueva. Un recorrido funcional no lo vuelve verde.

La VM dimensionada a 10 GiB informa 10 428 280 832 bytes de memoria total y
9 912 504 320 disponibles después del ajuste. Los preflight/up posteriores
registran exit 0, manteniendo el requisito 6 GiB/20 GiB. Esta conciliación no modifica
la VM ni repite el laboratorio. El resultado no establece capacidad bajo carga.

Se conservan dos ejecuciones diferenciadas:

- `benten-smoke-r1-966e5d`, exit 1: el selector pedía por defecto un día de historia,
  mientras el snapshot admitía 185 días. No encontró el evento seleccionado y
  la medición/reconciliación quedó incompleta. No se transforma en ejecución válida.
- `benten-reconciled-r1-24fe26`, exit 0: nuevo topic/group/index, clon `12ca2fa`
  intacto y **solo el selector** de `a1ed9d4`, fijado por SHA-256
  `595e7e6e01f69f10540997f65be989338000ea91d177690a8be65e23559e235e`.
  Solicita `desde=timestamp` del evento seleccionado. No se etiqueta el conjunto
  mixto como ejecución íntegra del HEAD actual.

El segundo ensayo ofrece seis eventos AI4I públicos con `source.kind=lab_fixture`,
a 1 evento/s durante seis segundos y modelo público de desarrollo. El recorrido
real Filebeat → Kafka → ciclo de worker programado por NiFi → API → CG15/ES → GET
reconcilia **6 ofrecidos, 6 Kafka, 6 guardados y 6 documentos ES**, cero pérdidas,
pendientes, rechazos, duplicados ES o elementos ajenos. Kafka termina committed/end
6/6 y lag 0; se observan seis POST con respuesta 200, sin POST repetidos. No hay
errores de controlador, observador o limpieza del run. El flujo demostrado usa ese
worker: no se convierte en prueba general de InvokeHTTP u otros procesadores/NARs.

El p95 HTTP es 28,66 ms; el p95 fin a fin, 24 533,51 ms; el drenaje, 28,12 s.
Con solo seis muestras son medidas descriptivas de esta ejecución, sin garantía de
latencia, caudal ni carga sostenida. Los máximos observados `container_mem_usage`
son API 142,2 MiB, ES 941,3, Filebeat 12,9, Kafka 472,2 y NiFi 993,7; no son una
medición de RSS del proceso ni un presupuesto simultáneo de toda la plataforma.
No hay pausa, reinicio, fallo inyectado, soak ni campaña completa de carga CG32.

El navegador real muestra el mismo evento seleccionado. Se verifican
mecánicamente **26 campos del JSON visible del modal contra el snapshot GET**,
con cero discrepancias, además de identidad canónica/CG15/ES del registro. Se
observan escritorio 1280×800, móvil 390×844, modal, página de datos y avance real
del temporizador. La ventana semanal vacía se conserva vacía; la de seis meses
muestra una observación, `n=1`, último evento y procedencia, con agregación mensual
UTC. No se inventan muestras, tendencia ni pronóstico. La evaluación offline
figura no disponible/incompatible; no se acepta el modelo. No se observaron
elementos de excepción Streamlit, pero **no se inspeccionaron exhaustivamente
consola ni red** ni se certifica accesibilidad global.

La exportación local `cg32-benten-public-20261106-01.tgz` tiene SHA-256
`d172c47fd26408c37ca715b467ea9f0701b408f7da6f4b8ec4294905c541e308`:
82 payloads verificados por el manifiesto, 83 ficheros regulares si se incluye el
propio manifiesto. Se verifican además los siete artefactos del manifiesto de
navegador, incluidas las dos capturas. Los nombres `ui:pending_browser` del run y
`view-result` se conservan históricos: la reconciliación/capturas posteriores
aportan el resultado de navegador separado. La exportación excluye credenciales,
modelos/configuración/claves. No es una publicación final ni aceptación de entrega.

Se demuestra este recorrido de fixture con servicios y navegador; siguen sin
aceptarse CNC físico, SMB, modelo industrial, carga completa, CI/merge, rúbrica
humana ni cierre de los 15 hallazgos NiFi. El alcance sigue siendo clasificación
contemporánea AI4I2020, sin ETA/RUL, forecasting o probabilidad futura.

## Plain Jackson: nueva cobertura 2/95, separada de la histórica

La prueba corregida de fuente `7ccc986`, sobre imagen NiFi `03f3e9a1…12d5`, usa
inventario esquema 2, SHA-256
`9a59bb0de97927ca731262477e32a3db6441f3c3000f6a78a6a2cc0abee540cb`.
Mide dos contextos del denominador nuevo de **95**; quedan 93 sin medir en este
lote. El 13/92 anterior queda histórico con su denominador obsoleto: no se suma
para afirmar 15/95 ni se convierte en cobertura del inventario nuevo.

AWS NAR inspecciona 77 298 clases y 589 consumidores externos; el WAR de framework,
49 419 clases y 202 consumidores. No aparecen nuevas referencias rotas en ese
modelo estático; el WAR conserva 767 ausencias preexistentes cuya opcionalidad
no está probada. Doce casos JVM corrigen/assertan la cadena padre Jetty y loader/
CodeSource exactos de mapper/core/databind; el control de origen incorrecto falla
con `AssertionError: code source mismatch`, sin cambiar bytes positivos. La
alcanzabilidad `WEB-INF/classes` de cuatro WARs es estática, no arranque Jetty.
Se verifican los 84 miembros del manifiesto de prueba, sin faltantes/discrepancias.

Persisten delegación WAR/Jetty real, enlaces internos/dinámicos/reflexivos/providers,
triage ABI, guard/writer de familia, imagen reconstruida, scans y QA independiente.
`Class.forName(false)` no acredita uso compatible de Jackson. Continúan
`replacement:null`, `promotion_eligible:false` y `runtime_approved:false`.

## OTel corregido: preparación actual pendiente de resultado

`e4c5751` prepara el experimento corregido con consumidores externos reales,
paridad old/aligned, SPI, procedencia y guardas de cobertura/fallo cerrado. La
nueva ejecución VM sigue pendiente del informe final del coordinador a este corte.
No se declara PASS ni se convierte la preparación en remediación de la imagen.

El `aligned-result.json` anterior permanece histórico: sus pruebas SDK no ejecutaron
consumidores GCP reales. El README corrige explícitamente aquella atribución; no
se reetiqueta el resultado antiguo como ejecución del experimento corregido.
Las nuevas fuentes, informes y tests versionados se inventarían como preparación
identificada por bytes, no como aceptación de componentes, CVE, servicios o CI.

### Escaneos normales ES, Kafka y Filebeat comprobados

Se verifican los 33 hashes (11 por imagen) del `gates.json` exportado. Las builds,
scans y gates de las tres imágenes `12ca2fa` terminan en 0, vinculados a los IDs
del recorrido: ES `2005cca9…ccb4` (74 OS/952 JAR, cero hallazgos), Kafka
`416bb85c…0c8a` (80 OS/109 JAR, cero) y Filebeat `53fe1a05…b557`
(55 OS/193 Go, un hallazgo permitido existente `GO-2026-5932` en
`golang.org/x/crypto v0.58.0`). No se presenta Filebeat como cero vulnerabilidades.
Junto a las pruebas anteriores, los siete gates normales pasan; NiFi anidado sigue
exit 1/15 hallazgos. No se crea excepción ni se cambia la política.

Actualización OTel comunicada por el coordinador: el primer intento corregido
`e4c5751` se detiene cerrado por ocho símbolos originales no clasificados. Sigue
en diagnóstico y pendiente de evidencia final; no se declara cualificación nueva.
Esta conciliación no ha verificado independientemente ese batch todavía.

El HEAD de preparación avanza después a `8429e12`, con resolución explícita de
declaraciones JDK heredadas. Se registran sus bytes actuales, sin atribuirles aún
un resultado VM. El intento fallido de `e4c5751` conserva su identidad; no se
convierte retrospectivamente en PASS. Las imágenes servidas no cambian.

## OTel: resultado corregido nuevo, fuente congelada `8429e12`

Este resultado **sustituye solo el estado pendiente de la ejecución corregida**.
Los registros anteriores siguen fechados y no se reetiquetan. El batch de fuente
`8429e12` pasa 52 tests y 3 subtests, seguido de Maven (1,179 s), análisis simbólico
(30,554 s) y controles de loader real (5,491 s), todos exit 0. El sealer versionado
procedente de `2f7f6eb` produce `summary.json`; se comprueba el hash de su fuente.
`6d064ce` añade después documentación del resultado, sin cambiar código runtime.

La nueva exportación local `reviewfix-evidence.tgz` tiene SHA-256
`54896f8f44cf5c3d142055387bb0dbe52a3c7a2120810438e5050af1396a4749`.
Se verifican 54 payloads del manifiesto, 55 ficheros incluyendo el manifiesto, y
las 20 fuentes archivadas contra Git `8429e12`, con cero faltantes/discrepancias.
El intento fallido `e4c5751` también se conserva: archivo SHA-256
`8d97be9bb82377ad39dc52e0e02f65864a0337b41f1fb20b9fdb99b2900be7fd`,
37 payloads verificados más manifiesto. Pasó oracle y 49 guards antes de detenerse
cerrado en ocho referencias originales no clasificadas; conserva dos diagnósticos
acotados. Ese fallo no se convierte retrospectivamente en resultado verde.

Con el `NarClassLoader` instalado y la cadena real de cuatro NARs, las **nueve
clases consumidoras externas seleccionadas se inicializan** correctamente tanto
en old como en aligned. Un `ResourceProvider` se instancia por ServiceLoader
con loader NAR explícito en cada variante. El control narrow falla en ConfigUtil
antes de atribuirse inicialización posterior. Esto sí aporta inicialización real
de esas clases, separada de la antigua mera carga sin inicialización. No ejercita
operaciones de exporter/GCP, atributos del provider, `InstanceClassLoader`/TCCL del
procesador real, scheduler o servidor NiFi. El resultado SDK anterior de `a6bddd0`
y su `aligned-result.json` conservan su corrección de alcance; no se hacen pasar
por este batch.

En el modelo simbólico actual, las 205 referencias no resueltas se clasifican
como **155 miembros JDK heredados y 50 internos incubator opcionales**; no quedan
sin clasificar. Las 228 de old son 161 JDK, 66 incubator y una llamada heredada
interna antigua exacta. Clasificarlas no demuestra que las rutas opcionales
funcionen. El control inverso SDK nuevo/API antigua expone ocho referencias
ConfigUtil no admitidas y falla; quitar API produce 37 fallos nuevos. El análisis
no detecta referencias modeladas rotas nuevas, pero declara diez miembros
abstractos nuevos, 29 removals públicos/protegidos, 22 restricciones de acceso y
un cambio static, con cero impactos externos **modelados**. No es una garantía ABI.

Las 144 clases externas incluyen usos solo en descriptores; las 110 de la revisión
antigua contaban constant pool. No son denominadores intercambiables ni cobertura
completa. Las declaraciones heredadas se modelan desde `java.base.jmod` del
**compilador Ubuntu JDK21 montado**, con hash propio: no es un verificador JVM
completo de la imagen. Persisten límites de accesos, reflexión, method handles,
herencia/JVM completa y rutas opcionales. Se discriminan fuente de encoding
modificada y marcadores de bytecode; los controles benignos no cierran la CVE.

Los 189 JARs expandidos, 16 de launcher, NARs originales, fuentes e identidad de
imagen se verifican antes/después sin cambios; no quedan contenedores propios de
la prueba ni errores de finalización. La clausura Maven medida cubre los nueve
módulos observados (SDK 8, SPI 9, unión 9), sin actualizar familias ajenas.
**No cambia overlay, writer, imagen servida, scan ni cuenta de 15 hallazgos NiFi**.
Continúan `replacement:null`, `promotion_eligible:false` y `runtime_approved:false`.
La prueba no cualifica ES ni añade aceptación CG32, SMB, modelo, CI/merge o humana.
