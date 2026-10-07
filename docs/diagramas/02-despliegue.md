# Despliegue

Todo corre con `docker compose`: nueve contenedores en una misma red interna. Solo el `frontend`
(5173) y el `gateway` (8000) publican puerto de aplicación; los cuatro backends no publican
ninguno y solo se alcanzan por el gateway o entre ellos. Cada servicio con datos tiene su propio
contenedor de PostgreSQL 16 (`postgres:16-alpine`) y su propio volumen, de modo que si una base se
cae las otras siguen arriba. Los documentos de verificación viven en un volumen aparte
(`identidad_uploads`), nunca como archivos estáticos.

```mermaid
flowchart TB
    host["Equipo anfitrión · navegador"]

    subgraph red["Red interna de docker-compose"]
        direction TB

        subgraph pub["Publican puerto de aplicación"]
            frontend["frontend<br/>build ./frontend · node:20-slim<br/>5173:5173"]
            gateway["gateway<br/>nginx:1.27-alpine<br/>8000:8000"]
        end

        subgraph internos["Solo red interna (sin puerto publicado)"]
            identidad["backend-identidad<br/>build ./backend-identidad · python:3.12-slim<br/>:8003"]
            accesos["backend-accesos<br/>build ./backend-accesos · python:3.12-slim<br/>:8000"]
            parqueadero["backend-parqueadero<br/>build ./backend-parqueadero · python:3.12-slim<br/>:8002"]
            vision["backend-vision<br/>build ./backend-vision · python:3.11-slim<br/>:8001"]
        end

        subgraph bases["Bases de datos · publican puerto al anfitrión"]
            db_identidad[("db-identidad<br/>postgres:16-alpine<br/>5435:5432")]
            db[("db<br/>postgres:16-alpine<br/>5432:5432")]
            db_parqueadero[("db-parqueadero<br/>postgres:16-alpine<br/>5434:5432")]
        end
    end

    subgraph vols["Volúmenes con nombre"]
        v_ide[/"db_identidad_data"/]
        v_upl[/"identidad_uploads"/]
        v_db[/"db_data"/]
        v_par[/"db_parqueadero_data"/]
    end

    host -->|":5173"| frontend
    host -->|":8000"| gateway

    gateway --> identidad
    gateway --> accesos
    gateway --> parqueadero
    gateway --> vision

    accesos -->|"/interno"| identidad
    accesos -->|"/interno"| parqueadero

    identidad --> db_identidad
    accesos --> db
    parqueadero --> db_parqueadero

    db_identidad --- v_ide
    identidad ---|"/code/uploads"| v_upl
    db --- v_db
    db_parqueadero --- v_par
```

- Los puertos se leen `anfitrión:contenedor` y son los valores por defecto del compose; se cambian
  en `.env` (`GATEWAY_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`, `PARQUEADERO_DB_PORT`,
  `IDENTIDAD_DB_PORT`).
- Las bases publican puerto al anfitrión para desarrollo; cerrarlos es parte del paso 7.
- No se dibujan los montajes de desarrollo: el código de identidad, accesos y parqueadero en
  `/code`, el del frontend en `/app` (con `node_modules` en un volumen anónimo) y la plantilla
  `gateway/nginx.conf.template` en solo lectura.
- Orden de arranque (`depends_on`): cada backend espera a que su base esté sana; accesos espera
  además a identidad y parqueadero; el gateway, a los cuatro backends.

Verificado contra: `docker-compose.yml` y el `Dockerfile` de cada servicio.
