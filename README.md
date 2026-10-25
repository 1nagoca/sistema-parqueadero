# Parqueadero de motos — UFPS

Aplicación web para gestionar el parqueadero de motos de la Universidad Francisco de Paula
Santander (UFPS). Muestra los cupos en tiempo real, registra las entradas y salidas, lee las
placas desde una foto y verifica que cada moto pertenezca a un estudiante aprobado.

**En línea:** https://motosufps.me

## Introducción

El parqueadero recibe solo motos. Cada estudiante se registra, sube sus documentos y los de su
moto, y un administrador los aprueba. En la portería, el vigilante busca la placa (escribiéndola
o tomándole una foto), confirma el nombre y el carnet del dueño, elige un puesto libre en el
plano y registra la entrada. Al salir, el puesto se libera y el mapa de cupos se actualiza al
instante en todas las pantallas.

Hay tres roles:

| Rol | Qué hace |
|---|---|
| Estudiante | Se registra, sube sus documentos y los de su moto, y consulta el mapa de cupos |
| Vigilante | Registra entradas y salidas, lee placas con la cámara y confirma al dueño |
| Administrador | Aprueba documentos, gestiona usuarios, zonas y puestos, y revisa la auditoría |

Toda entrada, salida y cambio de cupo queda en una auditoría que no se modifica. Al cierre de
cada semestre los accesos viejos se archivan y se borran.

## Lenguajes y tecnologías

| Lenguaje | Dónde se usa | Tecnologías principales |
|---|---|---|
| **Python 3.11** | Los cuatro backends | FastAPI, SQLAlchemy 2, Alembic, Pydantic, pytest |
| **TypeScript** (JavaScript) | Frontend | React 18, Vite, Tailwind CSS, React Router |
| **SQL** | Bases de datos y migraciones | PostgreSQL 16 |
| Configuración | Gateway, contenedores y despliegue | nginx, Docker Compose, GitHub Actions, Caddy |

Otras piezas:

- **Lectura de placas:** EasyOCR y OpenCV sobre PyTorch (solo CPU).
- **Seguridad:** sesión con JWT y contraseñas cifradas con bcrypt.
- **Tiempo real:** WebSocket para el mapa de cupos.
- **Aplicación instalable (PWA):** se puede agregar al celular como una app.

## Arquitectura

Son cuatro microservicios, cada uno con su propia base de datos, detrás de un único punto de
entrada (gateway):

| Servicio | Carpeta | Responsabilidad |
|---|---|---|
| Gateway | `gateway/` | Única entrada de la API; reparte cada ruta al servicio que corresponde |
| Identidad | `backend-identidad/` | Inicio de sesión, usuarios, motos, documentos y verificaciones |
| Accesos | `backend-accesos/` | Entradas, salidas, auditoría y cierre de semestre |
| Parqueadero | `backend-parqueadero/` | Zonas, puestos y cupos en tiempo real |
| Visión | `backend-vision/` | Lectura de placas a partir de una foto (sin base de datos) |
| Frontend | `frontend/` | Interfaz web para los tres roles |

Los servicios solo se comunican por API; ninguno lee las tablas de otro. El modelo de datos está
en [`base-de-datos/`](base-de-datos/diccionario-de-datos.md) y las pruebas de la API en
[`postman/`](postman/).

## Despliegue

| | |
|---|---|
| Dirección | https://motosufps.me |
| Servidor | Máquina virtual Ubuntu 24.04 en **Microsoft Azure** (región México Central, 2 CPU y 4 GB), con el crédito de Azure for Students |
| Contenedores | Todo el sistema corre con el mismo `docker-compose.yml` del desarrollo |
| HTTPS | Caddy, con certificado de Let's Encrypt renovado automáticamente |
| Dominio | `motosufps.me`, del GitHub Student Developer Pack (Namecheap) |
| Actualización | Automática: cada push a `main` ejecuta el flujo [`desplegar.yml`](.github/workflows/desplegar.yml), que actualiza el código, reconstruye los contenedores y aplica las migraciones |
| Horario | Encendido de lunes a viernes de 6:00 a. m. a 10:00 p. m. (hora de Colombia) |

## Cómo correrlo en local

Requisitos: Docker con Docker Compose.

```bash
cp .env.example .env    # y completar los valores
docker compose up -d
docker compose exec backend-identidad alembic upgrade head
docker compose exec backend-accesos alembic upgrade head
docker compose exec backend-parqueadero alembic upgrade head
docker compose exec backend-identidad python -m app.db.seed   # crea el admin y el vigilante (variables SEED_* del .env)
```

- Frontend: http://localhost:5173
- API (gateway): http://localhost:8000
- Pruebas: `docker compose exec -T -e PYTHONPATH=. <servicio> pytest` en `backend-identidad`,
  `backend-accesos` y `backend-parqueadero`.
