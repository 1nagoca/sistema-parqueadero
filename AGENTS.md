# Parqueadero UFPS
Gestión de parqueadero universitario: cupos en tiempo real, accesos, verificación de estudiantes.

## Stack
- backend-core: FastAPI + SQLAlchemy 2 + Alembic + Postgres 16 (JWT, bcrypt)
- backend-vision: FastAPI, lectura de placas (OCR); solo lo llama backend-core
- frontend: React 18 + Vite + TypeScript + Tailwind
- Todo se levanta con docker-compose

## Estructura
backend-core/app/{api/v1/routers, models, schemas, services}, alembic/versions
frontend/src/{pages, components, services/api, types}

## Comandos
- `docker compose up` · `alembic upgrade head` (en backend-core)
- Tests: `cd backend-core && PYTHONPATH=. pytest` (necesita DATABASE_URL y SECRET_KEY)
- Frontend: `npm run build`

## Convenciones
- Dominio y textos en español; routers delgados, lógica en services/
- Migraciones a mano con op.execute; enums de Postgres con create_type=False

## Trampas conocidas
- Los tests exigen Postgres real (gen_random_uuid, enums)
- auditoria_accesos es append-only
- tsconfig "ignoreDeprecations": "6.0" falla con TypeScript 5.9

## Límites
✅ Probar antes de dar algo por terminado
⚠️ Preguntar antes de cambiar el esquema de BD o dependencias
🚫 Nunca mostrar contraseñas ni servir documentos como estáticos
🚫 Nunca subir claves ni .env

## Verificación
Tests del backend pasan + `npm run build` compila.

## Memoria
- Al empezar, lee MEMORY.md. Al terminar cada tarea, actualízalo (~50 líneas).
- Si algo se vuelve regla permanente, propón moverlo aquí.
- Nunca guardes claves, tokens ni datos personales.
