# Corrección de los cuatro checks de 0fdf7ef · 28/10/2026

[Run original](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/40674593745).
[Recibo, IDs y hashes](CI_REFRESH_20261028/receipt.json),
[datos crudos, auditoría y logs](CI_REFRESH_20261028/raw-validation.zip),
[smoke de servicios](CI_REFRESH_20261028/runtime-smoke.json).

- **lock:** los cinco consumidores setup-uv se alinean a0.13.6, versión de la
  referencia de fuente auditada. La auditoría real completa vuelve a pasar;
  no se elimina su comprobación de consistencia.
- **Elasticsearch:** se liberan los pins de OpenSSL4.0 en apk/world para instalar
  la corrección4.0.3. Guava33.7.2-jre sustituye las copias normales y se recompila
  con el namespace reubicado de Iceberg; Snappy1.1.10.9 sustituye1.1.10.8.
  El nombre de módulo automático Snappy se conserva como `snappy.java`, requerido
  por la política existente. No se amplían entitlements. El primer arranque
  detectó esa incompatibilidad; el arranque posterior, ingesta201, replay409,
  consulta y ES|QL200 pasan. Guava normal/reubicado serializan correctamente y
  Snappy nativo comprime/descomprime; el aviso JDK de acceso nativo se conserva.
- **Kibana:** qs6.16.1 resuelve el fallo de stringify con arrays comma y objetos
  no coercibles; seis casos construidos pasan. Deepmerge no tiene release
  upstream corregida: se aplica un parche local real, no un cambio solo de
  metadatos. Cada escritura de mergeObject define una propiedad de datos propia,
  impidiendo setters de prototipo y conservando arrays, símbolos y merges
  ordinarios. Los entrypoints CJS/UMD fallan la regresión antes y pasan después.
  Se identifica como fork local4.3.2-cncguard.1, conservando procedencia4.3.1,
  licencia y scripts exactos. No se publica ese número como release upstream.
- **Filebeat:** x/net pasa av0.62.0, corrigiendo los dos avisos nuevos. La closure
  selecciona x/crypto v0.58.0. Se repite govulncheck contra el binario nuevo: cero
  vulnerabilidades alcanzables; permanece el aviso de módulo GO-2026-5932.
  La excepción exacta ya existente pasa de0.57.0 a0.58.0 tras esa comprobación;
  se retira0.57.0 y el test exige rechazarlo. No se añaden CVE ni rangos abiertos.
  El binario valida la configuración Filebeat vigente.

Los tres gates pasan. Elasticsearch no conserva hallazgos raw; Kibana conserva
los tres avisos de backports ya verificados y Filebeat el aviso de módulo ya
acotado, con prueba nueva. No se interpreta una ausencia de cobertura como
limpieza ni se eliminan escaneos. Kibana alcanza estado `available` contra el
Elasticsearch propio. Contenedores/red privados retirados; sin servicios o datos
compartidos. El verificador histórico limitado a D: no se forzó en Linux: se
registra el smoke independiente exacto, no se le atribuye aquella suite.

Suite completa706 pruebas/368 subpruebas con7 skips; grupo específico24 pruebas/
30 subpruebas. SELF_REVIEW / NOT_INDEPENDENT. La CI del nuevo head se consulta
separadamente; no se declara despliegue, aceptación humana ni repetición de la
campaña CG32 con estas imágenes.
