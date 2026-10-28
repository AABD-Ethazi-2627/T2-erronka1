# Triage de coincidencias históricas de secretos — 26/10/2026

## Resultado

Las 24 coincidencias `generic-api-key` del escaneo ejecutado son **falsos
positivos de hashes de contenido**. Se recalculó cada SHA-256 contra el blob Git
correspondiente o el artefacto original conservado. No se clasificaron por su
aspecto hexadecimal solamente. No se añadió ninguna exclusión, allowlist o
supresión al escáner, ni se reescribió historia.

Esto resuelve esas 24 coincidencias concretas; no certifica ausencia de todos los
tipos de secreto ni constituye auditoría de producción.

## Ejecución y cobertura

Gitleaks 8.30.1, binario Windows x64 de la release oficial `gitleaks/gitleaks`.
El ZIP se verificó contra su archivo oficial de checksums antes de ejecutarlo.
Ámbito: `gitleaks git <repositorio> --log-opts=--all --redact=100`, JSON local.
El escáner registró 210 commits y aproximadamente 16,31 MB, 24 coincidencias;
exit propio 2 (hallazgos). El wrapper `agent-ps` devolvió 1; no se presenta esa
ejecución como exit 0. El triage posterior y sus aserciones terminaron con 0.

Ese escaneo cubre las refs disponibles al ejecutarlo; las modificaciones y
commits de integración posteriores requieren su lectura/escaneo final propio.

## Prueba de la disposición

Para cada entrada del JSON redactado se recuperó
`git show <Commit>:<File>`, se leyó la línea exacta marcada y se identificó la
asignación de un digest SHA-256. Después se verificaron los bytes de la fuente:

| Familia de evidencia | Coincidencias | Verificación |
| --- | ---: | --- |
| CG32 piloto original, `api_server_sha256` | 3 | SHA-256 del `deploy/cg32/api_server.py` conservado en el worktree original CG32; igualdad exacta de bytes. |
| Auditoría durable ES955 | 1 | Blob `scoring/score_api.py` en el commit señalado. |
| CG20 same event | 6 | Blobs de `api-response.json`, logs, llamadas y scripts bajo el mismo directorio de evidencia y commit. |
| Manifiesto CG25 | 2 | Blob `scoring/score_api.py` en cada commit histórico. |
| Importación de respuestas scoring | 1 | Blob `scoring/score_api.py` en el commit señalado. |
| Grafo automático | 5 | Logs/scripts/recibo originales bajo el archivo local del laboratorio `automatic-graph-20261022`; cada digest recalculado e idéntico. |
| Kafka/NiFi real, CG14 y CG26 | 3 | Blob `scoring/score_api.py` en cada commit señalado. |
| Higiene contrato ES v4 | 3 | Blobs `tests/api_client.py`, `tests/test_api.py` y `tests/test_api_client.py` en el commit señalado. |

La regla genérica identifica palabras como `api` en claves/rutas próximas al
digest. La evidencia anterior muestra que los valores detectados representan
contenido de archivos, sin función de autenticación. No se propone rotar un
checksum ni cambiar los manifiestos sellados para evitar la regla.

## Reproducción local

Artefactos ignorados en el checkout de revisión original:

- `outputs/branch-debt-20261026/scan-history.ps1`: descarga verificada y comando.
- `outputs/branch-debt-20261026/secrets/history-scan.log`: cobertura y exit.
- `outputs/branch-debt-20261026/secrets/history-redacted.json`: 24 fingerprints.
- `outputs/branch-debt-20261026/triage-secrets.py`: lectura y recálculo sin
  imprimir candidatos de credenciales; aserciones 24/24 y fuentes verificadas.
- `outputs/branch-debt-20261026/secrets/triage-structural.json`: commit, ruta,
  línea, clave y fuente exacta que coincide, sin valores candidatos.

No se publican los raw logs del laboratorio ni información de autenticación.
Los artefactos locales anteriores se conservan para verificación; su ausencia
en otro host no se sustituye por una afirmación de igualdad no ejecutada.
