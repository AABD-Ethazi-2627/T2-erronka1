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
