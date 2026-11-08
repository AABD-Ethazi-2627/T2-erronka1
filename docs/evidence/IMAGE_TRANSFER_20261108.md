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
