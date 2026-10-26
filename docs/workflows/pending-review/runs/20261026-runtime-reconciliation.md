# Reconciliación de runtime y revisión — 26/10/2026

## Resultado técnico y revisión

La revisión independiente del código `01a5f2b` terminó sin hallazgos accionables
en su alcance: 40 pruebas inertes pasan sin skips; siete informes reales aceptados
y 42 mutaciones negativas rechazadas. `VERIFIED_FINDINGS` es idéntico al de la
base. [Recibo de revisión](../../../evidence/CODE_REVIEW_20261026.json).

El agente runtime construyó las nueve imágenes del commit `b7b9c05` y ejecutó
sus nueve escaneos/gates, los tres verificadores ES y tres consultas dashboard.
Los inputs copiados por esos Dockerfiles no cambiaron hasta `80f57f2`; el padre
lo comprobó por Git. Observabilidad, cleanup y gate no forman parte del código
copiado en esas imágenes. No se atribuye ejecución al resto del árbol nuevo.

El padre verificó 9/9 hashes de JSON, ImageID de build/inspect/scan, DiffIDs,
argumentos `--input` independientes del informe y exits individuales. Después
pasó los nueve JSON por el **gate reforzado actual**, suministrando el nombre
del TAR desde el comando de escaneo registrado: cero errores. No se eligió
`expected_artifact` a partir del propio JSON. [Recibo público compacto](../../../evidence/RUNTIME_VALIDATION_20261026.json).

| Imagen | Targets | Registros de paquetes | Avisos raw |
| --- | ---: | ---: | ---: |
| API | 3 | 576 | 0 |
| Elasticsearch | 2 | 1022 | 0 |
| Filebeat | 2 | 247 | 1 UNKNOWN |
| Kafka | 2 | 189 | 0 |
| Kibana | 2 | 2370 | 3 HIGH |
| Mock Python | 1 | 29 | 0 |
| NiFi | 4 | 1206 | 0 |
| Python | 1 | 34 | 0 |
| Wolfi | 1 | 19 | 0 |

Son 18 targets y 5692 registros por target; no paquetes únicos. Se conservan
los tres escaneos remotos UV/HAProxy/Go del integrador, sin repetirlos sin causa.
Los avisos del scanner se conservan, sin rebajar severidad ni ampliar excepciones.

## Disposición de los cuatro avisos existentes

- Filebeat: GO-2026-5932 (UNKNOWN) corresponde al paquete OpenPGP no mantenido
  de `x/crypto`, según el [registro primario Go](https://vuln.go.dev/ID/GO-2026-5932.json).
  En el binario exacto reconstruido, govulncheck v1.9.0 detecta el aviso a nivel
  módulo pero cero paquetes/símbolos afectados vinculados. Se conserva el
  diagnóstico; la disposición es alcanzabilidad verificada en ese binario.
- Kibana: se mantienen tres HIGH en versiones con backports propios. La prueba
  RSA rechaza el vector asociado al [parche propuesto en forge](https://github.com/digitalbazaar/forge/pull/1152).
  Las pruebas de extract-zip rechazan symlink fuera del destino y symlink seguido
  de archivo duplicado, conservando el control de ZIP válido. Los avisos primarios
  [CVE-2026-19693](https://github.com/advisories/GHSA-7pqw-9j4j-h8q3) y
  [CVE-2026-56876](https://github.com/advisories/GHSA-jmr9-qjv8-65gv) describen
  esas rutas. La mitigación local se infiere de código y pruebas propias;
  no se afirma que el proveedor haya publicado una versión corregida.

El padre abrió y contrastó esas cuatro fuentes primarias el 26/10/2026. No se
declara cero avisos ni cobertura universal del código embebido. Los warnings
de PURL/SBOM se contrastaron contra las bases APK extraídas: ES 73/73, Kibana
67/67 y Mock Python 29/29 paquetes/versiones instalados están en los informes.

## ES ejecutado y portabilidad pendiente de incorporar

Los scripts contract/ingest/durable terminaron exit0 con 89/93/17 operaciones;
el archivo dashboard ES terminó con tres pruebas y cero skips. Se fijaron image
ID, UUID y pertenencia antes de usar o limpiar recursos. Se usaron dobles
sintéticos en memoria; no modelos de entrega, entrenamiento, Kafka/NiFi real o
servicios OT/SMB. Las consultas dashboard no validan el renderizado de Kibana.

La ejecución empleó un adaptador externo explícito: seleccionó el ID reconstruido,
dirigió Docker al socket propio y resolvió hostname a loopback sin relajar
aserciones ni timeouts. El relay temporal Windows validó HTTP real y UUID;
no demuestra forwarding WSL nativo. Esa adaptación motivó corregir la interfaz
de los tres verificadores para que admitan imagen/motor/ruta ext4 explícitos.
Un agente trabaja esos cambios sin arrancar servicios; aún requieren su propia
validación y no se cubren por los PASS anteriores.

## Incidente: el primer arranque no respetó D:

El primer dockerd propio se conectó al containerd del sistema. Modificó metadatos
en `/var/lib/containerd/io.containerd.metadata.v1.bolt/meta.db`, archivo previo
de 16 MiB en el VHD C:. Fue un fallo de aislamiento. No había hash/snapshot
previo de esa base y **no se puede cuantificar o restaurar con seguridad el
delta exacto**. No se borró ni sobrescribió información compartida para ocultarlo.

Se corrigió usando containerd propio, con root/state/socket/namespaces en D:.
Los casos ES finalmente exitosos y las pruebas de backports/alcanzabilidad
usaron ese runtime corregido. No se afirma cumplimiento íntegro de D: durante
toda la ejecución, aunque sus imágenes/capas/cachés se conserven en D:.

Tras el cierre, el padre releyó el motor original: mismo ID y data-root que el
baseline, cero imágenes y contenedores como antes, namespaces `moby` y
`moby_history` sin contenedores ni tareas. El filesystem propio está desmontado.
Eso acredita recuperación operativa observada, no igualdad byte a byte de la
base de metadatos. Recibo privado: `shared-engine-recovery-readback.json`.

No repetir los scripts históricos `setup-runtime*.sh`/`first-build.sh`. Para
reanudar: procedimiento final conservado en `D:/cnc-guard-runtime-20261026`,
sin reformatear `storage.ext4`; confirmar ext4/backing file, configurar containerd
con socket propio explícito, comprobar la conexión de dockerd a ese socket antes
de iniciar cualquier build y verificar pertenencia antes de parar recursos.
No se ha modificado ni parado el daemon original.

## Fuentes, conservación y aceptación

Se conservan TAR de imágenes, JSON, logs y datos propios en D:. `storage.ext4`
tiene 64 GiB lógicos y unos 10,47 GB asignados al terminar; no se eliminó.
Las referencias completas y hashes están en el recibo enlazado, los raw en
`D:/cnc-guard-runtime-20261026`. No se publican esos raw ni bases locales.

El código puede revisarse con estas evidencias; CI, publicación y aceptación
global siguen separados. La credencial Projects, actos humanos, decisiones
docentes y campaña CG32 continúan abiertos. El incidente histórico también
permanece visible; no se convierte en conformidad por documentarlo.
