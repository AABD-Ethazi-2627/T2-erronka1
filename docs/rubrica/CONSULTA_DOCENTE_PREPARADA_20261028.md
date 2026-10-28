# Consulta docente preparada · 28/10/2026

Preparación no equivale a consulta enviada, respuesta recibida ni entrega: este documento deja el mensaje y el paquete listos para que las personas responsables los contrasten y utilicen.

Referencia de trabajo: merge PR91 en `main`, `b2186e519e5444dcdb127d9409da105a8fe6d674`. Se conserva como registro de decisiones [ACLARACIONES_20261023.md](ACLARACIONES_20261023.md); esta hoja no lo sustituye ni modifica sus respuestas parciales. Según ese registro, petiteiker canaliza la consulta y Angiecrizu registra respuesta, fecha y fuente. Los objetivos del [handoff del 28/10](../demo/PENDING_HANDOFF_20261028.md) son reconciliar el 04/11, ensayar el 05/11 y entregar el 06/11; no confirman canal, hora ni duración final.

## Mensaje en euskera, listo para copiar

**Gaia: CNC Guard · errubrikako eta azken entregako argibide zehatzak (A01–A05/A07)**

Kaixo, Aitor:

CNC Guard-en dokumentazioa eta aurkezpena prestatzen ari gara. Datuen ikuspegi tabularra eta emandako kostuen matrizea jaso ditugu. Irekita dauden puntu hauek argitu nahi ditugu:

1. **A01 · Errubrikaren bertsioa.** Indarrean al dago gure kopia, Excelaren SHA-256 `e3e05d6fe408e163f6f8247cd7054f2a4ce4de6aa5757048ba432cd682139463` duena (Zereginak, G zutabeko 40 deskribatzaile)? Beste bertsiorik badago, zein erabili behar dugu?
2. **A02 · Pisuak eta ebaluazioa.** Nola interpretatu behar ditugu H5 gelaxkako `15%%`, IASeko pisu ikusgarririk eza eta banakako/zeharkako ebaluazioa? Moduluen pisuak ez batzea proposatzen dugu, interpretazioa argitu arte.
3. **A03 · G49/G92.** Nola baloratuko dira akademikoki PMk onartutako SMB baliokidetasuna eta NiFi/worker banaketa? Frogatutako ibilbidea eta haren mugak aurkeztea proposatzen dugu; ez dugu NFS edo InvokeHTTP natiboaren exekuziorik aldarrikatuko.
4. **A04 · G62 eta sarrerak.** Sailkapen tabularra argituta dagoenez, nola baloratuko da «makina bakoitzeko historikoa»? Bost sentsoreen adibideak `machine_type` baztertzen du, ala onartzen dira oraingo bost sentsoreak eta makina mota? Egungo sailkapena mantentzea proposatzen dugu, timestamp sarreretan sartu gabe eta historia fisikorik asmatu gabe.
5. **A05 · G45/G61.** Nola baloratuko dira recallaren erreferentzia eta PMk onartutako 0,15/0,70 politikak? Balidazio berrerabiliaren mugak eta emandako kostuekin FN/FP konpromisoa azaltzea proposatzen dugu, egungo atalaseak aldatu gabe.
6. **A07 · Entrega eta defentsa.** Zein dokumentu eta formatu behar dira? Zein kanaletan, zein egun eta ordutarako, eta zer ordu-zonatan? Zein da defentsaren iraupena, eta galderak denbora horren barruan daude? Enuntziatuko 10 minutuko demo bizia nola aurkeztu behar dugu, eta onartzen al da artxibatutako ebidentzia offline erabiltzea ingurunea erabilgarri ez badago? Gure plangintzako datak 04/11ko bateratzea, 05/11ko entsegua eta 06/11ko entrega dira; azken baldintzak baieztatu nahi ditugu.

