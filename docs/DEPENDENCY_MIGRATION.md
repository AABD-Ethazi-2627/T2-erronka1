# Actualización de dependencias del laboratorio

Esta actualización prepara código y configuración para revisión. El PR no ejecuta
una migración, no cambia un modelo servido ni detiene servicios existentes.

## Entorno Python y API

`pyproject.toml` fija las dependencias directas y `uv.lock` todas las resoluciones.
El grupo `runtime` selecciona las ocho bibliotecas de serving; sus alias sin
versión heredan la resolución conjunta del proyecto. No es otro resolvedor.

Desde la raíz, para preparar y comprobar un cambio deliberado:

```bash
uv sync --frozen --python 3.11 --all-groups --extra kafka
uv run --frozen python -m scripts.export_runtime --check
uv run --frozen python -m scripts.image_inventory --check
uv run --frozen python -m scripts.build_refreshed_lab_flow --check
```

Si se modifica una dependencia, actualizar primero el lock con `uv lock` y después
`uv run --frozen python -m scripts.export_runtime`. Commitear los tres archivos;
CI rechaza el export desfasado. El Dockerfile instala únicamente esa clausura con
uv 0.13.5, hashes obligatorios y wheels; la imagen Python y el binario uv tienen
digests verificados. El binario uv también queda sujeto a la auditoría de tooling.
La base Debian 13 utiliza un snapshot firmado y seis paquetes de seguridad con
versión exacta en `scoring/debian-security.txt`. `Check-Valid-Until: no` permite
reproducir ese snapshot histórico; la comprobación de firmas sigue activa.
Se retiran pip/setuptools/wheel del runtime, incluidos los bundles de ensurepip.
La API corre sin capacidades, con `no-new-privileges` y raíz de solo lectura;
solo `/state` y el tmpfs acotado de `/tmp` permiten escritura.

La revisión de todas las versiones y los experimentos de compatibilidad se
encuentran en [el informe de dependencias](evidence/DEPENDENCY_REVIEW_20261023.md).
No actualizar scikit-learn/numpy/pandas en una API que siga cargando el bundle
anterior: el manifiesto exige la versión de scikit-learn con la que se entrenó.
Una futura migración científica necesita reentrenamiento, empaquetado y nueva
evidencia en rutas nuevas, conservando las particiones y el alcance AI4I aprobado.

## Imágenes y almacenamiento

`deploy/images.json` registra cada tag y digest del conjunto activo. Compose y el
Dockerfile repiten esas referencias para permitir actualizaciones revisables por
Dependabot; `scripts.image_inventory --check` rechaza su divergencia.

El Compose principal usa **cnc-guard-lab-v2**, un espacio nuevo para contenedores,
red y volúmenes. El material anterior permanece en el proyecto antiguo. Los puertos
son los mismos y siguen en loopback: si el laboratorio antiguo está activo, el
nuevo no podrá apropiarse de sus puertos. Elegir explícitamente el momento de una
futura transición; no parar otros proyectos para hacer pasar una prueba.

Antes de esa transición, registrar las imágenes/digests y respaldar configuración,
flujos, colas, offsets, ledgers e índices del laboratorio que realmente se quiera
migrar. Verificar la restauración en almacenamiento separado. Nunca conectar
directamente NiFi 2.12 o Kafka 4.3 a los volúmenes originales sin ensayar la ruta de
actualización admitida por el proveedor. No ejecutar `down -v` ni copiar repositorios
de NiFi mientras estén escribiendo.

Elasticsearch no admite un downgrade de los datos por cambiar el tag. Una vuelta
a la versión anterior necesita un clúster vacío de esa versión y restaurar su
snapshot compatible. [Guía de actualización de Elastic](https://www.elastic.co/docs/deploy-manage/upgrade/deployment-or-cluster/elasticsearch).

## NiFi 2.12

Usar el export `nifi-flows/cnc_lab_completed_nifi_2.12.0.json`, generado desde la
fuente 2.0 preservada con `scripts.build_refreshed_lab_flow`. No basta con cambiar
las versiones de los bundles: varios nombres de propiedad han cambiado.
`tests/fixtures/nifi-2.12-lab-components.json` recoge descriptores obtenidos del
API de la imagen oficial; la conversión conserva Groovy, esquemas, topics,
identificadores y conexiones. El nuevo export deshabilita los componentes.

La API de Elasticsearch del laboratorio continúa sin autenticación, limitada a
loopback/red Docker propia. Su controller service usa `Authorization Scheme=NONE`
para reflejar esa configuración; no es una receta para un clúster autenticado.
En un futuro entorno con autenticación hay que configurar sus credenciales y
certificados privados, no reutilizar ese ajuste del laboratorio.

Después de importar, comprobar el remapeo de referencias, habilitar los servicios
necesarios y validar todos los procesadores antes de planificar la ejecución.
Una importación correcta acredita compatibilidad de configuración; no acredita
consumo, ACK, persistencia ni el grafo completo con datos reales.

## Referencia histórica

`docs/templates/infra/` conserva las versiones antiguas con propósito documental.
Sus seis servicios requieren el perfil `historical-archive-only`; un arranque sin
perfil no selecciona ninguno. `scripts.check_lab_compose` solo hace validación
estática con valores ficticios. No incorporar ese perfil a los comandos activos.

## Auditoría continua

`python -m scripts.audit_dependencies --latest --output reporte-nuevo.json`
consulta todas las entradas del lock y uv; no sobrescribe reportes existentes.
Requiere acceso a PyPI. Un error de consulta o una fuente no cubierta falla.

El workflow `Dependency audit` se ejecuta en PR, semanalmente y bajo petición.
Conserva el JSON completo de cada imagen, incluidos avisos sin parche. El gate de
la API bloquea HIGH/CRITICAL corregibles; los scans de imágenes oficiales externas
son informativos sobre vulnerabilidades y fallan si el scanner no puede completar
el análisis. CI verde no significa que esas imágenes estén libres de CVE.
No hay despliegue, publicación de imágenes ni auto-merge.

Dependabot propone cambios semanales. Revisar sus releases y scans, sincronizar
`deploy/images.json` y regenerar el export runtime antes de aceptar. Los paquetes
Debian y la fecha del snapshot requieren actualización deliberada con un build y
scan nuevos; sus pins no se actualizan automáticamente con Dependabot.
