# Cierre auxiliar de infraestructura — 2026-11-08

Base: `860a25c`. PR de composición: <https://github.com/AABD-Ethazi-2627/T2-erronka1/pull/119>.
Trabajo local; no push, merge, despliegue, prune ni cambios de firewall/WSL.
No se modifican NiFi, Elasticsearch, Kibana, Filebeat ni `enforce_image_scan`.
Se aplicó la política MKDL de cero hallazgos pendientes a estos auxiliares.

## Resultado y decisión

El pin HAProxy anterior y el nuevo oficial Alpine presentan CVE-2026-4738
(Trivy: MEDIUM), zlib `1.3.2-r1`; versión corregida `1.4-r0`.
Se probó la imagen oficial `haproxy:3.4.7-alpine` con índice
`sha256:5312d37032c079c4937d45ef63758852434351f3b425a3703521fd999837abcf`:
24 paquetes, un hallazgo. La variante oficial Debian `3.4.7`, índice
`sha256:f6d2ee87b47192d9cc8c22e88fef405122ff339859644883edc2a7d1827f87b3`,
presenta 187 hallazgos en 83 paquetes. Ninguna satisface el gate.

La adaptación `deploy/images/haproxy.Dockerfile` conserva el origen oficial
fijado por digest e instala zlib `1.4-r0` del repositorio firmado de Alpine,
sin compilar HAProxy ni cambiar sus reglas TLS. Compose construye este
Dockerfile; el inventario valida el vínculo y CI escanea el resultado real.
La prueba LAN de CI también construye y usa esta imagen. El pipeline se activa
al cambiar el Dockerfile o el inventario de builds.

Go presentaba el mismo CVE en el CI original. `deploy/images/go.Dockerfile`
actualiza Alpine/zlib sobre su base oficial ya fijada. El target auxiliar Go
se construye antes del escaneo. El pin compartido con Filebeat queda intacto;
no se reconstruye ni se altera la remediación Filebeat del padre.

Los paquetes de Alpine se resuelven durante el build: no se promete igualdad
binaria entre builds futuros. Se fija exactamente zlib `1.4-r0`; cualquier
nuevo hallazgo debe bloquear nuevamente CI. No se añadieron excepciones.