Erreferentziak: [argibideen erregistroa](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/b2186e519e5444dcdb127d9409da105a8fe6d674/docs/rubrica/ACLARACIONES_20261023.md), [egungo matrizea](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/b2186e519e5444dcdb127d9409da105a8fe6d674/docs/rubrica/ESTADO_20261028.md) eta [28/10eko CG32 kanpaina](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/b2186e519e5444dcdb127d9409da105a8fe6d674/docs/evidence/CG32_CAMPAIGN_20261028.md). Dokumentazioa, ANEXO1/4, ahozko gidoia eta esportazio identifikatuak prestatuta ditugu berrikusteko; azken paketea erantzunaren arabera finkatuko dugu.

ID bakoitzaren ondoan erantzun laburra edo erabili beharreko iturria adieraz dezakezu. Eskerrik asko.

## Versión castellana de apoyo

**Asunto: CNC Guard · aclaraciones concretas de rúbrica y entrega final (A01–A05/A07)**

Hola, Aitor:

Estamos preparando la documentación y la presentación de CNC Guard. Ya hemos incorporado el alcance tabular y la matriz de costes facilitada. Queremos aclarar estos puntos abiertos:

1. **A01:** ¿Sigue vigente nuestra copia del Excel, SHA-256 `e3e05d6fe408e163f6f8247cd7054f2a4ce4de6aa5757048ba432cd682139463`, con 40 descriptores G de Zereginak? Si hay otra versión, ¿cuál debemos usar?
2. **A02:** ¿Cómo interpretar H5 `15%%`, IAS sin pesos visibles y la evaluación individual/transversal? Proponemos no sumar pesos de módulos mientras se aclara.
3. **A03:** ¿Cómo se valoran académicamente la equivalencia SMB y el reparto NiFi/worker aceptados por PM? Proponemos presentar el recorrido probado y sus límites, sin atribuir ejecución nativa de NFS/InvokeHTTP.
4. **A04:** Con la clasificación tabular ya aclarada, ¿cómo se valora «histórico por máquina» de G62? ¿El ejemplo de cinco sensores excluye `machine_type` o admite las seis entradas actuales? Proponemos conservar la clasificación vigente, sin timestamp en X ni historia física inventada.
5. **A05:** ¿Cómo se valoran la referencia de recall y las políticas 0,15/0,70 aceptadas por PM? Proponemos explicar los límites de validación reutilizada y el compromiso FN/FP con los costes facilitados, sin cambiar los umbrales actuales.
6. **A07:** ¿Qué documentos/formato, canal, fecha/hora/zona y duración de defensa se exigen? ¿Las preguntas entran en ese tiempo? ¿Cómo presentar la demo viva de diez minutos del enunciado y se admite respaldo offline archivado si el entorno no está disponible? Planificamos reconciliación 04/11, ensayo 05/11 y entrega 06/11, pendientes de las condiciones finales.

Adjuntamos como referencias el registro de aclaraciones, la matriz vigente y CG32 del 28/10 enlazados arriba. Tenemos documentación, ANEXO1/4, guion oral y exports identificados para revisión; fijaremos el paquete final según la respuesta. Basta una respuesta breve por ID o la fuente que debemos seguir. Gracias.

## Referencias para resolver cada respuesta

Enviar una sola versión lingüística. Los enlaces del mensaje están fijados al merge para que una edición posterior no cambie la consulta. Si el canal no permite enlaces, adjuntar copias de esos archivos identificando SHA y fecha, sin inventar una URL de Moodle.

