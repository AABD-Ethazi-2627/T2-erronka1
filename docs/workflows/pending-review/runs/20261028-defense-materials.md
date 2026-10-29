# Explicaciones y ensayo preparados · 28/10/2026

Solicitud: redactar las explicaciones y todo el material preparable con las
fuentes existentes para #37/#26/#27/#82/#83. Base integrada: `b2186e519e5444dcdb127d9409da105a8fe6d674`.

Dos agentes GPT-6.1-Sol/Codex, reasoning high, trabajaron en worktrees T3
separados. El padre integró sus commits locales, revisó el contenido y conectó
las cuatro piezas desde `docs/demo/README.md` y el handoff:

- `AZALPENAK_20261028.md`: explicación completa en castellano, cuatro bloques,
  ejemplos, relevos, preguntas y soluciones.
- `DEFENTSA_GIDOIA_20261023.md`: guion en euskera actualizado a la campaña del
  28/10; el piloto del 23/10 permanece identificado como histórico.
- `ENTSEGU_PRESTATUA_20261028.md`: exposición, archivos/campos que mostrar,
  casos, respuestas y hoja de notas vacía para el ensayo.
- `CONSULTA_DOCENTE_PREPARADA_20261028.md`: mensaje bilingüe listo para copiar,
  preguntas abiertas, inventario de archivos y checklist de entrega.

La revisión del padre corrigió la afirmación antigua de que los diez minutos
eran solo una propuesta: `ENUNTZIATUA.md:372-374` sí contempla demo live de
diez minutos. El ensayo offline se identifica como preparación/respaldo.
También se desarrollaron Pydantic y la diferencia entre scheduler autónomo y
lazo de control automático de la CNC.

Validación ejecutada: 186 enlaces locales con sus anclas, tres destinos GitHub
fijados a objetos Git existentes, 28 comprobaciones de percentiles en las dos
tablas contra siete recibos, suma de 1.860 eventos, fórmulas de coste y unidades.
El primer intento del validador propio exigía el nombre raw completo en la
tabla euskera, que usa etiquetas cortas; se corrigió el validador para localizar
la fila por su etiqueta y comprobar sus propios valores. No fue un fallo del
documento. La ejecución final pasa.

CG25: 40 criterios, 90 enlaces, 264 hashes vivos y 18 históricos; CG02, layout
y diff-check pasan. El snapshot histórico permanece idéntico. Evidencia del
padre en `D:/reviews/pr91-sampler-fix-20261028/defense-validation.json` y script
`validate_defense.py`. Los agentes además contrastaron CRC/238 hashes raw,
identidades, fuentes y capturas; esos resultados son suyos, no nuevas campañas
del padre. No se ejecutaron pruebas de producto para este cambio documental.

No se envió la consulta docente ni se cumplimentaron intervenciones, actas,
respuestas, firmas o recibos. La revisión de redacción/euskera por el equipo y
los actos reales permanecen separados del contenido que ya puede estudiar.
