# Proceso: acceso de visitante

Cuando la placa no está registrada, el vehículo es un visitante y no puede entrar por el camino
normal. Según la regla RN-03, alguien debe autorizarlo y dejar escrita la justificación: lo hace
el vigilante (o un administrador) desde el panel de vigilancia. El sistema crea el vehículo como
visitante, sin dueño, y guarda el acceso con quién lo autorizó y por qué. A un visitante no se le
exige verificación de documentos, pero sí que haya cupo. La salida es la misma del proceso 06.

```mermaid
flowchart TB
    subgraph VIG["Vigilante"]
        direction TB
        v0(["Inicio: llega un vehículo<br/>que no es de la universidad"])
        v1["Elige la zona y busca la placa"]
        v2["Elige el tipo de vehículo y<br/>escribe la justificación (obligatoria)"]
        v3["Pulsa Autorizar entrada<br/>de visitante"]
        v4["Ve el motivo del rechazo"]
    end

    subgraph SIS["Sistema · identidad, accesos y parqueadero"]
        direction TB
        s1{"¿El vehículo<br/>está registrado?"}
        s2["Identidad crea el vehículo<br/>como visitante, sin dueño"]
        s3{"¿Vienen quien autoriza<br/>y la justificación?"}
        s4{"¿Identidad responde y existen<br/>el vehículo y quien autoriza?"}
        s5{"¿Hay cupo en la zona<br/>y el espacio está libre?"}
        s6["Parqueadero descuenta el cupo"]
        s7["Accesos guarda el acceso de tipo visitante<br/>con quien autorizó y la justificación,<br/>y su traza en auditoria_accesos"]
        f1(["Fin: visitante adentro.<br/>La salida es la del proceso 06"])
        p6(["Sigue en el proceso 06:<br/>entrada normal"])
    end

    subgraph ADM["Administrador"]
        direction TB
        a1["Puede autorizar al visitante igual que<br/>el vigilante, desde el panel de vigilancia"]
    end

    subgraph EST["Estudiante"]
        direction TB
        e0["Sin actividades en este proceso"]
    end

    v0 --> v1 --> s1
    s1 -->|"Sí"| p6
    s1 -->|"No"| v2 --> v3 --> s2 --> s3
    s3 -->|"No: 422"| v4
    s3 -->|"Sí"| s4
    s4 -->|"No: 503 o 404"| v4
    s4 -->|"Sí"| s5
    s5 -->|"No: 409"| v4
    s5 -->|"Sí"| s6 --> s7 --> f1
```

| Carril | Actividad | Sistema / ruta | Resultado |
|---|---|---|---|
| Vigilante | Elige la zona y busca la placa | `GET /api/v1/accesos/buscar?placa=` y `GET /api/v1/vehiculos/placa/{placa}` | 404 en ambas: el panel muestra «Vehículo no registrado — requiere autorización de visitante» |
| Vigilante | Elige el tipo de vehículo y escribe la justificación | Frontend `/vigilante` | El botón no se habilita sin justificación ni cuando la zona no tiene cupos |
| Vigilante | Autoriza la entrada | `POST /api/v1/vehiculos` y luego `POST /api/v1/accesos/entrada` | Dos llamadas seguidas desde el navegador |
| Sistema | Crea el vehículo de visitante | Identidad, `POST /api/v1/vehiculos` con `es_visitante: true` (solo vigilante o admin) | 201: vehículo sin dueño. 409 si la placa ya existe |
| Sistema | Exige autorización y justificación (RN-03) | Accesos: validación del cuerpo y restricción `ck_accesos_visitante_requiere_autorizacion` | **422** si falta `autorizado_por_id` o `justificacion` |
| Sistema | Consulta a identidad | Accesos → `GET /interno/vehiculos/{id}` y `GET /interno/usuarios?id=` | **503** si identidad no responde; **404** si no existen el vehículo o quien autoriza. No se exige que estén verificados |
| Sistema | Ocupa el cupo (RN-01) | Accesos → `POST /interno/cupos/ocupar` (parqueadero) | **409** si no hay cupos o el espacio no está libre |
| Sistema | Guarda el acceso y su traza | Accesos, `accesos` y `auditoria_accesos` | Acceso de tipo `visitante` con `autorizado_por_id` y `justificacion`; la traza registra el tipo de acceso |
| Administrador | Autoriza a un visitante | Frontend `/vigilante` (roles vigilante y admin) | Las mismas actividades del vigilante; queda él como quien autoriza |
| Estudiante | — | — | No participa |

- Quien autoriza es siempre el usuario con sesión en el panel: el frontend envía su identificador.
- **Límite actual:** el vehículo de visitante queda registrado. Si vuelve, la búsqueda lo encuentra
  y entra por el [proceso 06](06-entrada-y-salida.md) como acceso normal, sin autorización ni
  justificación. Tampoco se comprueba que quien autoriza sea vigilante o administrador. Ambos puntos
  están anotados en [`pendientes.md`](../pendientes.md).

Verificado contra: `frontend/src/pages/guard/GuardDashboard.tsx`,
`backend-identidad/app/api/v1/routers/{vehiculos,interno}.py`, `backend-identidad/app/models/vehiculo.py`,
`backend-accesos/app/schemas/acceso.py`, `backend-accesos/app/services/acceso_service.py`,
`backend-accesos/alembic/versions/0001_estructura_inicial.py` y `docs/reglas-de-negocio.md` (RN-03).