| ID abierto | Fuente exacta y propuesta que se sostiene |
| --- | --- |
| A01 | [fuente.json](fuente.json): hash/celdas de la copia local; conservarla hasta identificar una versión sustituta. |
| A02 | [OBJETIVOS_Y_ETAPAS.md](OBJETIVOS_Y_ETAPAS.md): ejes de evaluación y anomalías literales; no inferir porcentajes ni una nota. |
| A03 | [registro de aclaraciones](ACLARACIONES_20261023.md), enlaces P36/P14, y [CG20 mismo evento](../evidence/CG20_SAME_EVENT_20261022.md): preservar aceptación PM y preguntar solo su valoración académica. |
| A04 | [alcance docente aportado](../evidence/DOCENTE_FORO_20261023.md), [CG06](../evidence/CG06.md), [CG07](../evidence/CG07.md): snapshots y desgaste como covariable; cinco sensores + tipo actuales, sin historia causal ni forecast. |
| A05 | [CG10 conciliado](../evidence/CG10_PRECISION_20261022.md), [business-summary.json](../evidence/CG34_20261023/business-summary.json) y [curvas de coste](../evidence/CG34_20261023/business-cost-curves.png): recall literal ≥76%, desarrollo reutilizado y niveles 0,15/0,70. No promover un umbral teórico ni reabrir el test excluido. |
| A07 | [enunciado](../../ENUNTZIATUA.md), [procedencia de la guía oral](../evidence/DOCENTE_FORO_20261023.md), [handoff actual](../demo/PENDING_HANDOFF_20261028.md) y [ensayo preparado](../demo/ENTSEGU_PRESTATUA_20261028.md): referencia de diez minutos, preparación offline y condiciones finales aún por confirmar. |

**A06 está resuelta y no es una pregunta del mensaje.** Se usan FN 5.000 €, FP 200 €, TP 300 €, TN 0 €, facilitados en el post atribuido del 22/10, con procedencia y límites en DOCENTE_FORO. Los posts proceden de transcripciones aportadas por el usuario, no de una nueva verificación de Moodle. Esa atribución no impide usar sus parámetros para el ejercicio; tampoco acredita ahorro industrial.

## Formulario corto de respuesta y efecto

Rellenar después de obtener una respuesta atribuible. Si no se responde a un punto, conservar PENDIENTE en el registro original. Una respuesta parcial no resuelve toda la fila.

| ID | Respuesta literal breve o resumen fiel | Persona/función · fecha/hora/zona · enlace o copia | Efecto concreto sobre matriz/paquete y responsable |
| --- | --- | --- | --- |
| A01 | | | |
| A02 | | | |
| A03 | | | |
| A04 | | | |
| A05 | | | |
| A07 | | | |

Comprobar el efecto antes de cambiar artefactos: A01 puede exigir comparar versiones; A02 afecta interpretación de evaluación; A03, las equivalencias documentadas; A04, redacción y alcance de entradas; A05, justificación académica de resultados/políticas; A07, selección, formato y logística del paquete. Una respuesta que pida cambiar modelo, contratos o infraestructura requiere concretar ese trabajo y su validación por separado; no modifica automáticamente lo servido.

## Inventario existente para revisión y congelación

Las filas siguientes son una propuesta de selección de archivos ya existentes, no un paquete final generado ni una lista de adjuntos obligatorios confirmada por el docente. Abrir las versiones del SHA que realmente se congele. La documentación histórica conserva sus cortes; la matriz y campaña del 28/10 dan el estado actual.

