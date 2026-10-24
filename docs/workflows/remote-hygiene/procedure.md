# Procedimiento de higiene remota

1. Ejecutar `git fetch --prune` y registrar cada rama remota con su SHA.
2. Consultar todos los PR abiertos y proteger sus ramas `head` y `base`, `main`
   y cualquier rama usada por un worktree activo.
3. Actualizar ramas vivas en worktrees aislados; validar pruebas, lint y gates
   específicos antes de publicar.
4. Publicar solo con `--force-with-lease` ligado al SHA observado.
5. Cerrar PR ya integrados o documentalmente superados antes de borrar su rama.
6. Para cada borrado, volver a comprobar SHA y ausencia en PR abiertos; borrar
   solo la referencia remota exacta. No borrar ramas locales ni worktrees.
7. Repetir `fetch --prune` y confirmar que solo quedan ramas vivas o protegidas.

Condición de parada: cualquier cambio de SHA, PR nuevo, fallo de validación o
hallazgo de seguridad pendiente impide publicar, borrar o declarar aceptación.

