# Laboratorio CNC Guard en Benten

La VM `9600` (`cnc-guard-integration`) está creada y accesible por SSH. Tiene
4 vCPU, 8 GiB de RAM fija y un disco de 120 GiB. Este entorno permite trasladar
las pruebas y las builds fuera del portátil; disponer de él no acredita el
despliegue completo del proyecto. La [evidencia del 5 de noviembre](../evidence/BENTEN_VM_20261105.md)
separa la preparación del entorno de las verificaciones de los componentes.

## Acceso y comprobación previa

Desde la máquina del coordinador se usa la configuración SSH ya preparada:

```sh
ssh -F /home/tears/.cache/cnc-benten-vm-20261105/ssh_config cnc-guard-vm
```

El alias entra como `cncguard` en `192.168.1.116`, con salto por Benten
(`100.105.11.19`). Ambos hosts exigen comprobación de clave. La clave pública
del invitado se obtuvo mediante el agente QEMU a través de la sesión autenticada
con Proxmox y quedó fijada en un fichero local. No copiar claves privadas al
invitado ni desactivar `StrictHostKeyChecking`.

Esta única llamada comprueba el estado sin arrancar servicios del proyecto:

```sh
ssh -F /home/tears/.cache/cnc-benten-vm-20261105/ssh_config cnc-guard-vm '
  set -eu
  date -u +%Y-%m-%dT%H:%M:%SZ
  hostname
  cloud-init status --long
  free -m
  df -h /opt/cnc-guard
  docker version --format "{{.Server.Version}}"
  docker compose version
  sysctl vm.max_map_count
'
```

Antes de cada campaña, repetir el preflight del runner: CG32 sigue exigiendo
**al menos 6 GiB de RAM disponible y 20 GiB de disco libre**. La memoria asignada
a la VM y una observación anterior no sustituyen esa comprobación. No ejecutar
builds y campañas pesadas en paralelo.

## Código y entornos

`/opt/cnc-guard/checkouts/bootstrap-080b6f9` conserva la revisión histórica
`080b6f9ec41b5f7aacd05fcaef6e9aec0f2ab057`, usada para preparar dependencias.
`/opt/cnc-guard/checkouts/review-ce3c1d7` contiene el snapshot de revisión
`ce3c1d761ab36f5c69458561cb99647a0f951ef3`. No presentar el bootstrap como el
código final desplegado. Para cada nueva revisión, transferir un snapshot
comprometido, verificar SHA-256 y commit, y conservar un checkout limpio.
Los experimentos con cambios pendientes deben tener identidad y evidencia propias.

Los entornos están separados:

| Uso | Intérprete y entorno |
| --- | --- |
| API, archivo y pruebas Python 3.11 | `/opt/cnc-guard/venvs/py311/bin/python` — 3.11.17 |
| API, archivo y pruebas Python 3.12 | `/opt/cnc-guard/venvs/py312/bin/python` — 3.12.14 |
| Dashboard | `/opt/cnc-guard/venvs/dashboard/bin/python` — 3.12.14 |

Los dos primeros se instalaron desde `uv.lock` con todos los grupos y el extra
Kafka. El dashboard usa sus propios requisitos con hashes; no reutilizar el
intérprete del worker para arrancar Streamlit. El uv preparado es 0.13.7 y la CI
fija 0.13.6: la equivalencia exacta con el runner de CI no se da por demostrada.

Antes de probar una revisión, registrar su identidad y el estado del checkout:

```sh
cd /opt/cnc-guard/checkouts/review-ce3c1d7
git rev-parse HEAD
git status --porcelain
sha256sum pyproject.toml uv.lock dashboard_laneki/requirements.txt
```

Ejecutar cada fase pesada con espera y plazo finitos, un solo proceso por el
candado compartido y salida en un directorio nuevo de evidencia:

```sh
flock -E 75 -w 30 /opt/cnc-guard/evidence/remote-heavy.lock \
  timeout 180 COMANDO_DE_LA_FASE
```

`COMANDO_DE_LA_FASE` es un marcador: sustituirlo por el comando revisado y su
intérprete concreto. Un código 75 indica contención del candado, no un resultado
de los tests. Los límites específicos de heap, CPU y contenedor de las sondas
se mantienen. Conservar comando, salida, código de salida, commit y hashes de
las fuentes realmente ejecutadas; no reutilizar una ejecución antigua para
etiquetar cambios nuevos.

## Builds e integración

Construir una imagen cada vez siguiendo [las builds serializadas](LOCAL_IMAGE_BUILDS.md).
Para el candidato NiFi usar [su contexto y sus compuertas](NIFI_CANDIDATE.md):
el overlay y las revisiones de biblioteca no equivalen a una imagen aceptada.
Después de construir, guardar el ID real de cada imagen, ejecutar los escaneos
existentes sin excepciones nuevas y comprobar imports y arranque dentro de ella.

La [campaña opt-in](README.md#real-lab-commands--blocked-until-6-gib-ram-and-20-gib-disk-free)
debe generar sus propios paths, montajes, puertos y estado en esta VM. Usar un
namespace nuevo y un bundle de modelo con la identidad y aceptación exigidas por
el runner. Un modelo local de prueba sigue siendo de prueba. Mantener los puertos
de los servicios en loopback del invitado. El acceso de un navegador mediante
forward SSH se prepara y comprueba aparte; todavía no se acredita aquí.

Retener ledgers, offsets y evidencia al parar la campaña. No ejecutar `down -v`
ni limpiar recursos ajenos. Siguen pendientes las imágenes finales y sus scans,
la campaña completa, las pruebas con classloaders NAR, SMB y las aceptaciones
humana y académica que correspondan. Las revisiones y pruebas de componentes
se documentan por separado.

## Parada y reversión preparada

La VM no tiene arranque automático (`onboot=0`) ni HA. Tras conservar evidencia y
parar los servicios de la campaña, la parada de **esta VM** se puede efectuar
desde el host autorizado con:

```sh
qm shutdown 9600
```

Es una acción preparada, no ejecutada por este documento. Antes de cualquier
eliminación hay que inspeccionar los volúmenes propios y conservar los datos
necesarios; aquí no se da una orden de destrucción. No cambiar otras VMs, el
clúster, HA, firewall, VPN ni la red del host para reproducir el laboratorio.