| Parte | Artefactos exactos del repositorio |
| --- | --- |
| Requisitos y rúbrica | [ENUNTZIATUA.md](../../ENUNTZIATUA.md), [fuente.json](fuente.json), [ESTADO_20261028.md](ESTADO_20261028.md), [ACLARACIONES_20261023.md](ACLARACIONES_20261023.md) y esta consulta preparada. |
| Memoria y anexos | [docs/memoria/README.md](../memoria/README.md), [ANEXO4_CNC_Guard.md](../memoria/ANEXO4_CNC_Guard.md), [ANEXO1_CNC_Guard.md](../requisitos/ANEXO1_CNC_Guard.md), [manifest.json de memoria](../memoria/manifest.json). No completar acuerdos o firmas por otras personas. |
| Defensa y ensayo | [DEFENTSA_GIDOIA_20261023.md](../demo/DEFENTSA_GIDOIA_20261023.md), [README técnico de demo](../demo/README.md), [ENTSEGU_PRESTATUA_20261028.md](../demo/ENTSEGU_PRESTATUA_20261028.md), [ACTA_PENDIENTE_20261022.md](../demo/ACTA_PENDIENTE_20261022.md) y [PENDING_HANDOFF_20261028.md](../demo/PENDING_HANDOFF_20261028.md). El acta sigue siendo plantilla hasta la sesión. |
| Export de la misma cadena CG20 | [kibana-final-runtime-export.ndjson](../evidence/CG20_SAME_EVENT_20261022/kibana-final-runtime-export.ndjson), [runtime-export.json de NiFi](../evidence/CG20_SAME_EVENT_20261022/lab-01/runtime-export.json), [graph.json](../evidence/CG20_SAME_EVENT_20261022/lab-01/graph.json) y [same-event.json](../evidence/CG20_SAME_EVENT_20261022/same-event.json). Son exports históricos con rutas propias, no configuración actual de servicios compartidos. |
| Respaldo offline del panel | [dashboard-verified.png](../evidence/CG20_SAME_EVENT_20261022/dashboard-verified.png), [Discover del mismo evento](../evidence/CG20_SAME_EVENT_20261022/discover-same-event.png), [discover.png CG32](../evidence/CG32_CAMPAIGN_20261028/discover.png) y [discover-receipt.json CG32](../evidence/CG32_CAMPAIGN_20261028/discover-receipt.json). Etiquetar fecha/identidad en cada vista. |
| Campaña actual y crudos | [CG32_CAMPAIGN_20261028.md](../evidence/CG32_CAMPAIGN_20261028.md), [identidad reconstruida](../evidence/CG32_REBUILT_IDENTITY_20261028.json), [summary-10.json](../evidence/CG32_CAMPAIGN_20261028/summary-10.json), [raw-runs.zip](../evidence/CG32_CAMPAIGN_20261028/raw-runs.zip), [raw-index.json](../evidence/CG32_CAMPAIGN_20261028/raw-index.json) y [archive.json](../evidence/CG32_CAMPAIGN_20261028/archive.json). Seleccionar adjuntos según límites del canal; conservar crudos íntegros. |
| ML y economía | [CG34_EXPLORACION_20261023.md](../evidence/CG34_EXPLORACION_20261023.md), [packages.json](../evidence/CG34_20261023/packages.json), [business-costs.json](../evidence/CG34_20261023/business-costs.json), [business-summary.json](../evidence/CG34_20261023/business-summary.json) y [business-cost-curves.png](../evidence/CG34_20261023/business-cost-curves.png). Investigación archivada y parámetros del ejercicio, sin promoción. |

No se ha creado un PPTX, PDF final ni ZIP final de entrega en esta preparación. Si A07 exige una conversión o presentación, producirla y revisarla antes de añadir su ruta y hash al inventario definitivo. Los ZIP de evidencia de la tabla ya existen y tienen otra finalidad.

## Checklist de canal, formato, hora, paquete y recibo

### Antes de la consulta y de fijar la entrega

- [ ] La persona portavoz revisa una sola versión del mensaje; los IDs son A01–A05/A07 y no se vuelve a preguntar A06.
- [ ] Se acuerda el canal real de consulta y quién conserva la respuesta; no hay envío automático desde esta preparación.
- [ ] Se registra el canal exacto de entrega indicado por el docente: curso/actividad/URL o destino concreto, responsable y permiso de acceso.
- [ ] Se registran formato(s), documentos requeridos, convención de nombres, tamaño máximo, modalidad individual/grupal y posibilidad de sustitución.
- [ ] Se anotan fecha, hora y zona de cierre; duración de exposición, tiempo de preguntas y condiciones de demo viva/respaldo. Contrastar con 04/11, 05/11 y 06/11 sin tratarlos como confirmación.

