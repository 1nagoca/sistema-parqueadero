# Proceso: entrada y salida de un vehículo

El vigilante elige la zona y busca la placa: la escribe, la lee con una foto (servicio de visión)
o escanea un QR. Si el vehículo está registrado, registra la entrada. Entonces el sistema hace tres
cosas en orden: Accesos le pregunta a Identidad si el vehículo y su dueño están aprobados, le pide
a Parqueadero que descuente el cupo y, por último, guarda el acceso con su traza de auditoría. Si
algo falla, la entrada se rechaza con un motivo claro. La salida es el camino inverso: se cierra
el acceso y se devuelve el cupo. Cada cambio de cupo se avisa por WebSocket al mapa.

```mermaid
flowchart TB
    subgraph VIG["Vigilante"]
        direction TB
        v0(["Inicio: llega un vehículo"])
        v1["Elige la zona y,<br/>si quiere, un espacio libre"]
        v2["Busca la placa: la escribe,<br/>la lee con una foto o escanea un QR"]
        v3["Pulsa Registrar entrada"]
        v4["Pulsa Registrar salida<br/>(resultado de la búsqueda o<br/>lista de vehículos adentro)"]
        v5["Ve el motivo del rechazo"]
    end

    subgraph SIS["Sistema · visión, identidad, accesos y parqueadero"]
        direction TB
        s1["Visión lee la placa de la foto<br/>(el gateway valida la sesión)"]
        s2{"¿La placa tiene<br/>un acceso abierto?"}
        s3{"¿El vehículo<br/>está registrado?"}
        s4{"¿Identidad responde, el vehículo<br/>existe y él y su dueño<br/>están aprobados?"}
        s5{"¿El vehículo<br/>ya está adentro?"}
        s6{"¿Hay cupo en la zona<br/>y el espacio está libre?"}
        s7["Parqueadero descuenta el cupo<br/>y ocupa el espacio"]
        s8["Accesos guarda el acceso con la placa<br/>y su traza en auditoria_accesos"]
        s9["Accesos cierra el acceso<br/>(hora de salida y duración)"]
        s10["Parqueadero devuelve el cupo<br/>y libera el espacio"]
        s11["Accesos escribe la traza de<br/>la salida en auditoria_accesos"]
        s12["Parqueadero avisa el cambio de cupo<br/>por WebSocket"]
        f1(["Fin: entrada o salida registrada"])
        p7(["Sigue en el proceso 07:<br/>acceso de visitante"])
    end

    subgraph EST["Estudiante"]
        direction TB
        e1["Ve el mapa de cupos actualizado<br/>si lo tiene abierto"]
    end

    subgraph ADM["Administrador"]
        direction TB
        a1["Puede hacer lo mismo que el vigilante<br/>desde el panel de vigilancia"]
    end

    v0 --> v1 --> v2
    v2 -->|"Con foto"| s1 --> s2
    v2 -->|"Escrita o QR"| s2
    s2 -->|"Sí"| v4
    s2 -->|"No"| s3
    s3 -->|"No"| p7
    s3 -->|"Sí"| v3 --> s4
    s4 -->|"No: 503, 404 o 409"| v5
    s4 -->|"Sí"| s5
    s5 -->|"Sí: 409"| v5
    s5 -->|"No"| s6
    s6 -->|"No: 409"| v5
    s6 -->|"Sí"| s7 --> s8 --> f1
    v4 --> s9 --> s10 --> s11 --> f1
    s7 -.-> s12
    s10 -.-> s12
    s12 -.-> e1
```

| Carril | Actividad | Sistema / ruta | Resultado |
|---|---|---|---|
| Vigilante | Elige la zona y, si quiere, un espacio libre | `GET /api/v1/zonas`, `GET /api/v1/espacios?zona_id=` (parqueadero) | Ve los cupos de la zona; sin espacio, solo se mueve el contador |
| Vigilante | Lee la placa con una foto | `POST /api/v1/alpr/reconocer` (visión; el gateway valida antes la sesión contra identidad) | Placa y confianza. 400 si la imagen no sirve; 422 si no se detecta una placa |
| Vigilante | Busca la placa (escrita, leída o por QR) | `GET /api/v1/accesos/buscar?placa=` (accesos) y `GET /api/v1/vehiculos/placa/{placa}` (identidad) | Acceso abierto → ofrece la salida; vehículo registrado → ofrece la entrada; no registrado → [proceso 07](07-acceso-de-visitante.md) |
| Vigilante | Registra la entrada | `POST /api/v1/accesos/entrada` con `tipo_acceso: normal` | 201 con el acceso; guarda si la placa la leyó la cámara y con qué confianza |
| Sistema | Consulta el vehículo | Accesos → `GET /interno/vehiculos/{id}` (identidad) | **503** si identidad no responde en 5 s; **404** si el vehículo no existe; **409** si el vehículo o su dueño no están aprobados |
| Sistema | Comprueba que no esté adentro | Accesos, índice único `uq_accesos_vehiculo_activo` | **409** «El vehículo ya tiene un acceso activo» |
| Sistema | Ocupa el cupo (RN-01) | Accesos → `POST /interno/cupos/ocupar` (parqueadero) | Descuento atómico. **409** si la zona no tiene cupos o el espacio no está libre; 503 si parqueadero no responde |
| Sistema | Guarda el acceso y su traza (RN-04) | Accesos, tablas `accesos` y `auditoria_accesos` | Acceso con la placa y traza de creación en una sola transacción; si falla, se libera el cupo (compensación) |
| Vigilante | Registra la salida | `POST /api/v1/accesos/{id}/salida` | 404 si el acceso no existe o ya se cerró |
| Sistema | Cierra el acceso (RN-02) | Accesos | Hora de salida y minutos de permanencia |
| Sistema | Libera el cupo | Accesos → `POST /interno/cupos/liberar` (parqueadero) | Cupo devuelto y espacio libre. Si parqueadero falla (503 o 409), la salida se revierte y el acceso sigue abierto |
| Sistema | Deja la traza de la salida | Accesos, `auditoria_accesos` | Traza de actualización; si falla, se vuelve a ocupar el cupo (compensación) |
| Sistema | Avisa el cambio de cupo | Parqueadero, WebSocket `/ws/zonas` | Evento `zona_actualizada` a todos los mapas abiertos |
| Estudiante | Ve el mapa actualizado | Frontend `/mapa` | Ver [proceso 08](08-cupos-y-auditoria.md) |
| Administrador | Opera el panel de vigilancia | Frontend `/vigilante` (roles vigilante y admin) | Las mismas actividades del vigilante |

- **Si identidad se cae**, toda entrada responde 503; las salidas, la lista de vehículos adentro
  y la búsqueda siguen funcionando porque `accesos` guarda la placa.
- El rechazo llega al vigilante como un mensaje en su pantalla; no se crea ningún acceso.
- Si la compensación del cupo también falla, hoy solo queda un registro en el log.

Verificado contra: `backend-accesos/app/api/v1/routers/accesos.py`,
`backend-accesos/app/services/acceso_service.py`, `backend-accesos/app/{identidad_client,parqueadero_client}/client.py`,
`backend-parqueadero/app/api/v1/routers/cupos.py`, `backend-parqueadero/app/services/zona_service.py`,
`backend-vision/app/api/routers/alpr.py`, `gateway/nginx.conf.template` y `frontend/src/pages/guard/GuardDashboard.tsx`.
