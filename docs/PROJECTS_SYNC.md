# Sincronización del planning T2-erronka1

Fuente: https://github.com/orgs/AABD-Ethazi-2627/projects/2
Destino: https://github.com/orgs/AABD-Ethazi-2627/projects/1

El workflow `sync-projects.yml` se ejecuta a las 00:17, 08:17 y 16:17 UTC
(GitHub puede retrasarlo), y manualmente desde Actions. Debe estar en `main`.
No se ejecuta en pushes ni PRs y nunca escribe en Project #2.

## Activación por un administrador

Configurar el secret de Actions `PROJECTS_SYNC_TOKEN` en este repositorio:
Settings → Secrets and variables → Actions. Usar una credencial dedicada,
con permiso para leer las issues del equipo y escribir en ambos Projects.
El GITHUB_TOKEN del runner no basta para Projects de organización.
Preferir una GitHub App; este workflow recibe un token ya disponible.
Si se usa un PAT clásico, necesita scope `project` y acceso al repositorio
(`repo` si es privado); respetar las políticas de autorización de la organización.
La credencial necesita también permiso para actualizar campos de las issues.
No copiar una sesión OAuth personal de `gh` al repositorio.

Después ejecutar manualmente primero con `dry_run=true`, después con false.
Revisar el resultado y el resumen en Actions. Si falta el secret, falla con
un error explícito; publicar el workflow no significa que ya esté activo.

## Qué se sincroniza

- Las mismas issues/PRs de T2-erronka1, identificadas por ID, sin duplicarlas.
- Responsables, título, cuerpo y comentarios son comunes porque se comparte
  la misma issue. No se modifican desde este script.
- `Taldea = B-taldea`.
- `Status`: Egiteke → To do; Lanean/Berrikusten/Blokeatuta → In Progress;
  Eginda → Done. El detalle completo sigue disponible en Project #2.
- Hasiera-data → Start date; Amaiera-data → Target date. Si las fechas vascas
  están vacías, usa Start date/Target date del origen. Dos fechas distintas
  para el mismo concepto provocan error antes de escribir.
- Borrar un estado o fecha en origen limpia ese campo gestionado en destino.

No borra ni archiva elementos; quitar/archivar una tarea en #2 no la elimina
 del central. No crea campos en el central ni copia prioridad/área (no existen
 allí). Otros campos y tareas de otros equipos se conservan. Cambios manuales
 en los tres campos gestionados del central serán reemplazados por #2.
Borradores deben convertirse en issues antes de sincronizar; contenido ajeno
al repositorio o conflictos de equipo abortan la operación.

## Verificación local

Python estándar, sin dependencias adicionales:

```bash
python3 -m unittest discover -s tests
python3 scripts/sync_projects.py          # lectura, sin cambios
python3 scripts/sync_projects.py --apply  # escritura y verificación posterior
```

Requiere `gh` autenticado con acceso a Projects. Se pagina todo el tablero,
se comprueba el plan antes de escribir y solo se actualizan diferencias.
Las mutaciones no son transaccionales: un fallo de red puede dejar una pasada
parcial. Reejecutar es seguro y completa los cambios pendientes. Concurrency
impide solapar ejecuciones de este workflow; si alguien edita durante la
pasada, la comprobación final falla y pide reejecutar.

Start date y Target date son campos compartidos de issue en esta organización.
Se actualizan mediante updateIssueFieldValue y serán visibles también en #2.
Las fechas vascas del #2 tienen prioridad; no editar fechas inglesas de forma
contradictoria. La prioridad y el área se mantienen exclusivamente en #2.
