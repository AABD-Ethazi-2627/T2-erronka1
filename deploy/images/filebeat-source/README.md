# Filebeat 9.5.5: origen del archivo de construcción

La construcción del 8 de noviembre de 2026 rechazó la descarga por tag porque
su digest recibido por BuildKit (`bef140a1a96994029153dca8c00b1750b9a5a764fb9db2dc68d7bb40e8a29e8a`)
no coincidía con el pin anterior
`ae4dae382249f28a53be500c0c5d5a6628677f3e65a7d35dfc148b9ad4dc0635`.
No se aceptó ese cuerpo ni se dedujo su contenido del nombre del tag. Dos
descargas diagnósticas posteriores por github.com terminaron en HTTP 504.
No se acredita la causa exacta de la diferencia ni se afirma una intrusión.

## Sustitución verificada

`git ls-remote` y la API oficial resuelven `v9.5.5` al commit
`b80bf8464fba72f582cefed91dd72909eb7116db`. La API informa firma válida;
el [commit público](https://github.com/elastic/beats/commit/b80bf8464fba72f582cefed91dd72909eb7116db)
y su respuesta completa se conservan en [commit.json](commit.json).

Se descargó el archivo por ese commit desde el host oficial codeload y se
compararon todos sus miembros con el árbol completo, no truncado,
`e004fcc3964d3da18e5d77973613d0559cc073b8` de ese commit. El verificador no
extrae ni ejecuta fuentes. Coinciden los **16.101 blobs**, sus permisos de
ejecución y la cobertura completa. Solo aplica las reglas de finales de línea
de la única `.gitattributes`, cuyo blob está fijado: 11 `.bat` del archivo
tienen CRLF y los blobs Git correspondientes tienen LF. No admite otras
normalizaciones ni archivos ausentes/adicionales.

Resultado y hash: [verification.json](verification.json). El Dockerfile cambia
la procedencia de descarga y conserva la versión 9.5.5, el Go fijado y el
checksum obligatorio. Nuevo archivo:

```text
https://codeload.github.com/elastic/beats/tar.gz/b80bf8464fba72f582cefed91dd72909eb7116db
SHA256 9174fdb1d926bcf717e90338538746026a44216a4690a5a1b8a30015ebe1b2bf
```

La fuente autenticada comprende 315.311.074 bytes; el archivo comprimido tiene
107.275.226 bytes. El archivo y ambas respuestas de árboles API se conservan
fuera de Git en `outputs/filebeat-source-verification/`. El primer árbol pedido
por alias de commit devolvió ese alias como identidad; el verificador lo
rechazó y se obtuvo el árbol por su SHA real, sin relajar la comprobación.

## Repetición

Descargar `git/commits/<commit>` y `git/trees/<tree>?recursive=1` desde
`https://api.github.com/repos/elastic/beats/`, conservarlos y ejecutar:

```powershell
uv run --frozen --group dev --extra kafka python deploy/images/filebeat-source/verify_archive.py ARCHIVO.tar.gz ARBOL.json COMMIT.json
uv run --frozen --group dev --extra kafka python -m pytest -q tests/test_filebeat_source.py
```

Ocho casos verifican el origen válido y el rechazo de contenido modificado,
extra, ausente, traversal, modo ejecutable cambiado, árbol truncado/ajeno y
commit no verificado. Las 23 pruebas focalizadas de origen, infraestructura y
gate, con 21 subpruebas, pasan. La construcción inicial superó la descarga con
checksum; la comprobación Go posterior detectó el defecto descrito a continuación.

## Bloqueo adicional descubierto por la prueba Go

La imagen inicial construida desde esta fuente, ID
`sha256:62cf3c2121838ec9e83e9d08f00b059f1b71a688d681ef2c4782c84ca2ff15cf`,
pasó Trivy con la única disposición preexistente GO-2026-5932. Su CLI real
devuelve Filebeat 9.5.5. Sin embargo, `govulncheck v1.9.0 -mode=binary` detectó
símbolos vulnerables de `github.com/klauspost/compress v1.20.0`:
GO-2026-6865 / CVE-2026-116591 / GHSA-fpmh-frq8-7rj8. El reporte Go oficial
descargado de `https://vuln.go.dev/ID/GO-2026-6865.json` y el
[advisory del mantenedor](https://github.com/klauspost/compress/security/advisories/GHSA-fpmh-frq8-7rj8)
identifican 1.20.2 como corrección. El gate no se rebaja ni se añade excepción.

Se fija explícitamente `github.com/klauspost/compress@v1.20.2` junto a los dos
ajustes existentes. La nueva compilación termina y el análisis binario real
devuelve exit 0, **cero vulnerabilidades alcanzables**. La identidad de la imagen
y el hash del binario extraído, el buildinfo con el hash Go de 1.20.2 y el hash
del log se conservan en [runtime-result.json](runtime-result.json).
El nuevo Trivy de esa imagen termina con gate `[]` y solo la disposición
GO-2026-5932 preexistente; el hash del reporte nuevo figura en el mismo JSON.
No se reutiliza el reporte de la imagen anterior. La imagen previa y ambos
binarios se conservan para contrastar el cambio. Sigue pendiente el recorrido
Filebeat/Kafka/NiFi del conjunto, que no se deduce de estas pruebas.

El primer intento del harness Go no pudo ejecutar su binario compilado porque
el tmpfs temporal era noexec. El segundo habilitó ejecución solo en ese tmpfs,
con raíz read-only, sin capacidades, 1 CPU, 1 GiB y 900 s de límite: es el que
produjo el diagnóstico real de compresión. No se atribuye el primer fallo al
producto ni se presenta como prueba superada.
