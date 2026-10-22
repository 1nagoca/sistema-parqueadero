# Despliegue en un servidor

Cómo montar el sistema en una VM con el mismo `docker-compose.yml` de desarrollo, sin cambiar
código. La arquitectura está en [`arquitectura.md`](arquitectura.md).

## Plan

- Una VM Ubuntu (droplet de DigitalOcean de 2 GB, con el crédito del GitHub Student Pack) que
  corre `docker compose up -d`.
- Caddy instalado en la VM, delante de todo: da HTTPS con un dominio y reparte las rutas.
  El HTTPS es obligatorio porque la cámara del celular (QR y PWA) no funciona sin él fuera de
  localhost.
- Descartados Vercel, Neon y Render: visión (EasyOCR + torch) pasa de los 512 MB de los planes
  gratis, esos servicios se duermen, `/interno` quedaría público y `uploads/` se perdería.

## 1. Preparar la VM

1. Crear el droplet (Ubuntu LTS, 2 GB) y cargar la llave SSH **pública** de quien lo crea.
2. Entrar con `ssh root@IP_DEL_SERVIDOR`, crear un usuario normal y dejar de usar `root`.
3. Instalar Docker con el plugin de Compose (guía oficial de Docker para Ubuntu).
4. Agregar 2 GB de swap: construir la imagen de visión (torch) con 2 GB de RAM puede quedarse
   sin memoria.
5. Firewall: `ufw allow OpenSSH`, `ufw allow 80`, `ufw allow 443`, `ufw enable`.

## 2. Código y `.env`

```bash
git clone https://github.com/1nagoca/sistema-parqueadero.git
cd sistema-parqueadero
cp .env.example .env
```

En el `.env` del servidor (nunca se sube a Git):

- **Claves nuevas**, distintas a las de desarrollo: `POSTGRES_PASSWORD`, `SECRET_KEY` (por
  ejemplo `openssl rand -hex 32`), `SEED_ADMIN_PASSWORD` y `SEED_VIGILANTE_PASSWORD` (mínimo 12
  caracteres). Se comparten entre el equipo por privado, nunca en el repo.
- **Puertos solo en localhost.** Docker se salta el firewall al publicar puertos, así que sin
  esto las bases quedarían abiertas a internet:

  ```
  POSTGRES_PORT=127.0.0.1:5432
  PARQUEADERO_DB_PORT=127.0.0.1:5434
  IDENTIDAD_DB_PORT=127.0.0.1:5435
  GATEWAY_PORT=127.0.0.1:8000
  FRONTEND_PORT=127.0.0.1:5173
  ```

- **El dominio** (todo bajo el mismo dominio, Caddy reparte por ruta):

  ```
  CORS_ORIGINS=["https://DOMINIO"]
  FRONTEND_ORIGIN=https://DOMINIO
  VITE_API_BASE_URL=https://DOMINIO/api/v1
  VITE_WS_URL=wss://DOMINIO/ws/zonas
  ```

## 3. Levantar

```bash
docker compose up -d --build
docker compose exec backend-accesos alembic upgrade head
docker compose exec backend-identidad alembic upgrade head
docker compose exec backend-parqueadero alembic upgrade head
docker compose exec backend-identidad python -m app.db.seed
```

- Visión baja sus modelos de OCR al arrancar: la primera vez tarda y necesita internet.
- En una base nueva las migraciones 0003 y 0005 de accesos no piden confirmación (solo la
  piden si hay datos viejos).

## 4. Caddy (HTTPS)

1. Apuntar el dominio a la IP del servidor (registro `A` en el proveedor del dominio).
2. Instalar Caddy (guía oficial para Ubuntu) y poner en `/etc/caddy/Caddyfile`:

   ```
   DOMINIO {
       handle /api/* {
           reverse_proxy 127.0.0.1:8000
       }
       handle /ws/* {
           reverse_proxy 127.0.0.1:8000
       }
       handle {
           # Vite solo acepta peticiones con Host localhost
           reverse_proxy 127.0.0.1:5173 {
               header_up Host localhost
           }
       }
   }
   ```

3. `sudo systemctl reload caddy`. Caddy saca y renueva solo el certificado HTTPS.

## 5. Acceso del equipo

- El servidor queda en la cuenta de DigitalOcean de quien tiene el crédito.
- Cada integrante entra con **su propia** llave SSH: crea la suya (`ssh-keygen -t ed25519`),
  manda solo la parte pública (`.pub`) y se agrega en `~/.ssh/authorized_keys` del usuario del
  servidor. Nunca se comparten llaves privadas ni la contraseña de la cuenta.
- Para quitarle el acceso a alguien basta con borrar su línea de `authorized_keys`.

## 6. Actualizar después de un cambio

```bash
cd sistema-parqueadero
git pull
docker compose up -d --build
docker compose exec backend-accesos alembic upgrade head
docker compose exec backend-identidad alembic upgrade head
docker compose exec backend-parqueadero alembic upgrade head
```

- Visión copia su código dentro de la imagen: sin `--build` sigue con el código viejo.
- **Nunca** `docker compose down -v`: borra los volúmenes, es decir las tres bases y los
  documentos subidos por los estudiantes.

## Limitaciones conocidas

- El frontend se sirve con el servidor de desarrollo de Vite, igual que en local. El service
  worker de la PWA solo se registra en el build de producción, así que en el servidor no aparece
  el aviso «Sin conexión». Servir el build es un cambio aparte, pendiente de decidir.
- Los backends corren con `--reload`, como en desarrollo.
