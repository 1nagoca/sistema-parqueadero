# Proceso: consulta de cupos en tiempo real y auditoría

Son dos consultas, ninguna cambia datos. Cualquier usuario con sesión abre el mapa y ve los cupos
de cada zona; el navegador se queda conectado por WebSocket y, cada vez que el vigilante registra
una entrada o una salida, Parqueadero avisa y el mapa se actualiza solo, sin recargar la página.
Por su parte, el administrador abre la auditoría y ve en una sola lista lo que guardan dos
servicios distintos: las trazas de accesos y las de verificaciones.

```mermaid
flowchart TB
    subgraph EST["Estudiante (o cualquier usuario con sesión)"]
        direction TB
        e0(["Inicio"])
        e1["Abre el mapa de cupos"]
        e2["Ve los cupos y espacios<br/>al día, sin recargar"]
    end

    subgraph VIG["Vigilante"]
        direction TB
        v1["Registra una entrada o una<br/>salida (proceso 06 o 07)"]
    end

    subgraph SIS["Sistema · parqueadero, accesos e identidad"]
        direction TB
        s1["Parqueadero entrega las zonas<br/>y los espacios"]
        s2["El navegador abre el<br/>WebSocket /ws/zonas"]
        s3["Parqueadero emite zona_actualizada<br/>a todos los conectados"]
        s4["El mapa vuelve a pedir<br/>las zonas y los espacios"]
        s5["Accesos entrega las últimas 200 trazas<br/>de auditoria_accesos"]
        s6["Identidad entrega las últimas 200 trazas<br/>de auditoria_identidad"]
    end

    subgraph ADM["Administrador"]
        direction TB
        a0(["Inicio"])
        a1["Abre la pestaña Auditoría"]
        a2["Ve las dos fuentes juntas, por fecha,<br/>y puede filtrar por tabla"]
    end

    e0 --> e1 --> s1 --> s2
    v1 --> s3
    s2 -.->|"queda a la espera"| s3
    s3 --> s4 --> e2

    a0 --> a1
    a1 --> s5 --> a2
    a1 --> s6 --> a2
```

| Carril | Actividad | Sistema / ruta | Resultado |
|---|---|---|---|
| Estudiante (o cualquier usuario) | Abre el mapa de cupos | Frontend `/mapa` → `GET /api/v1/zonas` y `GET /api/v1/espacios?zona_id=` (parqueadero) | Zonas activas con `cupos_disponibles/capacidad_total` y el estado de cada espacio; basta una sesión válida, sin importar el rol |
| Sistema | Abre el canal en tiempo real | Navegador → gateway `/ws/*` → parqueadero `/ws/zonas` | Conexión abierta; si se cae, el navegador reintenta con esperas de 1 a 10 s |
| Vigilante | Registra una entrada o una salida | Procesos [06](06-entrada-y-salida.md) y [07](07-acceso-de-visitante.md) | Parqueadero mueve el cupo |
| Sistema | Avisa el cambio | Parqueadero, tras `POST /interno/cupos/ocupar` o `liberar` | Evento `zona_actualizada` con la zona y sus cupos, a todos los conectados |
| Sistema | Refresca el mapa | Frontend: vuelve a pedir zonas y espacios | El usuario ve los cupos al día |
| Vigilante | Ve los cupos en su panel | Frontend `/vigilante` → `GET /api/v1/zonas` | Se recargan después de cada operación suya (no usa el WebSocket) |
| Administrador | Abre la pestaña Auditoría | Frontend `/admin` → `GET /api/v1/auditoria` (accesos) y `GET /api/v1/verificaciones/auditoria` (identidad) | Solo administrador; las últimas 200 trazas de cada servicio |
| Administrador | Revisa y filtra | Parámetro `tabla_afectada` en ambas rutas | Una sola lista ordenada por fecha, con el origen de cada traza; si un servicio falla, se muestra el otro con un aviso |

- La auditoría es de solo lectura: no hay rutas para modificarla y las tablas `auditoria_accesos`
  y `auditoria_identidad` solo admiten inserción (RN-04).
- **Límites actuales**, anotados en [`pendientes.md`](../pendientes.md): `/ws/zonas` no valida la
  sesión, y el filtro ofrece «espacios» y «zonas», tablas de las que ningún servicio escribe trazas.

Verificado contra: `frontend/src/pages/user/ParkingMapPage.tsx`,
`frontend/src/services/realtime/useActualizacionesZona.ts`, `frontend/src/pages/admin/AdminDashboard.tsx`,
`backend-parqueadero/app/api/v1/routers/{zonas,espacios,realtime,cupos}.py`,
`backend-accesos/app/api/v1/routers/auditoria.py` y `backend-identidad/app/api/v1/routers/verificaciones.py`.
