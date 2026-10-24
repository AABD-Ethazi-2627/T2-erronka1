# Mapa de archivos y política de rutas

Todas las órdenes del proyecto parten de la raíz del checkout. Las ramas son
entregas parciales: una carpeta puede aparecer solo cuando se incorpora su issue.
No copiar rutas absolutas de un worktree ni asumir que todas las ramas implementan
el laboratorio completo.

- `docker-compose.yml`: único punto de entrada del laboratorio o esqueleto de la rama.
- `scoring/`: API activa, dependencias y Dockerfile. El contexto del build se define
  en Compose; las versiones con imports de `scripts`/`contracts` usan la raíz.
- `filebeat/`: configuración activa. `nifi-flows/`, `elasticsearch/`, `kibana/`:
  configuraciones y exports revisables de cada componente.
- `scripts/`, `tests/`, `contracts/`: herramientas, regresiones y contratos.
- `data/`: fuentes docentes versionadas; no mover ni sustituir sus CSV al limpiar.
- `notebooks/`: cuadernos fuente; `.ipynb_checkpoints/` es una copia automática local.
- `models/`: bundles generados del esqueleto; `outputs/api/`: bundles del laboratorio
  con manifest. Respetar la ruta de la rama; no cambiar nombres de modelos a ciegas.
- `outputs/`, `historical/`: resultados, capturas y almacenamiento local regenerable.
- `docs/evidence/`: evidencia compacta deliberadamente versionada, con procedencia.
- `docs/issues/`, `docs/requisitos/`, `docs/rubrica/`, `docs/planificacion/`:
  requisitos, planificación y trazabilidad. `ENUNTZIATUA.md` y la presentación
  originales se conservan en raíz para no alterar referencias docentes.
- `docs/templates/infra/`: variante histórica de infraestructura, antes `infra/`.
  Conserva su API y Filebeat propios, diferentes del código activo; no es una
  segunda instalación vigente. No ejecutar su Compose como sustituto del principal.
  Sus rutas relativas se resuelven desde esa carpeta; modelos en `../../../models`.

## Exclusiones

`.gitignore` excluye entornos, cachés, checkpoints, secretos `.env*` y resultados
locales. Permite `.env.example` y `.env.*.example`. No excluye CSV/JSON/imágenes
por extensión: ocultaría fuentes, fixtures o evidencia. `uv.lock` se versiona.
No se borran capturas, exports, prototipos ni archivos ajenos durante esta reparación.
Los checkpoints ya versionados se retiran del índice conservando la copia local.
La plantilla histórica exige `CNC_NIFI_PASSWORD` y `CNC_STREAM_DIR`, sin valores
predeterminados ni credenciales CIFS. El directorio de entrada debe existir y
estar montado localmente; Filebeat lo recibe de solo lectura. Para NiFi se debe
proporcionar una contraseña privada de al menos 12 caracteres fuera de Git.
Todos sus puertos se publican en `127.0.0.1`, con TLS/autenticación en NiFi y
allowlist Host `localhost:8443,127.0.0.1:8443`. No incorpora un override LAN;
el Host permitido no sustituye la validación del certificado TLS del servidor.
Esta protección no convierte la plantilla antigua en la instalación vigente.

## Verificación sin iniciar servicios

```bash
python3 scripts/check_repository_layout.py
python3 scripts/check_lab_compose.py
```

Requiere Git y Docker Compose v2; no necesita daemon. Revisa el índice, las reglas
de exclusión, el contexto/Dockerfile/COPY y los bind mounts estáticos del Compose
principal. Las rutas generadas `outputs/` y `models/` se permiten sin crearlas.
No acredita que la API docente esté completa ni que exista una integración viva.
La CI ejecuta esta comprobación en PR y bajo petición manual.
El segundo comando valida por separado la plantilla histórica con valores
ficticios y un directorio de fixtures del checkout. Comprueba puertos privados,
TLS/autenticación, rutas, entrada de solo lectura y rechazo de variables ausentes
o vacías mediante `docker compose config`. No monta SMB ni inicia contenedores.
