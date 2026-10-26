# Estado de revisión de pendientes

26/10/2026: composición técnica local revisable; validación dinámica incompleta.

- Worktree: `C:/Users/unaiu/.t3/worktrees/B-taldea/t3-6a929eaa`.
- Rama: `kali/integrate-branch-readiness`.
- Código validado: `ae0d3bb5e2a01246193de0ae9fb4d5ec922932c7`;
  árbol `259573a450c5d5683fdfdfdd1079ca6631b9a919`.
- Integra como ancestros `06510ad`, PR91 `b8b4ff5`, PR93 `4ff9768`, PR95
  `b02e620`, guard CG26 `4a6e01a` y arreglo Windows remoto `82ae770`.
  PR96 `716c940` solo inspeccionada, fuera del árbol.
- Correcciones propias: expectativa del mensaje canónico de Projects y rechazo
  de informes de imágenes sin identidad/targets. Sin nuevas supresiones.
- Pytest: 666 passed, 324 subtests, 3 skips ES; unittest: 374 pruebas, 3 skips.
  Ambos `-W error`, exit 0. Once checks repo pasan. Research: 22 pruebas y
  smoke50 completo sin warnings; estudio sellado no repetido.
- Auditoría PyPI: 90 filas, sin errores ni grupos activos; rueda local solo
  cubierta por avisos upstream y regresiones. Trivy: uv/HAProxy/Go analizadas,
  JSON con cobertura y sin avisos; no cubre las nueve imágenes construidas.
- CG25: 191 hashes actuales y 18 históricos verificados; manifiesto sin cambios.
- Artefactos: `D:/cnc-guard-integration-20261026`; modelos, cachés y temporales
  nuevos allí. Entornos compartidos sin modificar.
- No hay procesos propios pendientes, subagentes ni watchers. No hubo push, PR,
  merge remoto, cambios de Projects, contenedores creados/parados ni intervención
  en otros worktrees. El padre mantiene rendimiento y aceptación por separado.

Siguiente acción: revisión independiente del padre y motor Linux propio con
almacenamiento en D: para construir/escanear las nueve imágenes y ejecutar los
tres casos ES con UUID verificado, loopback y comprobación de pertenencia antes
de detener recursos. Docker Desktop no tiene pipe; Fedora Docker usa data-root
en C: y no tiene caché reutilizable. No se usa para nuevas builds.

[Run actual, comandos y límites](runs/20261026-integration.md) ·
[Recibo con hashes de logs](runs/20261026-integration-checks.json).
El [run del 23/10](runs/20261023.md) y su estado en `06510ad` son históricos;
su evidencia de ejecución no equivale a validación del árbol nuevo. Aceptación
docente, ensayo, entrega e integración industrial siguen sin acreditarse aquí.
