# Acceso SSH restringido para CG14

Host Omarchy/Arch; OpenSSH 10.6p1 está instalado. En la inspección actual, `sshd` está `inactive` y `disabled`, no escucha en el puerto 22 y no hay host keys legibles en `/etc/ssh`. `sshd -t` sobre la configuración instalada falla con `no hostkeys available`; no se habilitó el servicio ni se cambiaron usuarios, llaves, firewall o configuración del sistema.

La plantilla `99-cg14-tunnel.conf.example` solo restringe un usuario de túnel y una IP `/32`; no impone una política global sobre root ni otros usuarios. Validé `sshd -t` y `sshd -T -C` sobre una copia temporal del candidato con una host key efímera de auditoría: sintaxis válida y resultado efectivo `publickey`, forwarding TCP `local`, `PermitOpen 127.0.0.1:18443`, sin stream-local, GatewayPorts no, shell/TTY/túnel/agent/X11 deshabilitados y `MaxSessions 0`. Esta prueba valida el candidato; no valida host keys reales ni el servicio instalado para arrancar. La key temporal y la copia se eliminaron.

## Preparación administrativa pendiente

Un administrador debe, desde consola local o una sesión SSH alternativa que conserve abierta:

1. En consola local o una sesión administrativa alternativa que se mantendrá abierta, revisar `systemctl status sshd`, `ss -lntp`, `/etc/ssh/sshd_config`, todos los drop-ins y la política efectiva del firewall (`nft list ruleset`, `iptables -S` e `ip6tables -S`, según backend). Los comandos pueden requerir privilegios de lectura. El servicio `sshd` está instalado pero deshabilitado; no habilitar hasta completar las verificaciones.
2. Confirmar/crear host keys con el mecanismo de la distribución y validar sus permisos.
3. Crear un usuario individual por compañero, sin acceso de administración, y recopilar su clave pública ED25519 por un canal fiable. No copiar claves privadas.
4. Añadir una línea por clave en `~/.ssh/authorized_keys`, con permisos y propiedad correctos. Para limitar también la clave:

   ```text
   restrict,port-forwarding,permitopen="127.0.0.1:18443" ssh-ed25519 AAAA... comentario
   ```

   `permitopen` en `sshd_config` limita el destino de forwarding. Limitar origen con `Match User ... Address <IP_AUTORIZADA>/32`; usar una dirección estable/reservada por compañero.
5. Sustituir el usuario/IP de la plantilla para cada persona. No crear una cuenta compartida. El bloque restringe cada cuenta a clave pública y forwarding local hacia NiFi, sin shell (`MaxSessions 0`), PTY, agente, X11, stream-local, túneles TUN ni forwarding remoto. La plantilla no cambia la política root global; no crear una cuenta de túnel llamada root.
6. Ejecutar `sshd -t` y resolver cualquier error antes de recargar. Después inspeccionar la configuración por conexión con `sshd -T -C user=<cuenta>,addr=<IP_autorizada>,host=<hostname>` y probar la clave en una sesión nueva, manteniendo abierta la sesión de administración existente.
7. Preparar rollback antes de habilitar: guardar copia con permisos del drop-in existente; si falla la prueba de conexión desde una segunda sesión, detener/deshabilitar únicamente `sshd` si esta iteración lo inició y retirar solo el nuevo drop-in/usuario autorizado. No revertir cambios de terceros. Habilitar `sshd` solo con autorización administrativa, configuración efectiva revisada y host keys válidas. No abrir el puerto 22 en el router; permitirlo en firewall solo desde IPs autorizadas.

Estado: servicio y listeners verificados como inactivos/sin listener. Sintaxis instalada: **BLOCKED** por ausencia de host keys. Sintaxis/valores efectivos del candidato temporal: **VERIFIED**, pero su aplicación y prueba de autenticación real requieren autorización administrativa, identidad de usuario, IP de origen estable y clave pública autorizada.

## Conexión desde los equipos autorizados

Linux/macOS, Windows OpenSSH o PowerShell:

```bash
ssh -o ExitOnForwardFailure=yes -N -L 127.0.0.1:18443:127.0.0.1:18443 USUARIO@192.168.75.205
```

Abrir <https://localhost:18443/nifi>. Verificar el certificado público local de NiFi por una huella comunicada en un canal confiable y confiarlo en el dispositivo cliente. El certificado actual es de desarrollo/autofirmado; el túnel no reemplaza la validación TLS. El usuario único configurado en NiFi no proporciona identidades ni permisos NiFi individuales. Para separar roles se requiere OIDC/LDAP y autorización RBAC.

Verificación desde cliente autorizado, pendiente: mantener el túnel abierto; comprobar acceso sin credenciales (401) y luego autenticado (200). En curl, usar `--user <usuario>` sin contraseña para que la solicite de forma interactiva y `--cacert nifi-local.crt`; no incluir contraseña en comando o historial. Comprobar también que falla el forwarding a un destino distinto de `127.0.0.1:18443`, cerrar con Ctrl+C y repetir la conexión directa a `https://192.168.75.205:18443/nifi` desde el segundo equipo para confirmar rechazo. Ninguna de estas pruebas remotas se ejecutó porque no había un segundo equipo autorizado disponible.

Comando de prueba autenticada tras abrir el túnel:

```bash
curl --cacert nifi-local.crt --user USUARIO_NIFI \
  https://localhost:18443/nifi-api/flow/about
```

Para probar la restricción de destino, abrir un segundo túnel hacia un puerto no permitido en un puerto local de prueba y solicitar una conexión; el canal debe ser denegado por `PermitOpen`:

```bash
ssh -o ExitOnForwardFailure=yes -N \
  -L 127.0.0.1:18445:127.0.0.1:1 USUARIO@192.168.75.205
curl --max-time 3 http://localhost:18445/
```

El segundo comando debe fallar y el cliente SSH debe informar que el canal fue rechazado administrativamente. Cierra ambos túneles con Ctrl+C y confirma que `https://localhost:18443/nifi` deja de responder. No se ejecutaron estas pruebas desde un equipo remoto en esta iteración.
