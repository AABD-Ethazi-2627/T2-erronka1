# Correcciones de guardas NiFi verificadas en Benten

La [revisión de 0dafc5d](CLAUDE_NIFI_ATOMIC_CONTEXT_RECHECK_20261105.md)
identificó cinco hallazgos medios. El commit `ce3c1d761ab36f5c69458561cb99647a0f951ef3`
comparte las reglas de política entre escritor y contexto, fija por código las
seis familias/reemplazos y sus 22 ocurrencias, y rechaza entradas bloqueadas,
firmas, solapes, inyección y cambios ajenos. La verificación de la salida aplica
también las guardas ZIP de reescritura. La CLI del contexto tiene plazo de pared
de 180 segundos. Un JSON de revisión sigue siendo una selección del coordinador,
no una firma criptográfica ni una aprobación humana o runtime.

Se actualiza el pin de `jackson/support-lock.json` y se acepta la distinta
redacción del rechazo seguro de Unicode ZIP en Python 3.12. Se rechazan las formas de mediación/herencia/perfiles cubiertas por las
reproducciones documentadas; eso no garantiza rechazo de toda forma no modelada. Los contextos
de exclusión distintos solo se admiten si sus diferencias son irrelevantes para
los descendientes requeridos. Las dependencias nativas opcionales no alcanzables
no desbloquean bibliotecas nuevas. No se afirma implementar Maven completo.

## Ejecuciones nuevas

Sobre un checkout limpio e inmutable `ce3c1d7` de la VM 9600:

| Verificación | Resultado |
| --- | --- |
| Cuatro suites afectadas, Python 3.11.17 | 111 tests y 65 subtests pasan |
| Las mismas suites, Python 3.12.14 | 111 tests y 65 subtests pasan |
| Ruff 0.17.1, seis Python modificados | Sin errores |
| Integridad antes/después | 1339 ficheros versionados iguales; checkout limpio |
| RSS máximo de pytest | 54224 / 50884 KiB |
| 18 fixtures nuevos frente a Maven real 3.9.11 | 9 iguales, 9 rechazos seguros, 0 éxitos divergentes |
| Cierres Jackson fijados | 8 de 8 iguales |
| RabbitMQ 5.37.0 | Las 13 coordenadas coinciden |
| RabbitMQ 5.35.0 | Rechazo por POM Netty 4.2.17 sin pin; no es divergencia |

Las pruebas usan el candado común, un CPU y plazos finitos. Los oráculos Java
usan JRE 21, heap de 256 MiB y un namespace sin red. La primera descarga de JDK
agotó 180 segundos: queda conservada como fallo de preparación y se resolvió
instalando solo JRE desde la caché apt, sin descarga. La advertencia ZIP duplicado
de pytest pertenece al caso negativo deliberado.

Evidencia local bajo `/home/tears/.cache/cnc-benten-vm-20261105/`:

| Registro | SHA-256 |
| --- | --- |
| `nifi-guards/report.json` | `6b9b84d2dc743782f153c22c57535bcf7ca50cf9543842e8feb7a94ca6aec97b` |
| `nifi-guards-ce3c1d7-20261105/sha256.json` | `326469b7371933220c6551f977609f5247f23488f5589a44af184727f417808f` |
| `maven-ce3c1d7/report.json` | `bbcc413c0a54a37dd494266901284e8c72f2ef9e7d7c2e5cc7e465cd249082ba` |
| `maven-ce3c1d7/evidence-summary.tar.gz` | `77c700c62e613401889c79a9a015b07d98ccc2a503cbf151ef824cfa2e376715` |

La comparación anterior de 27 fixtures pertenece a una revisión anterior y no
se reetiqueta. Tampoco se presenta esta selección de tests como suite completa,
CI, nueva QA independiente ni aceptación de imagen/NiFi/classloader/SMB. Los
JAR de Hadoop v2, Hazelcast y Parquet y los bytes del overlay privado siguen
congelados. La nueva validación real del contexto, las imágenes, los escaneos y
la integración sobre Benten se registran como fases separadas. No cambian gates,
excepciones, alcance del modelo ni estado de aceptación humana.
