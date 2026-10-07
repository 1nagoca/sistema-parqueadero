# Diagramas

Diagramas del sistema, dibujados a partir del código real. Cada archivo trae el diagrama y un
párrafo para explicarlo. El modelo de datos está en [`diagrama-er.md`](../../base-de-datos/diagrama-er.md).

| Diagrama | Qué muestra |
|---|---|
| [Arquitectura de microservicios](01-arquitectura.md) | Navegador, gateway, los cuatro servicios, sus bases y qué ruta va a cada uno |
| [Despliegue](02-despliegue.md) | Contenedores de `docker-compose`, imágenes, puertos y volúmenes |
| [Mapa de contextos](03-mapa-de-contextos.md) | Los cuatro contextos (DDD) y el tipo de relación entre ellos |
| [Capas por servicio](04-capas-por-servicio.md) | Organización interna de cada microservicio |
| [Proceso: registro y verificación](05-registro-y-verificacion.md) | BPM por roles: registro, carnet, vehículo, aprobación o rechazo y reenvío |
| [Proceso: entrada y salida](06-entrada-y-salida.md) | BPM por roles: búsqueda de placa, entrada, salida y rechazos |
| [Proceso: acceso de visitante](07-acceso-de-visitante.md) | BPM por roles: autorización con justificación (RN-03) |
| [Proceso: cupos y auditoría](08-cupos-y-auditoria.md) | BPM por roles: mapa en tiempo real y consulta de auditoría |

Los procesos (05 a 08) usan un carril por rol y traen una tabla de actividades para redibujarlos
en notación BPMN. Están en Mermaid: GitHub los dibuja al abrir el archivo; en VS Code, vista previa
(`Ctrl+Shift+V`) con la extensión «Markdown Preview Mermaid Support».
