# CNC Guard: prototipo visual del panel propio

Prototipo desechable v0.1 para discutir el diseño con Angie y el equipo. HTML, CSS y JavaScript sin dependencias ni conexión a servicios reales. Todos los datos son sintéticos. No controla equipos ni configura Kibana.

## Abrir

Abrir `index.html` directamente en el navegador, o desde esta carpeta:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Visitar http://127.0.0.1:8765. Detener con Ctrl+C.

## Interacciones

- Navegación entre vista general, máquinas, calidad, modelo, infraestructura y Kibana.
- Filtros de máquina y ventana temporal sobre la telemetría de demo.
- Búsqueda de máquinas y detalle mediante clic en el identificador.
- Estado sin datos para CNC-04, que no equivale a una máquina detenida.
- Actualización del fixture y propuesta de integración de Kibana.

Calidad, evaluación, infraestructura y mapa de calor son escenarios independientes; no se filtran con la telemetría. La ventana cambia la serie sintética, no la última lectura. El score es ilustrativo y no se presenta como probabilidad calibrada ni previsión temporal.

## Decisiones abiertas

Idioma final, identidad visual, jerarquía de avisos, métricas adicionales y sus fuentes, permisos de consulta, contrato API y forma de acceso a Kibana (enlace o iframe condicionado a autenticación y política de frames). Los estados y umbrales de esta demo no son requisitos aprobados ni controles operativos.
