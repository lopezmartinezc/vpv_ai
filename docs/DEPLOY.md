# Guia de Despliegue — Liga VPV Fantasy

Guia completa para desplegar la aplicacion en produccion (AlmaLinux 10) y migrar la base de datos desde MySQL a PostgreSQL.

## Indice

1. [Requisitos del servidor](#1-requisitos-del-servidor)
2. [Instalacion de dependencias del sistema](#2-instalacion-de-dependencias-del-sistema)
3. [PostgreSQL nativo](#3-postgresql-nativo)
4. [Migracion MySQL a PostgreSQL](#4-migracion-mysql-a-postgresql)
5. [Backend (FastAPI)](#5-backend-fastapi)
6. [Frontend (Next.js)](#6-frontend-nextjs)
7. [Nginx + SSL](#7-nginx--ssl)
8. [Systemd + PM2](#8-systemd--pm2)
9. [Fotos de jugadores](#9-fotos-de-jugadores)
10. [Backups y cron](#10-backups-y-cron)
11. [Verificacion final](#11-verificacion-final)
12. [Actualizaciones posteriores](#12-actualizaciones-posteriores)
13. [Rollback](#13-rollback)
14. [Desarrollo local (Docker)](#14-desarrollo-local-docker)

---

## 1. Requisitos del servidor

- AlmaLinux 10 (servidor dedicado)
- Dominio: ligavpv.com apuntando al servidor
- Puertos abiertos: 80, 443
- RAM minima: 2 GB
- Disco: 10 GB libres (BD + fotos jugadores)

## 2. Instalacion de dependencias del sistema

```bash
# Actualizar sistema
sudo dnf update -y

# Python 3.12
sudo dnf install -y python3.12 python3.12-pip python3.12-devel

# Node.js 20 LTS
sudo dnf module enable nodejs:20 -y
sudo dnf install -y nodejs npm

# PM2 (gestor de procesos Node.js)
sudo npm install -g pm2

# Herramientas de compilacion (para dependencias Python nativas)
sudo dnf install -y gcc gcc-c++ libpq-devel

# Nginx
sudo dnf install -y nginx

# Certbot (SSL)
sudo dnf install -y certbot python3-certbot-nginx

# Git
sudo dnf install -y git
```

## 3. PostgreSQL nativo

PostgreSQL se instala directamente en el servidor (sin Docker) para mejor rendimiento y mantenimiento.

```bash
# Instalar PostgreSQL 16
sudo dnf install -y postgresql-server postgresql-contrib

# Inicializar cluster
sudo postgresql-setup --initdb

# Arrancar y habilitar
sudo systemctl enable --now postgresql

# Crear usuario y base de datos
sudo -u postgres psql <<SQL
CREATE USER vpv WITH PASSWORD '<STRONG_PASSWORD>';
CREATE DATABASE ligavpv OWNER vpv ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8';
GRANT ALL PRIVILEGES ON DATABASE ligavpv TO vpv;
SQL
```

### Configurar autenticacion

Editar `/var/lib/pgsql/data/pg_hba.conf` — cambiar `ident` por `scram-sha-256` para conexiones locales:

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     scram-sha-256
host    all             all             127.0.0.1/32            scram-sha-256
```

```bash
sudo systemctl restart postgresql
```

### Verificar conexion

```bash
psql -U vpv -d ligavpv -c "SELECT version();"
```

## 4. Migracion MySQL a PostgreSQL

### 4.1. Preparar entorno de migracion

La migracion se ejecuta desde una maquina con acceso tanto a MySQL (origen) como a PostgreSQL (destino). Puede ser el propio servidor o una maquina de desarrollo.

```bash
cd migration

# Crear entorno virtual para la migracion
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configurar conexiones
cp .env.example .env
```

Editar `migration/.env`:

```ini
# MySQL origen (la BD actual en produccion)
MYSQL_HOST=<IP_SERVIDOR_MYSQL>
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=<PASSWORD_MYSQL>
MYSQL_DATABASE=ligavpv

# PostgreSQL destino
PG_HOST=localhost
PG_PORT=5432
PG_USER=vpv
PG_PASSWORD=<STRONG_PASSWORD>
PG_DATABASE=ligavpv
```

### 4.2. Opcion A: Migracion desde MySQL en vivo

Si MySQL sigue corriendo en el servidor actual:

```bash
cd migration/scripts

# Dry-run primero (no persiste nada)
python migrate.py --dry-run

# Migracion real
python migrate.py
```

El orquestador ejecuta 13 pasos en orden:
1. `00_create_schema.sql` — Crea las 20 tablas PostgreSQL
2. `01_seed_data.sql` — Datos fijos (formaciones validas)
3. Seasons — Migra temporadas
4. Users + Participants — Migra usuarios (deduplica por temporada)
5. Scoring + Payments — Genera reglas de puntuacion y pagos
6. Teams — Migra equipos vinculados a temporada
7. Matchdays + Matches — Migra jornadas y partidos (separados)
8. Players — Migra jugadores con FK a equipo y owner
9. Player Stats — Migra 224K+ estadisticas
10. Lineups — Migra alineaciones (normaliza de flag a 11 jugadores)
11. Scores — Calcula puntuaciones por participante/jornada
12. Validate — Verifica integridad referencial y conteos
13. Add indexes — Crea indices de rendimiento para queries del dashboard

Tiempo estimado: 5-10 minutos.

### 4.3. Opcion B: Migracion desde dump MySQL

Si MySQL ya no esta disponible, usar el dump incluido:

```bash
# Levantar MySQL temporal con Docker
cd migration
docker compose up -d mysql-source

# Esperar a que cargue el dump (~2 minutos)
docker compose logs -f mysql-source
# Cuando veas "ready for connections", continuar

# Ejecutar migracion (MySQL en localhost:3307, PG en localhost:5432)
cd scripts
python migrate.py
```

### 4.4. Verificacion post-migracion

```bash
psql -U vpv -d ligavpv <<SQL
SELECT 'seasons' AS tabla, count(*) FROM seasons
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'players', count(*) FROM players
UNION ALL SELECT 'player_stats', count(*) FROM player_stats
UNION ALL SELECT 'matches', count(*) FROM matches
UNION ALL SELECT 'matchdays', count(*) FROM matchdays
UNION ALL SELECT 'lineups', count(*) FROM lineups
UNION ALL SELECT 'transactions', count(*) FROM transactions
ORDER BY 1;
SQL
```

Valores esperados (a fecha de migracion):
- seasons: 8
- users: 15
- players: ~6,344
- player_stats: ~224,609
- matches: ~3,039
- matchdays: ~266
- lineups: variable
- transactions: variable

### 4.5. Configurar usuario administrador

La migracion no establece ningun usuario como admin. Asignar el rol manualmente:

```bash
# Ver usuarios disponibles
psql -U vpv -d ligavpv -c "SELECT id, username, display_name FROM users;"

# Marcar como admin
psql -U vpv -d ligavpv -c "UPDATE users SET is_admin = TRUE WHERE username = 'tu_username';"
```

Una vez configurado, puede gestionar otros usuarios desde `/admin/usuarios`.

### 4.6. Stamp de Alembic

Despues de la migracion, marcar la version de Alembic para que las migraciones futuras funcionen:

```bash
cd /opt/vpv/backend
source .venv/bin/activate
alembic stamp head
```

## 5. Backend (FastAPI)

### 5.1. Crear usuario del sistema

```bash
sudo useradd -r -m -d /opt/vpv -s /bin/bash vpv
sudo mkdir -p /opt/vpv/{backend,frontend,backups}
sudo mkdir -p /var/log/vpv
sudo chown -R vpv:vpv /opt/vpv /var/log/vpv
```

### 5.2. Clonar repositorio

```bash
sudo -u vpv git clone <REPO_URL> /opt/vpv/repo
```

### 5.3. Instalar backend

```bash
cd /opt/vpv/repo/backend

# Crear entorno virtual
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
```

### 5.4. Configurar variables de entorno

```bash
cp /opt/vpv/repo/.env.production.example /opt/vpv/backend/.env
```

Editar `/opt/vpv/backend/.env` con valores reales:

```ini
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://vpv:<STRONG_PASSWORD>@localhost:5432/ligavpv
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Generar con: python3 -c "import secrets; print(secrets.token_urlsafe(64))"
JWT_SECRET_KEY=<TOKEN_GENERADO>
JWT_EXPIRE_MINUTES=480

CORS_ORIGINS=["https://ligavpv.com"]

INVITE_BASE_URL=https://ligavpv.com/registro
INVITE_EXPIRY_DAYS=7

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<BOT_TOKEN>
TELEGRAM_CHAT_ID=<CHAT_ID>

SCRAPING_BASE_URL=https://www.futbolfantasy.com
SCRAPING_SEASON_SLUG=laliga-25-26
SCRAPING_POLL_INTERVAL_SECONDS=900
```

### 5.5. Ejecutar migraciones Alembic

```bash
cd /opt/vpv/repo/backend
source .venv/bin/activate
export DATABASE_URL=postgresql+asyncpg://vpv:<STRONG_PASSWORD>@localhost:5432/ligavpv
alembic upgrade head
```

### 5.6. Symlink del backend

```bash
ln -s /opt/vpv/repo/backend/src /opt/vpv/backend/src
ln -s /opt/vpv/repo/backend/pyproject.toml /opt/vpv/backend/pyproject.toml
ln -s /opt/vpv/repo/backend/alembic.ini /opt/vpv/backend/alembic.ini
ln -s /opt/vpv/repo/backend/alembic /opt/vpv/backend/alembic
```

### 5.7. Verificar arranque manual

```bash
cd /opt/vpv/backend
source .venv/bin/activate
uvicorn src.app:app --host 127.0.0.1 --port 8000
# Ctrl+C para parar
```

```bash
curl -s http://localhost:8000/api/health
# Esperado: {"status":"healthy","database":true,"version":"0.1.0"}
```

## 6. Frontend (Next.js)

### 6.1. Build

```bash
cd /opt/vpv/repo/frontend
npm ci --production=false

# Variables para el build
export NEXT_PUBLIC_API_URL=https://ligavpv.com/api
npm run build
```

### 6.2. Copiar standalone output

```bash
rm -rf /opt/vpv/frontend
cp -r .next/standalone /opt/vpv/frontend
cp -r .next/static /opt/vpv/frontend/.next/static
cp -r public /opt/vpv/frontend/public 2>/dev/null || true
```

### 6.3. Verificar arranque manual

```bash
cd /opt/vpv/frontend
PORT=3000 HOSTNAME=127.0.0.1 node server.js
# Ctrl+C para parar
```

## 7. Nginx + SSL

### 7.1. Copiar configuracion

```bash
sudo cp /opt/vpv/repo/deploy/nginx/ligavpv.conf /etc/nginx/conf.d/
sudo nginx -t
sudo systemctl enable --now nginx
```

### 7.2. Obtener certificado SSL

```bash
sudo certbot --nginx -d ligavpv.com -d www.ligavpv.com
```

Certbot configura la renovacion automatica. Verificar:

```bash
sudo certbot renew --dry-run
```

### 7.3. Firewall

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 8. Systemd + PM2

### 8.1. Backend (systemd)

```bash
sudo cp /opt/vpv/repo/deploy/systemd/vpv-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vpv-backend

# Verificar
sudo systemctl status vpv-backend
sudo journalctl -u vpv-backend -f
```

### 8.2. Frontend (PM2)

```bash
sudo -u vpv pm2 start /opt/vpv/repo/deploy/pm2/ecosystem.config.js
sudo -u vpv pm2 save
sudo -u vpv pm2 startup systemd -u vpv --hp /opt/vpv
# Ejecutar el comando sudo que pm2 muestra

# Verificar
sudo -u vpv pm2 status
sudo -u vpv pm2 logs vpv-frontend
```

## 9. Fotos de jugadores

Las fotos se almacenan en `/opt/vpv/backend/static/players/` como archivos WebP 200x200.

### 9.1. Copiar fotos existentes

Si tienes fotos del sistema anterior:

```bash
mkdir -p /opt/vpv/backend/static/players
# Copiar desde la fuente anterior
cp /ruta/fotos/*.webp /opt/vpv/backend/static/players/
chown -R vpv:vpv /opt/vpv/backend/static
```

### 9.2. Descargar fotos via scraping

```bash
cd /opt/vpv/repo/backend
source .venv/bin/activate
python -m src.features.scraping.cli download-photos 8  # season_id=8
```

### 9.3. Poblar photo_path en la BD

Despues de tener las fotos en disco, actualizar la BD:

```bash
# Generar SQLs de update
ls /opt/vpv/backend/static/players/ | sed 's/\.webp$//' | \
  awk '{print "UPDATE players SET photo_path = '\''players/" $0 ".webp'\'' WHERE slug = '\''" $0 "'\'';" }' \
  > /tmp/update_photos.sql

# Aplicar
psql -U vpv -d ligavpv -f /tmp/update_photos.sql
rm /tmp/update_photos.sql

# Verificar
psql -U vpv -d ligavpv -c "SELECT count(*) FROM players WHERE photo_path IS NOT NULL;"
```

### 9.4. Servir fotos con Nginx

El `ligavpv.conf` ya incluye la ruta `/static/` que hace proxy al backend.
Las fotos se sirven con cache de 30 dias (`expires 30d; Cache-Control: public, immutable`).

## 10. Backups y cron

### 10.1. Backup automatico de la BD

```bash
# Copiar script
sudo cp /opt/vpv/repo/deploy/scripts/backup_db.sh /opt/vpv/
sudo chmod +x /opt/vpv/backup_db.sh
sudo chown vpv:vpv /opt/vpv/backup_db.sh

# Cron: backup diario a las 3:00 AM
sudo -u vpv crontab -e
# Anadir:
# 0 3 * * * /opt/vpv/backup_db.sh >> /var/log/vpv/backup.log 2>&1
```

Los backups se guardan en `/opt/vpv/backups/` con retencion de 30 dias.

### 10.2. Logrotate

```bash
sudo cp /opt/vpv/repo/deploy/logrotate/vpv /etc/logrotate.d/vpv
```

### 10.3. Renovacion SSL (automatica con certbot)

Certbot instala un timer de systemd. Verificar:

```bash
sudo systemctl list-timers | grep certbot
```

## 11. Verificacion final

Ejecutar estas comprobaciones despues del despliegue:

```bash
# 1. Health check del API
curl -s https://ligavpv.com/api/health
# Esperado: {"status":"healthy","database":true,...}

# 2. Temporadas cargadas
curl -s https://ligavpv.com/api/seasons | python3 -m json.tool | head -10

# 3. Frontend accesible
curl -s -o /dev/null -w "%{http_code}" https://ligavpv.com
# Esperado: 200

# 4. Fotos accesibles
curl -s -o /dev/null -w "%{http_code}" https://ligavpv.com/static/players/dani-parejo.webp
# Esperado: 200

# 5. Servicios activos
sudo systemctl status vpv-backend
sudo -u vpv pm2 status
sudo systemctl status postgresql
sudo systemctl status nginx

# 6. SSL valido
curl -vI https://ligavpv.com 2>&1 | grep "SSL certificate"
```

## 12. Actualizaciones posteriores

Para desplegar nuevas versiones:

```bash
cd /opt/vpv/repo
./deploy/scripts/deploy.sh
```

El script hace:
1. `git pull --ff-only`
2. Backend: instala deps + `alembic upgrade head` + restart systemd
3. Frontend: `npm ci` + `npm run build` + copia standalone + restart PM2
4. Health check automatico

## 13. Rollback

### Rollback de codigo

```bash
cd /opt/vpv/repo
git log --oneline -5          # ver commits recientes
git checkout <commit_hash>    # volver a version anterior
./deploy/scripts/deploy.sh    # redesplegar
```

### Rollback de BD

```bash
# Listar backups disponibles
ls -lht /opt/vpv/backups/

# Restaurar
/opt/vpv/deploy/scripts/restore_db.sh /opt/vpv/backups/ligavpv_YYYYMMDD_HHMMSS.dump
```

### Rollback de migracion Alembic

```bash
cd /opt/vpv/backend
source .venv/bin/activate
alembic downgrade -1          # revertir ultima migracion
sudo systemctl restart vpv-backend
```

## 14. Desarrollo local (Docker)

Para desarrollo local se usa Docker Compose con 3 servicios (PostgreSQL, backend, frontend).

### 14.1. Requisitos

- Docker Engine + Docker Compose plugin
- En WSL2/AlmaLinux: `sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo && sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin`

### 14.2. Setup

```bash
git clone <REPO_URL> && cd vpv_ai

# Copiar env files
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# Arrancar
docker compose up --build -d
```

### 14.3. Notas importantes

- **Primer arranque**: El seed de la BD (~274K inserts) tarda ~6 minutos. PostgreSQL no acepta conexiones TCP hasta que termina. Si el backend falla al conectar, esperar y reiniciar: `docker restart vpv-backend`
- **Fotos de jugadores**: El campo `photo_path` no viene en el seed. Despues del primer arranque, poblar con el script de la seccion 9.3.
- **Puertos**: Frontend en `localhost:3000`, API en `localhost:8001`, PostgreSQL en `localhost:5433`
- **Hot reload**: Los volumenes montan `src/` del backend y frontend para desarrollo con recarga automatica.

### 14.4. Comandos utiles

```bash
docker compose up -d              # arrancar
docker compose down               # parar
docker compose down -v            # parar + borrar datos BD
docker compose logs -f backend    # ver logs backend
docker restart vpv-backend        # reiniciar solo backend

# Acceder a la BD
docker exec -it vpv-db psql -U vpv -d ligavpv

# Ejecutar tests backend
docker exec vpv-backend pytest

# Scraping CLI
docker exec vpv-backend python -m src.features.scraping.cli scrape-current
```

---

## Resumen de rutas en produccion

| Recurso | Ruta |
|---------|------|
| Repositorio | `/opt/vpv/repo` |
| Backend (app) | `/opt/vpv/backend` |
| Backend (venv) | `/opt/vpv/backend/.venv` |
| Backend (env) | `/opt/vpv/backend/.env` |
| Backend (static) | `/opt/vpv/backend/static/players/` |
| Frontend (standalone) | `/opt/vpv/frontend` |
| Logs | `/var/log/vpv/` |
| Backups BD | `/opt/vpv/backups/` |
| Nginx config | `/etc/nginx/conf.d/ligavpv.conf` |
| Systemd backend | `/etc/systemd/system/vpv-backend.service` |
| PM2 config | `/opt/vpv/repo/deploy/pm2/ecosystem.config.js` |
| Logrotate | `/etc/logrotate.d/vpv` |

## Resumen de puertos

| Servicio | Puerto | Acceso |
|----------|--------|--------|
| Nginx (HTTP) | 80 | Publico (redirect a 443) |
| Nginx (HTTPS) | 443 | Publico |
| FastAPI | 8000 | Solo localhost (via Nginx) |
| Next.js | 3000 | Solo localhost (via Nginx) |
| PostgreSQL | 5432 | Solo localhost |
