# Arquitectura de microservicios

El navegador solo conoce una dirección: el **API Gateway** (nginx, puerto 8000), que reparte cada
ruta al microservicio que le corresponde. Detrás hay cuatro servicios; tres tienen su propia base
de datos y Visión no guarda nada. Ningún servicio lee las tablas de otro: Accesos le pregunta a
Identidad por el vehículo y los usuarios, y a Parqueadero le pide ocupar o liberar el cupo, siempre
por la API `/interno`, que el gateway no publica. Antes de dejar pasar una foto a Visión, el
gateway comprueba la sesión contra Identidad (línea punteada).

```mermaid
flowchart TB
    nav["Navegador<br/>frontend React + Vite · :5173"]
    gw["API Gateway · nginx<br/>:8000 · única entrada de la API"]

    subgraph s_ide["Identidad"]
        ide["backend-identidad<br/>:8003 interno"]
        dbi[("parqueadero_identidad<br/>db-identidad · host :5435")]
        ide --> dbi
    end

    subgraph s_acc["Accesos"]
        acc["backend-accesos<br/>:8000 interno"]
        dba[("parqueadero<br/>db · host :5432")]
        acc --> dba
    end

    subgraph s_par["Parqueadero"]
        par["backend-parqueadero<br/>:8002 interno"]
        dbp[("parqueadero_zonas<br/>db-parqueadero · host :5434")]
        par --> dbp
    end

    subgraph s_vis["Visión"]
        vis["backend-vision<br/>:8001 interno · sin base de datos"]
    end

    nav -->|"HTTP y WebSocket"| gw

    gw -->|"/api/v1/auth, usuarios, vehiculos,<br/>documentos, verificaciones"| ide
    gw -->|"lo demás:<br/>/api/v1/accesos, /api/v1/auditoria"| acc
    gw -->|"/api/v1/zonas, espacios, reportes<br/>/ws/* (WebSocket)"| par
    gw -->|"/api/v1/alpr/*"| vis
    gw -.->|"auth_request antes de visión:<br/>GET /api/v1/usuarios/me"| ide

    acc ==>|"GET /interno/vehiculos/{id}<br/>GET /interno/usuarios"| ide
    acc ==>|"POST /interno/cupos/ocupar y liberar<br/>GET /interno/espacios"| par
```

- Flecha fina: lo que reparte el gateway. Flecha gruesa: llamadas entre servicios por `/interno`.
- Los puertos de las bases son los que se publican en el equipo anfitrión por defecto; se cambian
  en `.env` (`POSTGRES_PORT`, `PARQUEADERO_DB_PORT`, `IDENTIDAD_DB_PORT`). Dentro de la red de
  Docker las tres escuchan en el 5432.
- Accesos y Parqueadero no consultan a Identidad para autorizar: validan la firma del token.

Verificado contra: `gateway/nginx.conf.template`, `docker-compose.yml`, los routers de cada
servicio y `backend-accesos/app/{identidad_client,parqueadero_client}/client.py`.
