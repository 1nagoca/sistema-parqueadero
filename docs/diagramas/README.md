# Diagramas

Diagramas del sistema, dibujados a partir del código real. Cada archivo trae el diagrama y un
párrafo para explicarlo.

| Diagrama | Qué muestra |
|---|---|
| [Arquitectura de microservicios](01-arquitectura.md) | Navegador, gateway, los cuatro servicios, sus bases y qué ruta va a cada uno |
| [Despliegue](02-despliegue.md) | Contenedores de `docker-compose`, imágenes, puertos y volúmenes |
| [Mapa de contextos](03-mapa-de-contextos.md) | Los cuatro contextos (DDD) y el tipo de relación entre ellos |
| [Capas por servicio](04-capas-por-servicio.md) | Organización interna de cada microservicio |

El modelo de datos está en [`base-de-datos/diagrama-er.md`](../../base-de-datos/diagrama-er.md).

## Cómo verlos

Están escritos en Mermaid dentro de Markdown. GitHub los dibuja al abrir el archivo. En VS Code,
abrir la vista previa (`Ctrl+Shift+V`); si se ve el texto en vez del dibujo, instalar la extensión
«Markdown Preview Mermaid Support».
