# Reparación del escaneo API · 28/10/2026

El [job API de 719c839](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/40671358463/job/122758646661)
rechazó cuatro avisos de rustls0.23.45 en `/usr/local/bin/uv`:
GHSA-c8m5-c952-6cm4, GHSA-h2v8-394m-p7vv, GHSA-vp88-798v-h67f y
GHSA-w44r-93j7-qv28. El gate funcionó; no era un fallo transitorio del escáner.

La [versión publicada uv0.13.6](https://github.com/astral-sh/uv/releases/tag/0.13.6)
aún fija rustls0.23.45 en Cargo.lock. Se reconstruye esa fuente con la
[corrección rustls0.23.46](https://github.com/advisories/GHSA-c8m5-c952-6cm4).
`uv-rustls.patch` cambia únicamente versión y checksum de ese paquete respecto
al lock upstream. Tar de uv, imagen compiladora y versión cargo-auditable quedan
fijados; Cargo compila con `--locked`. No se rehace el lock de Python ni se ajustan
modelos, umbrales, servicios compartidos o resultados de campañas anteriores.

La etapa canónica `deploy/images/uv-stage.Dockerfile` se replica en API, NiFi y
la imagen uv de auditoría. El inventario rechaza desviaciones entre consumidores
y cambios de versión de fuente no conciliados. La etapa final parte de scratch:
no hereda capas con los binarios vulnerables. La compilación con cargo-auditable
conserva la información embebida necesaria para auditar las dependencias Rust.
El gate conserva cobertura Rust y todas sus reglas; no hay nuevas excepciones.
La matriz de doce escaneos permanece, y uv pasa a construirse como target propio.
La referencia uv de `deploy/images.json` conserva la versión/digest upstream para
procedencia; `deploy/build-targets.json` hace que CI audite el artefacto propio
compilado, no que dé por corregido el binario upstream sin modificar.

El recibo y los escaneos de este directorio registran las verificaciones locales.
La CI del nuevo head se comprueba separadamente. Revisión del agente principal,
SELF_REVIEW / NOT_INDEPENDENT; no se atribuye revisión a un subagente. Los
resultados de carga del 28/10 siguen ligados a sus hashes originales de imágenes;
esta reparación no se presenta como repetición de aquella campaña.

## Validación local completada

[Recibo y hashes](UV_RUSTLS_REPAIR_20261028/receipt.json),
[escaneos completos y logs](UV_RUSTLS_REPAIR_20261028/raw-validation.zip),
[resultado del gate](UV_RUSTLS_REPAIR_20261028/scan-validation.json): UV, API y
NiFi pasan con cero hallazgos raw. Trivy identifica rustls0.23.46 y513 registros
Rust en API,1026 en UV/NiFi; no se acepta ausencia de cobertura como limpieza.
El informe original sigue produciendo los cuatro rechazos del gate.

[Smoke API](UV_RUSTLS_REPAIR_20261028/api-smoke.json): health/predict HTTP200,
event_id conservado y hash RF del candidato esperado. UV y UVX ejecutan su
comando de versión; UV también ejecuta dentro de la imagen NiFi. No quedan
contenedores propios de estas comprobaciones. Suite completa706 pruebas y368
subpruebas,7 skips; grupo específico23 pruebas y18 subpruebas. Ruff, inventario,
layout y diff check pasan. La CI remota del nuevo commit no se deduce de estos
resultados locales.