Referencias upstream consultadas:
[empaquetado oficial HAProxy](https://github.com/docker-library/haproxy),
[cambios de zlib](https://github.com/madler/zlib/blob/develop/ChangeLog).
Los escaneos crudos contienen las referencias del advisory y la corrección.

## Diagnóstico del CI original

Se ejecutó `gh run view 42469896609 --repo AABD-Ethazi-2627/T2-erronka1 --log-failed`.
Los logs de los seis auxiliares relevantes están en `original-ci-logs.txt.gz`.

- HAProxy y Go: rechazo por CVE-2026-4738 en zlib `1.3.2-r1`.
- uv: BuildKit rechazó SHA-256 `839488ebc08446a096a893996ed23eac321ac166724cd8c5d9092057834d2d79`,
  esperado `c2e01687fbbcb109277698ec97baca46e1547656ad580abf6d993f9c459af1c7`.
- mock-python: descarga de Trivy con timeout y HTTP 503.
- Python: descarga de Trivy con timeouts de 90 segundos.
- Kafka: descarga de Trivy con cuatro HTTP 504; el escaneo no llegó a ejecutarse.

Los errores de descarga no prueban vulnerabilidades en esas imágenes.
El checkout ya tiene reintentos acotados y verificación del checksum de Trivy;
se conservan. No se reconstruyen estos targets ni Kafka por esos fallos de transporte.

## Procedencia de uv

La descarga local desde la URL original produce el SHA-256 esperado `c2e016…`.
El tag oficial `0.13.6` resuelve al commit
`329bf9448afd9f9088d14a4d57fbc61eb454f117`, cuya firma GitHub informa válida.
Se clonó el tag por Git, se generó `git archive` del commit y se contrastaron
los 1.882 archivos/enlaces del tarball: nombres, tipo, permisos y SHA-256 de
contenidos coinciden. No se acepta el hash observado en CI ni se cambia el pin.
Sin el payload de aquel job no se puede determinar por qué difirió; el rechazo
de integridad original sigue siendo la conducta correcta.

Reproducción: descargar la URL `ADD` de `uv.Dockerfile` como `uv-tag.tar.gz`,
clonar `https://github.com/astral-sh/uv.git` con `--bare --single-branch --branch 0.13.6`,
y ejecutar `git --git-dir=uv.git archive --format=tar --output=uv-git.tar 329bf9448afd9f9088d14a4d57fbc61eb454f117`.
Colocar ambos tar junto a `verify_uv.py` y ejecutarlo. Las respuestas oficiales
del tag/commit y el resultado del contraste se conservan como JSON.

## Validación ejecutada

Evidencia cruda en [infra-ci-closeout-20261108](infra-ci-closeout-20261108/summary.json);
integridad de todos los adjuntos en [SHA256SUMS](infra-ci-closeout-20261108/SHA256SUMS).

- Docker Desktop verificado: `eab72f91-4cdf-4d18-a6dc-e1160f26af25`.
  Builds secuenciales pequeños HAProxy y Go, sin compilación.
- Trivy nativo `0.76.1`, SHA-256 del ejecutable
  `94618922c9eb324d7099bf217b01504bfc1f87a0d46d6008cb24ec89b1d1a4bb`;
  caché privada `.local/infra-closeout/trivy-cache`.
  Comando para cada target: `trivy image --image-src docker --cache-dir .local/infra-closeout/trivy-cache --scanners vuln --list-all-pkgs --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --ignore-unfixed=false --format json --output REPORT cnc-guard-audit:TARGET`.
- HAProxy final: 24 paquetes, cero hallazgos; Go final: 27 entradas, cero
  hallazgos, incluido análisis gobinary. Ambos pasan `python -m scripts.enforce_image_scan TARGET REPORT`.
- `python -m scripts.image_inventory --check`: pasa.
- `python -m unittest discover -s tests -p test_dependency_infra.py -v`:
  6 pruebas pasan en Windows; `test_lan_access.py`: 1 pasa;
  `test_image_scan_gate.py`: 10 pasan.
- TLS real en distribución `fedora`, daemon separado
  `8d5884a7-2b08-44af-9dec-ce45915df105`, usando el venv Linux del padre y
  `PYTHONPATH` de este checkout. Se importó únicamente nuestra imagen.
  `CNC_RUN_LAN_TLS_TESTS=1 CNC_LAN_TLS_BACKEND=docker CNC_LAN_TLS_IMAGE=sha256:948578f16456927f400ca7d8a652dd0b041270b9ab00afd1642b88d508010a47 python -W error -m unittest discover -s tests -p test_lan_ca_rotation.py -v`:
  2 pruebas pasan. Cubren los cinco frontends, cuatro clientes, mTLS,
  rechazo de origen no listado, lista vacía, TLS 1.2/1.3 y retirada de
  conexiones/sesiones antiguas durante rotación de CA. Cada contenedor:
  `--memory 256m --cpus 1`; solo se detienen sus nombres aleatorios propios.
- La imagen Desktop HAProxy tiene ID `2730e720…`; la importación Fedora tiene
  ID `948578f1…`. Sus RootFS coinciden byte a byte (adjuntos), aunque los
  motores representan de forma distinta el objeto importado. El escaneo se
  hizo en Desktop y TLS sobre el ID Fedora indicado, no sobre un tag remoto.
- `git diff --check`: pasa. Revisión local del diff; sin revisión independiente.

## Intentos fallidos y límites

El nombre supuesto `FedoraLinux-43` no existe aquí; `wsl --list --quiet`
identificó la distribución real `fedora`. Una ejecución inicial de infraestructura
en WSL falló porque Git Linux no resuelve el gitdir Windows de este worktree;
la suite completa se ejecutó después correctamente con Git/Python Windows.
Un primer intento TLS usó el ID Desktop en Fedora y falló antes de arrancar
el contenedor; se inspeccionó el ID importado y se repitió con ese ID exacto.
El primer escaneo desde tar fue rechazado por identidad del artifact, y se
repitió mediante Docker con el tag esperado, sin editar el informe ni el gate.

No se tocaron los contenedores/redes/volúmenes del E2E `cg32-bbf35ca8`, ni el
laboratorio. No se ejecutaron builds pesados, pruebas E2E adicionales ni CI remoto.
El cierre global de PR119, el resultado del E2E del padre y la nueva CI remota
quedan a cargo del padre; estos resultados locales no los sustituyen.