### Congelación del paquete tras concretar A07

- [ ] Se fija SHA/árbol de la versión integrada que se entregará. Referencia actual: merge PR91 `b2186e519e5444dcdb127d9409da105a8fe6d674`; las nuevas revisiones documentales se identifican con su propio SHA.
- [ ] Se conserva el alcance de CI: los **20 checks del head `36797200d9517a3005f32faf1d2adebf9da707f1`** proceden del estado comunicado por el padre, sin consulta remota nueva en esta preparación. No llamarlos CI nueva del merge ni de estos documentos. [CI_REFRESH_20261028.md](../evidence/CI_REFRESH_20261028.md) documenta reparaciones y validación local separadas.
- [ ] Se identifican CG26 histórico (manifiesto `a6cc7a29…`, RF `803ee2e1…`, IF `a12304b4…`), rebuilt del 28/10 (`b85be76e…`, `67c98ff5…`, `4354475c…`) y RF research (`34a14ab9…`). Los hashes completos están en [CG26](../evidence/CG26_REHEARSAL_2026-10-21.json), [rebuilt](../evidence/CG32_REBUILT_IDENTITY_20261028.json) y [packages](../evidence/CG34_20261023/packages.json); no intercambiar identidades por compartir `model_version`.
- [ ] Se seleccionan las rutas exactas de la tabla, se revisa coherencia en euskera/castellano y se comprueban enlaces y hashes de los bytes seleccionados. El inventario final contendrá ruta, tamaño, SHA-256, identidad/fecha y razón de inclusión; todavía no se declara generado.
- [ ] Se contrasta la memoria histórica con matriz/handoff/campaña actuales, sin reescribir recibos históricos para ocultar diferencias. Se comprueba CG25 con el verificador existente [scripts/check_cg25_memory.py](../../scripts/check_cg25_memory.py) sobre el árbol final y se conserva su salida real. Esta casilla no acredita una ejecución en esta preparación.
- [ ] Se revisan las capturas offline en el dispositivo de exposición; se distingue CG20 sintético del candidato CG32 y se conserva el fallo de la meta E2E. No presentar históricos de CG23 o pilotos del 23/10 como capacidad actual.
- [ ] Se acuerda si anexar crudos o referenciarlos según el canal, manteniendo acceso a las evidencias que sustentan las afirmaciones. No incluir secretos, `.env`, credenciales, ledgers privados ni modelos por arrastre de una carpeta de trabajo.
- [ ] Se registra ensayo/explicación reales en el acta existente cuando ocurran; las casillas y plantillas vacías no cuentan como aceptación ni asistencia.

### En el acto de entrega y después

- [ ] La persona responsable comprueba los archivos seleccionados y el canal antes de enviar; este documento no ejecuta el envío.
- [ ] Tras la entrega efectiva se conserva recibo con fecha/hora/zona, actividad/destino, remitente real y nombres/tamaños de los archivos entregados o identificador de versión.
- [ ] Se comprueba que el recibo corresponde al paquete congelado; si el canal transforma los bytes, registrar original y copia recibida por separado, sin atribuirles el mismo hash.
- [ ] Se registra el enlace/copia del justificante y cualquier reenvío o corrección en el registro existente. Sin recibo o respuesta comprobable, conservar ese estado pendiente.

Campos auxiliares vacíos para preparar la logística; la respuesta y la entrega realizadas se registran en sus fuentes existentes:

```text
Canal de consulta / portavoz / registro:
Respuesta A07 que fija condiciones (referencia):
Canal y actividad de entrega / responsable:
Formatos / nombres / tamaño máximo / modalidad:
Fecha-hora-zona de cierre / duración y preguntas:
SHA-árbol congelado / inventario de hashes:
Archivos seleccionados y conversiones revisadas si se exigieron:
Referencia al acta real de ensayo:
Referencia al recibo real de entrega:
```
