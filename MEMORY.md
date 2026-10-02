# Memoria del proyecto

## Estado
- Autorregistro de estudiantes con verificación de documentos: hecho y probado (5 tests), en el PR #1 (rama `claude/funny-fermi-3qd1rv`).
- Estudiante: se registra (@ufps.edu.co), registra su carro/moto y sube foto de placa, tarjeta de propiedad y carnet/Divisist.
- Admin: pestaña Verificaciones, aprueba o rechaza con motivo; cada decisión queda en auditoría.
- La interfaz aún no se ha probado en un navegador.

## Decisiones (con su porqué)
- El admin nunca conoce contraseñas (solo el hash) y no puede crear estudiantes: privacidad.
- Documentos en volumen privado y descarga autenticada (solo admin y dueño): son datos personales sensibles (Ley 1581).
- Un acceso normal exige vehículo y dueño aprobados; el visitante tiene su propio flujo.
- Código y textos en español, igual que el resto del proyecto.

## Errores a evitar
- `tsconfig` con `ignoreDeprecations: "6.0"` falla con TypeScript 5.9 (ya existía).
- Los tests necesitan Postgres real, no SQLite.

## Siguiente paso
Probar `/registro` en local; luego verificación de correo con enlace y recuperación de contraseña (requieren servicio de correo).
