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
`ca.crt` mediante un canal privado. Revocar y reemitir certificados si una
clave se pierde o sale del equipo autorizado. No compartir `private/`.

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
