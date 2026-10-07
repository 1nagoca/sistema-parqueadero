# Capas por servicio

Las capas **no son la arquitectura del sistema**: la arquitectura global son los microservicios
del [diagrama de arquitectura](01-arquitectura.md). Las capas son la forma en que se ordena el
código **dentro** de cada microservicio: los `routers` reciben la petición y revisan permisos, los
`services` aplican las reglas de negocio y los `models` son las tablas de la base propia; los
`schemas` definen qué entra y qué sale. Cada servicio repite esta organización por separado, con
su propio código y su propia base.

```mermaid
flowchart TB
    cli["Gateway u otro servicio"]

    subgraph ms["Un microservicio (app/)"]
        direction TB
        rou["<b>routers</b> · api/v1/routers<br/>HTTP, permisos por rol, códigos de respuesta"]
        sch["<b>schemas</b><br/>forma de entrada y salida (Pydantic)"]
        ser["<b>services</b><br/>reglas de negocio"]
        mod["<b>models</b><br/>tablas (SQLAlchemy)"]
        ext["<b>adaptadores</b><br/>accesos: identidad_client, parqueadero_client<br/>parqueadero: ws"]
    end

    bd[("Base de datos propia")]
    otros["Otros microservicios · /interno<br/>Navegadores · WebSocket"]

    cli --> rou
    rou --> ser
    rou -.->|"valida y responde con"| sch
    rou -.->|"consultas simples"| mod
    ser --> mod
    ser --> ext
    mod --> bd
    ext --> otros
```

| Servicio | ¿Sigue las capas? | Particularidades |
|---|---|---|
| `backend-identidad` | Sí | `services` de verificación, vehículos, documentos y auditoría. |
| `backend-accesos` | Sí | Añade `identidad_client` y `parqueadero_client` para llamar a los otros servicios. |
| `backend-parqueadero` | Sí | Añade `ws` para avisar los cupos por WebSocket. |
| `backend-vision` | No | Es `routers → pipeline` (preprocesar, OCR, posprocesar); no tiene base, `models` ni `services`. |

Las líneas punteadas son atajos que existen en el código: los routers validan y responden con
`schemas`, y hacen directamente las consultas simples (listar, buscar por id) sobre `models`; las
operaciones con reglas de negocio pasan por `services`. El router de accesos también usa
`parqueadero_client` para mostrar el código de cada espacio.

Verificado contra: `app/api/v1/routers/`, `app/services/`, `app/models/` y `app/schemas/` de cada
backend, y `backend-vision/app/{api/routers,pipeline}/`.
