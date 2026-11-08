# Transferencia de imágenes al motor Linux

Se conservó el archivo Docker de 5.510.876.160 bytes bajo D:, con SHA256
`a99933c59371e5a3e8993332c633fa95476f7afbbae890b623bf4173b7e14770`.
La carga en el daemon Fedora/Kalista terminó. No se borraron recursos previos.

La primera comprobación detectó IDs diferentes en las cinco imágenes y suspendió
su atribución hasta contrastarlas. La diferencia es de representación:
Docker Desktop informa el digest de configuración; el motor de destino informa
el del manifiesto OCI, coincidente con su `Descriptor.digest`.

El [registro](IMAGE_TRANSFER_20261108.json) conserva ambos identificadores.
Para cada imagen se verificó que el índice del TAR contiene el manifiesto de
destino; el SHA256 de ese blob coincide con su digest; su `config.digest` apunta
al ID de origen; el SHA256 del blob de configuración coincide con ese ID.
Además coinciden `Created`, arquitectura, OS, configuración de ejecución y la
lista completa y ordenada de `RootFS.Layers` entre ambos daemons. No se deduce
equivalencia solo del nombre del tag ni se omite la comprobación del digest.

Esto atribuye los bytes escaneados de API, dashboard, Kafka, Elasticsearch y
Kibana a las imágenes cargadas. No es una nueva ejecución funcional, aceptación
del otro host ni prueba de NiFi/Filebeat, que no estaban en este archivo.
El JSON crudo de ambas inspecciones sigue en
`outputs/image-transfer-inspection.json`; TAR e imágenes se conservan.

## Filebeat final

Transferencia adicional mediante `filebeat-final.tar`: 532.616.192 bytes,
SHA256 `ed1ab300df887006043d5bc93aee2ea23f64bf35bf9bb34e7fd3210d0cf2cee1`.
Se repitieron todas las comprobaciones índice/manifiesto/config y comparación
de campos y capas. Config de origen `aabe875e...`; manifiesto OCI de destino
`aea160cd...`. El JSON contiene los digests completos y el inventario del
archivo adicional. Crudo: `outputs/filebeat-transfer-inspection.json`.
Esta imagen corresponde al binario con compress 1.20.2 ya escaneado y revisado;
su E2E sigue pendiente.

## NiFi completo

`nifi-final.tar`, SHA256
`4330e93d4175fb2eaae2f6c46b9a9be358e467ddc038d9b9a62b3ac431079b1a`,
ya está cargado y comprobado con el mismo procedimiento: config `ce5cc168...`,
manifiesto destino `0a759f2e...`, campos y 20 capas idénticos. Digests completos
y tamaño en JSON; crudo `outputs/nifi-transfer-inspection.json`. Se conservan
el TAR y los recursos fuente. El E2E usa esta imagen completa, sin excluir NAR.
