# Arquitectura — Parqueadero UFPS

El sistema migra de un backend único a microservicios, un servicio por vez. Este documento dice
a dónde vamos y en qué punto estamos.

## Objetivo: cuatro microservicios

Cada servicio tiene su propia base de datos y su propia API. Entre ellos solo se hablan por API;
ninguno lee las tablas de otro.

| Servicio | Responsabilidad | Datos propios |
|---|---|---|
| Identidad y verificación | Inicio de sesión, usuarios, vehículos, documentos y su aprobación | `usuarios`, `vehiculos`, `documentos` |
| Parqueadero | Zonas, espacios y cupos en tiempo real (WebSocket) | `zonas`, `espacios` |
| Accesos | Entradas, salidas y auditoría | `accesos`, `auditoria_accesos` |
| Visión (ALPR) | Lectura de placas a partir de una foto | Ninguno (sin estado) |

El navegador entra siempre por el **API Gateway** (nginx), que reparte cada ruta al servicio que
corresponde. Así el frontend conoce una sola dirección.

```
Navegador → gateway :8000 → /api/v1/alpr/*  → visión
                          → /ws/*           → parqueadero
                          → lo demás        → identidad / parqueadero / accesos
```

## Estado actual

| Paso | Estado |
|---|---|
| 1. Gateway + visión con pantalla propia | Hecho |
| 2. Separar Parqueadero | Pendiente |
| 3. Separar Identidad y verificación | Pendiente |
| 4. Accesos con su base y auditoría | Pendiente |

Hoy Identidad, Parqueadero y Accesos siguen juntos en `backend-core` con una sola base de datos.
Visión ya es un microservicio independiente: el gateway le envía directamente las fotos de placa
desde el panel del vigilante.

## Decisiones

- **Gateway en nginx.** Es una pieza estándar, liviana y solo se configura; no hay código propio
  que mantener (`gateway/nginx.conf.template`).
- **Visión no conoce usuarios.** No tiene base de datos ni lógica de negocio. El gateway valida la
  sesión contra Identidad (`auth_request`) antes de dejar pasar la imagen.
- **Los servicios de atrás no publican puerto.** Solo el gateway es alcanzable desde fuera.

## Lo que falta resolver

- **Consistencia de cupos.** Hoy registrar una entrada descuenta el cupo en la misma transacción.
  Con bases separadas, Accesos reserva el cupo en Parqueadero, crea el acceso y, si falla, libera
  el cupo (compensación).
- **Referencias entre servicios.** Las llaves foráneas que cruzan servicios (por ejemplo
  `accesos.vehiculo_id`) pasan a ser identificadores sin restricción en la base.
- **Autenticación.** Cada servicio valida el mismo token JWT por su cuenta.
