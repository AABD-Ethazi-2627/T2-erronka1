# Kibana y Elasticsearch corregidos: smoke conectado

El 8 de noviembre de 2026 el coordinador ejecutó el servicio Kibana real contra
Elasticsearch real, con seguridad activa, en una red Docker interna propia y
sin puertos publicados. El [resultado compacto](KIBANA_ES_CONNECTED_20261108.json)
fija ambas imágenes, el daemon, las respuestas y los hashes de la evidencia.

Resultado: Elasticsearch verde y rechazo anónimo 401; Kibana `/api/status`
autenticado alcanza `available` con todos los servicios y plugins disponibles;
Fleet `/api/fleet/agent_policies?perPage=10` devuelve 200 y una lista vacía real;
la misma ruta sin credenciales devuelve 401. No es una simulación HTTP ni una
CLI `--version`. Una lista vacía no prueba creación de políticas, enrolamiento
de agentes, descarga del registro ni todas las ramas de matching de Fleet.
Los controles de sus consumidores afectados permanecen en el build de Kibana.

Se utilizó un usuario file-realm sintético efímero y un token de servicio propio
de Kibana. El token no se publica; el harness lo redacta antes de conservar logs.
Fleet usa el modo air-gapped documentado por
[Elastic](https://www.elastic.co/docs/reference/kibana/configuration-reference/fleet-settings),
apropiado para la red interna sin salida. No se desactiva la autenticación.
Todos los contenedores y la red propios se retiran; `cleanup_errors=[]`.

## Arranque en frío: defecto descubierto y corregido

El primer intento conservado (`smoke-01`) pasó los endpoints pero emitió dos
`index_not_found_exception` desde Workflows. No se lo acredita como arranque
sin errores. La [fuente oficial v9.5.5](https://github.com/elastic/kibana/blob/v9.5.5/src/platform/plugins/shared/workflows_execution_engine/server/lib/data_streams/roll_data_stream_if_required.ts)
prevé omitir el rollover de streams ausentes, pero usa solo `allow_no_indices`,
que no hace opcional un nombre explícito ausente. Se añade
`ignore_unavailable: true` a esa consulta, con preimage SHA256 fijado.
No se cambia ni suprime ningún logger ni se capturan errores de permisos.

El test sobre la función real del paquete original falla con
`index_not_found_exception`; sobre la imagen corregida pasa. Comprueba ausencia,
versiones de mapping iguales, mayores y menores, rollover real solicitado al
cliente en el caso antiguo y propagación exacta de errores de permisos/conexión.
La segunda ejecución conectada confirma además contra ES real: nombre ausente
con solo `allow_no_indices` devuelve 404; añadiendo `ignore_unavailable` devuelve
200 y `{}`. Kibana alcanza `available` y ambos servicios tienen **cero registros
ERROR** durante el ensayo. Esta es la imagen `cnc-closeout-kibana:connected`,
ID `sha256:2d52fc60f9ae3c12453004544bbe77b95472aa0e48bfab9ad546845aa958365c`.
El build vuelve a ejecutar todos los controles de componentes. Su nuevo escaneo
Trivy 0.76.1 completo termina con gate `[]`, atribuido al ID anterior; SHA256
del JSON crudo `01a138b97c86914368f016053b65ef055c3d7a03a6fd372c0a6da20e1d995682`.
Conserva únicamente las dos tuplas verificadas de extract-zip ya existentes;
no se añade ninguna excepción ni se afirma cero diagnósticos brutos.

Repetición sobre las imágenes ya construidas:

```powershell
uv run --frozen --group dev --extra kafka python scripts/check_kibana_image.py cnc-closeout-es:final cnc-closeout-kibana:connected outputs/closeout-kibana-es-smoke-NUEVO
```

El directorio de salida debe ser nuevo. Ambos intentos y sus logs se preservan
en `outputs/closeout-kibana-es-smoke-01/` y `smoke-02/`. El primer script ejecutado
se conserva como `check_kibana_image.executed.py`; su Ruff format conservó el
AST. El segundo incluye la comprobación real de ausencia y rechazo de logs
ERROR; su hash se captura antes de ejecutar. La base de producto es `0942dc2`;
el harness y la corrección cold-start se añadieron después, como declara el JSON.
Ruff check, Ruff format y diff-check pasan para el harness incorporado.

Esta prueba no establece NiFi/Kafka/Filebeat, UI Laneki en navegador, SMB real,
aceptación industrial del modelo, CI, revisión GitHub, merge ni producción.
