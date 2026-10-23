# Estado de la exploración ML, 23/10/2026

Objetivo: ejecutar #83–#89 y recomendar con evidencia; sin cambiar el modelo servido.
Worktree T3: `C:/Users/unaiu/.t3/worktrees/B-taldea/t3-e86974d3`.
Rama: `kali/ml-alternatives-kalista-study`; base remota verificada:
`41cb66f0f3a967bcc4e72c6e251586898edceee9`.

Leídas políticas globales Windows, política MKDL, instrucciones heredadas y cuerpos
y comentarios actuales de #83–#89 (sin comentarios al iniciar). No hay AGENTS.md
versionado. Worktree limpio al comenzar. El remoto B-taldea redirige al mismo main
que T2-erronka1. No se usan checkouts anteriores ni sus outputs.

Hardware observado: Ryzen 5 7600X, 6C/12T; RAM 31,1 GiB, ~7,8 GiB disponibles;
RTX 5070 Ti 16 GiB, driver 630.20, ~2,4 GiB ocupados. CUDA visible desde Windows
y FedoraLinux-43 WSL2. WSL tiene límite existente ~7,8 GiB; no se modifica.
Sin procesos de experimentos ML detectados en Windows/WSL ni otro hilo activo
del proyecto. Hay servicios personales y aplicaciones de escritorio: preservarlos.

Límites fijados antes de scores: un experimento y un hilo por biblioteca; RSS del
árbol de procesos <=2 GiB, memoria disponible del host >=4 GiB, evidencia <=2 GiB,
disco libre >=10 GiB; VRAM del experimento <=4 GiB y libre >=6 GiB. CPU acumulada
14 h (screening 3, nested 8, secundarios 2, benchmark 1). GPU acumulada 2 h,
piloto <=10 min; contabilización conservadora por duración de proceso GPU.
El piloto puede desaconsejar GPU; no cambia silenciosamente el backend del pool.

Próximo paso: resolver entorno research aislado en D:, implementar protocolo,
smoke sintético, sellar folds/configuración antes de scores y ejecutar piloto.
No hay entrenamiento nuevo ejecutado todavía. Validación reutilizada y test
excluido no se puntúan en este estudio. Históricos no son ejecuciones actuales.
