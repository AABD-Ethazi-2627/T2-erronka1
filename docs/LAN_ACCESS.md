# Acceso directo al laboratorio desde la LAN

El Compose base conserva los puertos en `127.0.0.1`. El archivo
`docker-compose.lan.yml` añade cinco puertos en **una IP LAN concreta del
servidor**. Cada estudiante usa su propio certificado de cliente. NiFi mantiene
su autenticación interna; el gateway comprueba además el certificado de cliente
y verifica el certificado TLS de NiFi antes de reenviar tráfico.

| Servicio | URL o broker desde otro equipo | Control LAN |
|---|---|---|
| NiFi | `https://IP-SERVIDOR:18080/nifi` | mTLS + login NiFi |
| Kafka | `IP-SERVIDOR:19092` | mTLS, cliente Kafka `SSL` |
| Elasticsearch | `https://IP-SERVIDOR:19200` | mTLS |
| Kibana | `https://IP-SERVIDOR:15601` | mTLS |
| Scoring API | `https://IP-SERVIDOR:18001/docs` | mTLS |

La CA y las claves privadas **no se guardan en Git**. En el servidor, generar
fuera del checkout un directorio nuevo con cuatro certificados distintos:

```bash
bash scripts/create_lan_certs.sh IP-SERVIDOR /ruta/privada/cnc-lan-certs
```

El script rehúsa sobrescribir el directorio. `gateway/` contiene solo el
certificado y clave del gateway y la CA pública de los clientes; `private/`
contiene la clave de la CA; `clients/` contiene los pares de cada estudiante.
Entregar a cada persona **solo** su par `student-N.crt`/`student-N.key` y
`ca.crt` mediante un canal privado. No compartir `private/`: también contiene
copias de las claves de servidor y clientes, además de la clave de la CA.

**No hay revocación individual ni CRL en este overlay.** Reemitir un certificado
bajo la misma CA no invalida el anterior. Si una clave se pierde o sale del
equipo autorizado, aplicar la rotación completa descrita abajo; no basta con
entregar otro certificado al estudiante afectado.

Antes de arrancar el gateway, copiar a `gateway/nifi-ca.pem` el certificado
de confianza de la instancia NiFi que ya funciona en loopback y verificar su
huella en el servidor. `CNC_NIFI_CERT_NAME` debe coincidir con el nombre que
aparece en ese certificado. El gateway falla al iniciar si falta el archivo o
si la identidad de NiFi no coincide. Si NiFi regenera su certificado, renovar
esta confianza antes de volver a abrir el acceso LAN.

Configurar en el servidor, usando su IP real en vez de la IP de ejemplo:

```bash
export CNC_LAN_BIND_IP=IP-SERVIDOR
export CNC_LAN_HOST=IP-SERVIDOR
export CNC_LAN_CERT_DIR=/ruta/privada/cnc-lan-certs/gateway
export CNC_LAN_CERT_UID="$(id -u)"
export CNC_LAN_CERT_GID="$(id -g)"
export CNC_NIFI_CERT_NAME=NOMBRE-DEL-CERTIFICADO-NIFI
docker compose -f docker-compose.yml -f docker-compose.lan.yml --profile dashboard config -q
docker compose -f docker-compose.yml -f docker-compose.lan.yml --profile dashboard up -d
```

El gateway publica solo en `CNC_LAN_BIND_IP`. El broker mantiene el listener
interno `kafka:9092` para Filebeat/NiFi y anuncia el listener externo
`CNC_LAN_HOST:19092` para clientes LAN. Kafka en ese puerto es TLS hacia el
gateway y tráfico interno dentro de la red Docker. No apuntar clientes LAN a
`kafka:9092`.

Comprobación desde otro equipo, con el par de certificado de un estudiante:

```bash
curl --cacert ca.crt --cert student-1.crt --key student-1.key \
  https://IP-SERVIDOR:18001/health
kcat -b IP-SERVIDOR:19092 -X security.protocol=ssl \
  -X ssl.ca.location=ca.crt \
  -X ssl.certificate.location=student-1.crt \
  -X ssl.key.location=student-1.key -L
```

Sin certificado de cliente, la negociación TLS debe fallar. La comprobación
local de Compose y certificados no acredita el acceso real desde los cuatro
equipos; verificar desde cada uno, incluyendo NiFi y Kibana, antes de dar por
operativo el laboratorio. No abrir más interfaces ni usar `0.0.0.0` para el
bind externo. Conservar volúmenes y evidencias al parar el laboratorio.

## Emergencia: retirar todos los certificados anteriores

