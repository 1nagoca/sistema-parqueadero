# Reglas de negocio

Se aplican siempre en el backend. Cómo se cumplen entre servicios está en
[`arquitectura.md`](arquitectura.md).

- **RN-01 — Descuento atómico de cupo.** Al registrar una entrada se verifica la disponibilidad
  de la zona y se descuenta el cupo de forma atómica. Si no hay cupos disponibles, no se permite
  el ingreso.
- **RN-02 — Liberación atómica de cupo.** Al registrar una salida se devuelve el cupo a la zona
  y el acceso queda con la fecha y hora exacta de salida y el tiempo de permanencia.
- **RN-03 — Trazabilidad y vinculación obligatoria.** Todo vehículo que ingresa debe estar
  vinculado a un usuario activo con rol válido. Los visitantes o vehículos no registrados
  requieren autorización manual del vigilante, con la justificación guardada en el sistema.
- **RN-04 — Auditoría e inmutabilidad.** No se cambia el estado de un cupo ni se elimina un
  registro de acceso sin dejar su traza en `auditoria_accesos`.
- **RN-05 — Solo motos.** El parqueadero recibe únicamente motos: el registro del estudiante y
  el del visitante rechazan cualquier otro tipo, y la placa debe tener formato de moto
  (`ABC12` o `ABC12D`). La base conserva los demás valores del enum, pero la API no los acepta.
- **RN-06 — Toda entrada ocupa un puesto.** El vigilante elige un puesto libre del plano en cada
  entrada, normal o de visitante; sin `espacio_id` la API de accesos responde 422. Parqueadero
  solo ocupa el puesto si está libre y es de la zona de la entrada (si no, 409 y no se descuenta
  el cupo).
