# Kibana: cierre local de CI y corrección del runtime Node

Base examinada: `481b6936e8a090b79e7e83d3b0e38bd1f21a1109`, PR119.
Estado: construcción, controles de componentes, CLI y gate de imagen verificados
localmente. **Aceptación del servicio conectado a Elasticsearch pendiente**.
No se ha hecho push, merge, despliegue ni una nueva revisión Muse desde este
subagente. La observación Muse sobre MM11 y la sugerencia de 9.5.6 llegaron del
coordinador; las comprobaciones siguientes son ejecuciones propias.

## CI terminado y origen del fallo

Se descargaron el log del job Kibana y su artefacto del último Dependency audit
terminado: [run 41833235278, job 126585473266](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/41833235278/job/126585473266),
head `6d67bc2ec72d931486174b906654bcc089250cba`.
El gate rechazó CVE-2026-118764 en Minimatch `10.2.4+cncguard.1` y `3.1.5`.
El JSON contiene además los dos avisos HIGH históricos de extract-zip.
SHA256 del JSON extraído:
`f23462fa5c4aa5f5721511439bb75e8f7bd7ce939cc4c93692e4bb6c3f854f26`.

El checkout actual ya incluía la migración a Minimatch **11.0.4**, la adaptación
real de Fleet desde `.makeRe()` a `.match()` y la retirada de la antigua clausura
del/Glob7/MM3. Se leyeron los registros `MM11_MIGRATION_20261105.md`,
`DEL_MIGRATION_20261105.md` y `KIBANA_SCAN_EA0A89E_20261104.md` antes de construir.
No se duplicó ni sustituyó esa implementación por otro backport de MM10.
El [advisory del mantenedor](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249)
identifica 11.0.1 como versión corregida. Se comprobó también la
[fuente oficial 11.0.4](https://github.com/isaacs/minimatch/blob/v11.0.4/changelog.md).

La primera construcción del checkout sin modificaciones terminó correctamente:
`cnc-closeout-kibana:481b693`, imagen
`sha256:76a97603081c30d3ac915012bf64bb3910a0bcda8730222d9a87da07089b7c1b`.
Su escaneo nuevo contiene solamente los dos avisos extract-zip; el gate pasa.
Esto verifica la migración ya existente, no una contribución nueva de este agente.

El run de la base actual `42469896609` estaba en curso/cola al consultarlo:
lock había pasado y los jobs de imágenes aún no aportaban un resultado terminado.
Los demás checks de la base, incluidas las pruebas 3.11/3.12, estaban en SUCCESS.
No se vigilaron, relanzaron ni sondearon pipelines.

## Corrección adicional necesaria: Node y Brotli

Se verificó la existencia de 9.5.6 mediante las
[notas oficiales de Kibana](https://www.elastic.co/docs/release-notes/kibana),
el [anuncio de Elastic](https://www.elastic.co/blog/elastic-stack-9-5-6-released)
y el manifest del registro oficial.
[ESA-2026-232](https://discuss.elastic.co/t/kibana-8-19-24-9-4-9-9-5-6-security-update-esa-2026-232/391369)
declara que 9.5.5 incluye un Node con decoder Brotli vulnerable, alcanzable a
través de respuestas HTTP salientes; identifica Node 24.22.1 en 9.5.6 como
corrección. Elastic no afirma haber reproducido ejecución de código en Kibana.
Un escaneo de paquetes sin ese aviso no basta para descartar el runtime incluido.

Se descargó y escaneó la base oficial 9.5.6 antes de elegir la estrategia.
Su imagen amd64 es
`sha256:e0d31dbaa49f11cec62721ca3e88ac111c0cb5655b4c622db2dff65a6092ae20`.
Trivy encontró 49 combinaciones únicas aviso/paquete/versión: 3 CRITICAL,
14 HIGH, 25 MEDIUM y 7 LOW. Incluye MM10/MM9, Glob10, node-forge1.4.0,
instrumentaciones OTel y bibliotecas Wolfi. La fuente oficial también conserva
Minimatch10.2.4 y del6.1.1 y cambia just-bash a3.4.2. Una sustitución directa
de base reintroduciría findings e invalidaría los inventarios/consumidores
calificados. No se presenta 9.5.6 sin parches como candidata limpia.

La corrección acotada conserva la aplicación 9.5.5 y sus migraciones e integra
**ambas distribuciones Node 24.22.1**, sin modificar sus bytes, desde:

```text
docker.elastic.co/kibana/kibana-wolfi:9.5.6@sha256:fcc4fd28898aec394dc45c568ba811e34c132f5a0ebadfa8f8d1d412f55e00c3
amd64 manifest: sha256:4c1e39a1d4d99fa21421a2c27994f6cb8be38b01f2ff6f8e1a49ec7fe997df71
```

Se elimina el árbol Node antiguo antes de copiar; el fallback `glibc-217` no
puede conservar el binario vulnerable. Se descubrió mediante CLI real que la
aplicación rechaza Node distinto del declarado. `apply-node-security-runtime.cjs`
verifica el SHA256 del package.json original y cambia su contrato exacto de
24.21.0 a24.22.1, conservando versión9.5.5 y añadiendo procedencia explícita de
la integración local. **No es una distribución upstream de Kibana9.5.6 ni una
afirmación de soporte oficial para esta combinación.**

El validador original permanece sin cambios; no se usa
`UNSAFE_DISABLE_NODE_VERSION_VALIDATION`. Su SHA256 es
`f185b797e4bc73bf2509302c700a377d3ddcd0045d53ea9fa21a947734616b7e`.
La prueba nueva ejecuta ambos binarios, hace round-trip Brotli, rechaza entrada
inválida, ejecuta el validador real y comprueba sus negativas para24.21.0 y24.22.2.
Estos controles no son un exploit de corrupción de memoria.

Hashes de los binarios coincidentes en donante y candidata:

```text
default/bin/node   e32e2d16081cf644f88392934288086e7662529d0d43277c34f7aad2207cfafb
glibc-217/bin/node 6b75cf562942b1822fd36461d5626942b87a02a986b686e635d3629376ddcf7a
```

## Ejecución final e identidad

Todas las construcciones, pulls, escaneos Docker y ejecuciones Node usaron el
Docker **Windows desktop-linux**, daemon
`eab72f91-4cdf-4d18-a6dc-e1160f26af25`, nombre `docker-desktop`, 8CPU,
8329531392bytes de RAM. No se usó el daemon distinto de Fedora/Kalista.
No hubo prune, limpieza, cambios de servicios existentes ni actividad pesada
en Lenovo/Benten. Los contenedores propios temporales usan `cnc-closeout-kibana-*`.

Comando final de construcción, exit0:

```powershell
docker build --progress plain --file deploy/images/kibana.Dockerfile --tag cnc-closeout-kibana:final .
```

Imagen final:
`sha256:690d9f3434d8f82240168951e364be665730df2e16b63a4262081a70e3ae5392`.
Todos los controles finales del Dockerfile se ejecutan **después** del cambio de
runtime: Forge/cadenas, redirects, paquetes de la misma línea, Hono CJS/ESM,
Glob CJS/ESM, MM11 instalado y del. El inventario confirma solo las dos copias
MM11.0.4 y ninguna MM3; conserva los hashes oficiales y consumidores adaptados.
El pin Node de la prueba del distingue el fixture original24.21.0 de la imagen
servida24.22.1, sin retirar controles de comportamiento.

CLI real, exit0, devuelve9.5.5 y registra Node24.22.1:

```powershell
docker run --rm --name cnc-closeout-kibana-cli-final --network none --memory 768m --entrypoint /usr/share/kibana/bin/kibana cnc-closeout-kibana:final --version
```

Trivy0.76.1 Windows se obtuvo de GitHub Releases. SHA256 del ZIP coincidente
con los checksums oficiales:
`1051f49cb22d5284f43425f72aad9cda63ca12ceb92e7caa06903490c82dc9bf`.
Escaneo completo OS/Node, todas las severidades y sin omitir unfixed, exit0:

```powershell
.local/kibana-closeout/trivy/trivy.exe image --quiet --scanners vuln --list-all-pkgs --format json --timeout 15m --output .local/kibana-closeout/final-scan.json cnc-closeout-kibana:final
```

JSON final SHA256:
`736e28b0cc7a3c24a93e2a91cbd56ce9d5360281535e8d96ca07ada412b3eb09`.
El reporte identifica la imagen final anterior. `validate('kibana', report,
expected_artifact='cnc-closeout-kibana:final')` devuelve `[]`: solo se cambia
la identidad esperada del tag local, no las reglas del gate.

Persisten exactamente CVE-2026-19693 y CVE-2026-56876, ambos HIGH,
extract-zip2.0.1+cncguard.1, bajo las dos disposiciones ya existentes. El parche
rechaza entradas symlink antes de escribir y su regresión ejecutada durante el
build pasa. No se amplían `VERIFIED_FINDINGS`, no desaparecen estos avisos y no
se afirma que Trivy haya dado cero avisos brutos. El gate no tiene hallazgos
nuevos sin disposición; la política y sus pruebas permanecen intactas.

## Pruebas y fallos preservados

- `uv run --python 3.12 --frozen python -m pytest -q tests/test_dependency_infra.py tests/test_image_scan_gate.py`:15passed/21subtests, Windows.
- `python -m scripts.image_inventory --check`:exit0, pins activos coinciden.
- `git diff --cached --check`:exit0.
- Suite ampliada Windows con extra kafka:39passed/26subtests,3failed. Dos
  tests llegan a `Read storage unavailable or incompatible` en el fixture de
  archivo; otro falla en el render Compose de rutas Windows. No se tocaron
  esas rutas ajenas al ownership ni se llamaron defectos de Kibana.
- Primera ejecución Fedora:40passed/26subtests,2failed porque Git Linux no
  interpreta el gitdir absoluto Windows del worktree T3.
- Ejecución Fedora con las rutas Git reales por variables de entorno:
  **42passed/26subtests,35.98s**. Mismos tests, sin skips nuevos ni cambios a
  sus aserciones. Usa el venv del coordinador solo para ejecutar pruebas.

```powershell
wsl --distribution fedora --cd /mnt/c/Users/unaiu/.t3/worktrees/B-taldea/t3-6e57043b --exec env GIT_DIR=/mnt/d/github/AABD-Ethazi-2627/B-taldea/.git/worktrees/t3-6e57043b GIT_COMMON_DIR=/mnt/d/github/AABD-Ethazi-2627/B-taldea/.git GIT_WORK_TREE=/mnt/c/Users/unaiu/.t3/worktrees/B-taldea/t3-6e57043b /home/Fedora/.cache/cnc-closeout-20261108/venv/bin/python -m pytest -q tests/test_dependency_infra.py tests/test_image_scan_gate.py tests/test_integration_wiring.py tests/test_cg32_load.py
```

Se preservan también dos invocaciones diagnósticas fallidas: `uv run pytest`
no encontraba `scripts` y se corrigió a `python -m pytest`; ejecutar Docker
con `--version` como comando por defecto hizo que tini intentara ejecutarlo,
corregido usando el entrypoint real de Kibana. La CLI de la primera candidata
Node24.22.1 falló antes de actualizar el contrato exacto; no se oculta ese fallo.

## Relevo al coordinador y bloqueos fuera de ownership

En el run terminado41833235278 solo fallaron Kibana y NiFi; lock, API,
dashboard, Kafka, Elasticsearch, Filebeat, Python, mock-python, uv, Go,
HAProxy y Wolfi pasaron. El log NiFi contiene59tuplas únicas rechazadas,
incluyendo Guava, RabbitMQ, LZ4, Snappy, OTel, Wire y Jackson2/3. Son evidencia
del head6d67bc2, **no** un nuevo escaneo del NiFi recuperado ni de sus archivos
anidados. No se modificó NiFi, Elasticsearch, Compose ni dependencies.yml.

El padre debe ejecutar el smoke conectado sobre la imagen final identificada,
coordinar la compatibilidad/versiones ES, revisión Muse del diff y los checks
completos de la revisión integrada. La CLI y las pruebas de componentes no
sustituyen el arranque de plugins, `/api/status`, conexión ES ni aceptación de
flujos/dashboards. Hasta entonces la aceptación runtime sigue pendiente.

Artefactos crudos locales, conservados y no añadidos al commit:
`.local/kibana-closeout/` de este worktree. Incluye logs CI descargados,
los cuatro JSON completos de Trivy, checksums, logs de build/CLI/pruebas,
manifest oficial y hashes del donante/candidata. El padre puede recogerlos antes
de retirar el worktree. Hash del escaneo base9.5.6:
`dedd86155f19b3ff879954db1da7d664ae4f8fa4aa804f64b2ac9b52a1e7e669`;
hash del escaneo local955 previo:
`13b2e65aaf40e3abcf12b49e95be3caf8c1f2feafbec743582d7622c47e1ca41`.