La unidad de revocación de este laboratorio es la **CA completa**, para los
cinco puertos y los cuatro estudiantes. Habrá una interrupción del acceso LAN.
No se modifican Kafka, NiFi, los otros servicios o sus volúmenes.

1. En el servidor, con las variables de Compose del gateway actual, detener
   **solo** el gateway y esperar a que el comando termine:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.lan.yml --profile dashboard stop --timeout 10 lan-gateway
   docker compose -f docker-compose.yml -f docker-compose.lan.yml --profile dashboard ps --status running --services
   ```

   `lan-gateway` no debe aparecer entre los servicios en ejecución. No continuar
   mientras siga activo. Esto debe cortar también las conexiones existentes.
   Una recarga suave, reemplazar archivos o reiniciar solo clientes no basta:
   las sesiones Kafka activas pueden seguir enviando datos sin agotar su timeout.

2. Conservar el directorio anterior protegido para investigar el incidente.
   Generar una CA, servidor y cuatro pares de cliente nuevos en otro directorio
   fuera de Git. No reutilizar claves, no copiar la CA anterior al nuevo gateway
   y no concatenar ambas CA:

   ```bash
   OLD=/ruta/privada/cnc-lan-certs-anterior
   NEW=/ruta/privada/cnc-lan-certs-nuevo
   bash scripts/create_lan_certs.sh IP-SERVIDOR "$NEW"
   openssl x509 -in "$OLD/gateway/clients-ca.pem" -noout -fingerprint -sha256
   openssl x509 -in "$NEW/gateway/clients-ca.pem" -noout -fingerprint -sha256
   ```

   Las huellas deben ser distintas. El script rehúsa un destino ya existente.
   Copiar únicamente la confianza pública de NiFi a `"$NEW/gateway/nifi-ca.pem"`,
   desde la fuente verificada de la instancia, y volver a comprobar su huella.
   Esa confianza es independiente de la CA de clientes; no regenerar NiFi.

3. Entregar a **cada uno de los cuatro estudiantes** su nuevo par y el nuevo
   `clients/ca.crt` por canal privado. La CA del servidor también cambia;
   actualizar la confianza de todos los clientes, sin desactivar la verificación
   TLS. Comprobar antes de abrir el gateway:

   ```bash
   for n in 1 2 3 4; do
     openssl verify -purpose sslclient -CAfile "$NEW/gateway/clients-ca.pem" "$NEW/clients/student-$n.crt" || exit 1
     if openssl verify -purpose sslclient -CAfile "$NEW/gateway/clients-ca.pem" "$OLD/clients/student-$n.crt"; then
       echo "ERROR: se sigue confiando en un certificado anterior" >&2
       exit 1
     fi
   done
   ```

4. Cambiar el montaje al directorio **nuevo** y recrear únicamente el gateway:

   ```bash
   export CNC_LAN_CERT_DIR="$NEW/gateway"
   docker compose -f docker-compose.yml -f docker-compose.lan.yml --profile dashboard config -q
   docker compose -f docker-compose.yml -f docker-compose.lan.yml --profile dashboard up -d --no-deps --force-recreate lan-gateway
   ```

   No usar solo `restart`: no aplica el nuevo directorio montado. No restaurar
   la CA anterior como rollback del incidente; si hay un error, mantener cerrado
   el gateway hasta corregir la configuración nueva.

5. En cada puerto, probar tráfico con los cuatro pares nuevos y rechazo de los
   cuatro antiguos y de un cliente sin certificado. Para aislar el rechazo del
   cliente antiguo, la prueba negativa debe confiar en **la CA nueva del servidor**
   y presentar **el par antiguo**. Verificar envío y recepción, no solo la apertura
   del socket TLS. Confirmar que ninguna conexión anterior continúa operativa.
   Conservar los resultados y huellas públicas sin guardar claves en los informes.

La prueba aislada `tests/test_lan_ca_rotation.py` usa los cinco frontends y
backends de eco sintéticos; la CI la ejecuta con la imagen HAProxy fijada en
`deploy/images.json`. Comprueba los cuatro pares antes/después, conexiones
abiertas y rechazo de sesiones TLS anteriores. No sustituye el ensayo desde
los cuatro equipos del laboratorio ni aplica una rotación a servicios reales.

Referencias: [verificación de clientes HAProxy](https://docs.haproxy.org/3.2/configuration.html#5.1-verify),
[conexiones durante soft-stop](https://docs.haproxy.org/3.2/configuration.html#3.1-hard-stop-after)
y [recreación de servicios Compose](https://docs.docker.com/reference/cli/docker/compose/up/).
