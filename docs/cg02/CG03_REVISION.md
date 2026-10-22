# CG03 revisión offline

Contratos reutilizados sin cambios desde PR30 (9066c71). El validador local
scripts/validate_contracts.py resuelve referencias sin red y comprueba UTC real.
Comando: `uv run --with jsonschema python -m unittest discover -s tests -q`.
17 pruebas superadas, incluidos ejemplos positivos y negativos de los cuatro contratos.
No verifica API, NiFi, SMB actual ni carga del modelo. La propuesta continúa pendiente
de revisión del equipo. El README original cita inferencia del PR30 que todavía no
forma parte de esta rama: aquí se ha aislado exclusivamente la validación de esquemas.
