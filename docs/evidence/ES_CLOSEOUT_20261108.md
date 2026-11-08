# Elasticsearch: ejecución OTel y cierre local, 2026-11-08

Base de trabajo: `481b6936e8a090b79e7e83d3b0e38bd1f21a1109`.
Solo Elasticsearch; sin push, merge, despliegue ni cambios a Kibana/NiFi.
No se modificó la fuente histórica ejecutada `89f58fc` ni su inventario sellado.

## Imagen y entorno comprobados

Etiqueta final Windows Docker Desktop: `cnc-closeout-es:final`.
Image ID: `sha256:0519cbd228bc6fd0446c2946740556372f1da18e8bf690026b04b32aaedf8f99`.
Daemon: `eab72f91-4cdf-4d18-a6dc-e1160f26af25`, 8 CPU, 8.329.531.392 bytes RAM.
No se utilizó el daemon distinto de Fedora. JDK de imagen **27**;
host Java 21 no se usó para compilar ni ejecutar los probes.
Python local: `uv run --python 3.12`. MemAvailable inicial: 6.871.692 KiB;
filesystem Docker: 983.594.372 KiB disponibles. Los gates históricos VM no se
rebajaron ni se aplicaron artificialmente a estas pruebas locales limitadas.

ES mantuvo 9.5.5 y la base oficial inmutable del Dockerfile. Se descargó e
inspeccionó la oficial 9.5.6, digest
`sha256:592bd996ac90ef6386646821ae38970c31fb82c670b31b5f181520f82d27dd9b`:
lleva API/context/common/SDK OTel **1.64.0**. No elimina el advisory de API
<=1.66, por lo que no simplifica este cierre y no se cambió la versión del stack.
[Release notes Elastic](https://www.elastic.co/docs/release-notes/elasticsearch),
[registro oficial](https://www.docker.elastic.co/r/elasticsearch/elasticsearch-wolfi).

## Defectos reproducidos y corregidos

1. API 1.67 con SDK 1.62: el probe Java compilado falla realmente por
   `io/opentelemetry/api/internal/ConfigUtil`. Alineados seis SDK a 1.67.
2. Solo seis SDK alineados: el arranque real con exportación habilitada falla
   en exporter-common 1.62 por `SemConvAttributes`. Alineados los cuatro
   exporters a 1.67 y sus dependencias publicadas OkHttp JVM 5.5.0 / Okio JVM
   3.18.1. Kotlin conserva el override vendor 2.2.21; Wire JVM conserva 6.4.0.
3. Ese candidato descubre `BoundDoubleHistogram` ausente: API-incubator se
   alinea a 1.67.0-alpha. Instrumentation y disk-buffering conservan sus versiones.
4. Exportando ya métricas/spans aparece un aviso de uso API. Diagnóstico JUL
   FINEST + Log4j TRACE: `APMTracer.stopTrace` llama a `Span.fromContextOrNull`
   con contexto nulo en tareas sin span. Se compila la fuente oficial v9.5.5,
   SHA256 `5bd12c7a170309f026bb9bc2728c2294fcfcb59595926bb2fe8c0176392a841a`,
   con guards en las ocho consultas nullable del mapa. Un contexto ausente sigue
   produciendo ausencia de span; un contexto presente conserva su operación.
   No se suprime el logger ni se cambia el comportamiento de la API OTel.

Fuentes primarias: [advisory CVE-2026-118259 / GHSA-ccrj-gw8r-854m](https://github.com/open-telemetry/opentelemetry-java/security/advisories/GHSA-ccrj-gw8r-854m),
[DefaultConfigProperties 1.62](https://github.com/open-telemetry/opentelemetry-java/blob/v1.62.0/sdk-extensions/autoconfigure-spi/src/main/java/io/opentelemetry/sdk/autoconfigure/spi/internal/DefaultConfigProperties.java),
[ExporterInstrumentation 1.62](https://github.com/open-telemetry/opentelemetry-java/blob/v1.62.0/exporters/common/src/main/java/io/opentelemetry/exporter/internal/metrics/ExporterInstrumentation.java),
[APMTracer original](https://github.com/elastic/elasticsearch/blob/v9.5.5/modules/apm/src/main/java/org/elasticsearch/telemetry/apm/internal/tracing/APMTracer.java).
Los POM originales y pins nuevos están en el directorio de evidencia adjunto.

## Pruebas reales y controles

[Evidencia compacta](../../deploy/images/elasticsearch-patches/otel-qualification/closeout-20261108/runtime-result.json).
Los logs completos y reportes grandes permanecen en `outputs/es-closeout/` de
este checkout, con hashes en el resultado. No contiene datos de producción.

- Build real del Dockerfile, todas las descargas nuevas con SHA256: exit 0.
- Maven 3.9.11 real, plugin dependency 3.8.1: árboles current, SDK-six y aligned;
  override vendor explícito y variante JVM de Wire, excluyendo su artefacto
  multiplataforma común. Maven no se presenta como resolver Gradle: los ajustes
  JVM se especifican para reproducir el inventario instalado. Los árboles retienen
  los conflictos mediados, incluidos los roots alpha originales.
- `javac` JDK27 compila el probe contra los módulos boot reales, seguido por
  `java -cp /tmp EsLoaderProbe ... aligned ...`: exit 0. Loader ES auténtico,
  jar-hell y capas/SPI originales, tres realms, hashes de los nueve core JARs.
  Trace/context/scope, métricas y logs reales; builders HTTP y gRPC LATEST,
  cerrados sin transmisión en el probe aislado.
- Control previo compila pero falla con ConfigUtil; los dos arranques negativos
  posteriores fallan con SemConvAttributes y BoundDoubleHistogram. Se conservan
  las salidas sin relabelarlas como aprobadas.
- Smoke activo: ES 2 GiB/2 CPU, collector 256 MiB/1 CPU, red propia `--internal`,
  sin puertos publicados. Collector oficial 0.143.0, digest
  `sha256:e94651f4a264e36b6009fae118b45c034a93b7ea5fe7f6b29f9d4a0196d19541`.
  OTel metrics/traces activados mediante sus propiedades JVM reales y settings;
  exportación gRPC al collector propio. Entitlement agent adjunto; políticas y
  descriptor APM idénticos al control. Cluster verde y documento sintético
  escrito/leído con autenticación. Collector recibe métricas y spans reales.
  Tras el guard no aparece el aviso API ni `NotEntitledException`.
- Seguridad ES activa; acceso anónimo 401, usuario sintético efímero file-realm.
  Sin exports generales añadidos ni modificaciones de permisos/entitlements.
- 26 pruebas focalizadas/infraestructura y Ruff pasan. El ejecutable `pytest`
  directo no encontraba `scripts`; `python -m pytest` resuelve la invocación.
  Imports POSIX de `fcntl` y `resource` movidos a ejecución Linux: las pruebas
  portables Windows cargan los modelos; la ejecución limitada sigue fail-closed.

Los avisos CPU/GPU no disponible, deprecaciones y transport TLS de un nodo
sintético sin transporte externo no se presentan como prueba de producción.
La ejecución OTel SDK no afirma haber adjuntado el agente APM Java vendor ni
haber validado un backend APM externo, logs de auditoría o repositorios GCS.
No se añaden como obligaciones nuevas de aceptación del serving actual.

## Repetición y límites

```powershell
docker build -f deploy/images/elasticsearch.Dockerfile -t cnc-closeout-es:final .
uv run --python 3.12 deploy/images/elasticsearch-patches/otel-qualification/smoke_runtime.py cnc-closeout-es:final outputs/es-repeat
uv run --python 3.12 deploy/images/elasticsearch-patches/otel-qualification/maven_oracle.py outputs/es-oracle-repeat
uv run --python 3.12 --with pytest python -m pytest -q tests/test_es_otel_qualification.py tests/test_dependency_infra.py
```

Para el smoke OTel activo: collector con `collector.yaml` adjunto en red Docker
interna propia y alias `sink`; ES con `ES_JAVA_OPTS=-Xms512m
-Dtelemetry.otel.metrics.enabled=true -Dtelemetry.otel.traces.enabled=true`,
`telemetry.metrics.enabled=true`, `telemetry.tracing.enabled=true`,
`telemetry.tracing.sample_rate=1.0`, `telemetry.export.endpoint=http://sink:4317`,
intervalo `10s` y send/connect timeout `1s`. Mantener seguridad, límites y
contenedores propios. Capturar el collector antes de detenerlo. El JSON de
inspect completo preservado en outputs contiene la invocación ejecutada.

Escaneo exacto final: **0 findings**, Trivy 0.76.1 fijado por digest
`sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c`.
1.026 paquetes, dos targets, todas las severidades, `ignore-unfixed=false`.
`scripts.enforce_image_scan.validate` con identidad exacta devuelve `[]`.
[Resumen, identidad y hash del JSON crudo](../../deploy/images/elasticsearch-patches/otel-qualification/closeout-20261108/scan-result.json).
Reporte completo: `outputs/es-closeout/final-scan.json`, 709.398 bytes.
La primera campaña sobre un candidato superado se detuvo: exit137, no OOM;
la descarga Java DB se completó mediante el repositorio oficial GHCR. Se
reutilizaron ambas bases recién descargadas para escanear la imagen final;
no se saltó el análisis Java ni se cambiaron filtros.

Los contenedores ES, collector, scanner y la red interna de esta campaña se
eliminaron al acabar; quedan las imágenes etiquetadas para el smoke del padre.
No se tocaron contenedores, builders, volúmenes ni datos ajenos. No hubo prune.
No hay CI, merge, revisión Muse nueva ni aceptación humana nueva. Kibana
conectado/Fleet queda al padre con la etiqueta/ID indicada.
