# CG02: portabilidad y comprobación de higiene

Base deliberada PR42 `28a77543bfd67a36b96ddc2f4acc103b13f62c2e`; rama
`fix/cg02-portable-inventory`, PR52. La normalización `as_posix()` conserva el
inventario publicado tanto en Windows como en FedoraLinux-43. No se reescribe
el inventario para aceptar una diferencia ni se cambia su contenido.

Tras la composición se resuelven diez diagnósticos heredados de PR42 en
`scripts/audit_cg02.py`: nueve E501 y un E731. Se dividen comentarios y literales
sin cambiar sus valores; el formateador UTC pasa de lambda a def con la misma
expresión. No se añade noqa ni se relaja la configuración.

Validación ejecutada el 21 de octubre de 2026 en Windows/Python 3.11.9 y
FedoraLinux-43/Python 3.11.15:

- Ocho pruebas `test_audit_cg02.py` correctas en ambos sistemas.
- `python -m scripts.audit_cg02 --check`: salida 0 en ambos.
- Ruff 0.17.1 `check --select E,F,I,PLW1510` y `format --check`, sobre el
  script y sus pruebas: salida 0 en ambos sistemas.
- Regeneración en memoria, idéntica byte a byte a `docs/cg02/inventory.json`:
  SHA256 `e2b9239e295ae2dd9b397358e02da290fc8b833c9a9903dad0f9e3a4e8ee5af3`.
  [Windows](CG02_inventory_recheck_windows.json) y
  [Fedora](CG02_inventory_recheck_fedora.json).
- Enlaces locales y `git diff --check` correctos. Datos, modelos, scoring,
  contratos y lock conservan los blobs de PR42.

Solo se leen evidencias congeladas del repositorio; sin SMB/OT ni servicios
compartidos. No se ejecuta la suite completa Windows, cuyo límite POSIX sigue
documentado en PR50. Sin CI manual, Copilot, merge, cierre ni despliegue.
Validación local; revisión independiente, checks remotos y aceptación separados.
