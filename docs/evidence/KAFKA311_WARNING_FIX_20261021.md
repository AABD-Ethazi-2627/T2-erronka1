# Kafka: cierre de INHERITED-KAFKA311-WARN-1

Validación local 2026-10-21 del proyecto educativo CNC Guard, base PR42
`e5faf015cc16e2044d25ab59c1ec30c32222d889`. Clasificación original:
IMPORTANT / P2 de validación, confianza alta. No es una vulnerabilidad demostrada.

Se incorpora `kafka-python==3.0.11+cncguard.1` mediante wheel local y fuente uv
path con hash en el lock. El único cambio funcional migra el lector de recursos
a `files(...).joinpath(...).read_text(encoding='utf-8')`. Procedencia, licencia,
transformación y retirada están en [vendor/README.md](../../vendor/README.md)
y [el manifiesto](../../vendor/kafka-python-provenance.json). Ninguna release
oficial corregida estaba disponible en la consulta de PyPI/fuente upstream
documentada allí. No se crea un fork externo ni se modifica un venv a mano.

## Resultado ejecutado

- Python 3.11.15 y 3.12.15, WSL FedoraLinux-43 (sistema reporta Fedora44).
  Entornos propios instalados desde el lock con extra Kafka y hash verificado.
- Control negativo: wheel oficial, proceso limpio, 218 DeprecationWarning en
  3.11 (109 read_text y 109 open_text); cero en 3.12. Este cero del original en
  3.12 no se atribuye a un arreglo de Kafka.
- Wheel corregido: primer import aislado sin supresión, cero avisos en ambas
  versiones. Regresión en procesos nuevos con `-W always` y `-W error`, los
  108 esquemas y FileNotFoundError para recurso ausente: pasa en ambas.
- 17 tests del adaptador por versión, con avisos como errores: pasan.
- Lab librdkafka mock loopback 2.16.0 por versión: almacenamiento, duplicado,
  rechazo, tres replays, offset final 3, SIGTERM exit 0 y Parquet sin cambios.
  No es aceptación de un broker Apache Kafka. Su etiqueta histórica `client`
  es un literal 3.0.11; el paquete instalado verificado es 3.0.11+cncguard.1.
- Suite estricta completa: **251 tests contabilizados por pasada, 3 skips ES,
  0 failures, 0 errors, 0 warnings y 0 unraisables**, dos pasadas por versión.
  Los skips opt-in de Elasticsearch siguen sin ejecutarse; no acreditan E2E.
- Reproducción byte a byte en Windows/Linux, Python3.11/3.12: mismo SHA256
  `92126ea98835abfef978b6c77963faa8dac78f185ac0f5349e54acb19391485a`.
  Los 108 JSON y la licencia permanecen idénticos, RECORD verificado.
- Ruff 0.17.1 default, E/F/I/PLW1510 y format global; lock check con uv 0.13.1;
  layout, CG02 y rango completo `git diff --check` contra la base: pasan.
- Audit locked para 3.11/3.12: 52 paquetes, 0 vulnerabilidades conocidas y 0
  estados adversos. Consulta OSV adicional del upstream 3.0.11 sin advisories.
  uv emite sus avisos de interfaz experimental; no son avisos Python ocultados.
- Sólo cambian dos registros del lock: raíz y Kafka. El proyecto conserva
  `>=3.11,<3.13`; el wheel local declara >=3.9 por disponibilidad de files().

## Conservación y límites

NiFi/CG14, score_api, los consumidores y los datos son idénticos a la base;
los tres archivos preexistentes de outputs/api mantienen sus hashes. No se
entrenaron modelos de entrega, no se evaluó test final ni se operó infraestructura
compartida. Los unit tests crean sus estimadores pequeños y fixtures temporales.

Evidencia completa en el taskroot local `kafka311-warning-fix`: procedure.md,
311-final-results.json,312-final-results.json, logs final, final-summary.json,
package-checks.json, hashes y respuestas originales. Se conservan aparte los
intentos previos: timeout de herramienta, wheel cp311 inicialmente ausente en
caché y rechazo correcto de hash obsoleto antes de regenerar el lock. El mock
cp311 descargado ocupaba 4958027 bytes; las pasadas definitivas fueron offline.

Este cambio queda pendiente de revisión independiente del padre y merge.
No acredita cierre CG14, integración NiFi, aceptación ES, CI ni producción.
