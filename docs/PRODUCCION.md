# Guía Completa de Producción — Liga VPV Fantasy en AlmaLinux 10

**Última actualización:** 2026-03-08

Esta guía te lleva paso a paso desde un servidor dedicado AlmaLinux 10 desnudo hasta tener la aplicación Liga VPV (ligavpv.com) completamente operativa en producción. Está diseñada para alguien con conocimientos básicos de Linux.

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Instalación de AlmaLinux 10](#2-instalación-de-almalinux-10)
3. [Configuración inicial del sistema](#3-configuración-inicial-del-sistema)
4. [Seguridad del sistema](#4-seguridad-del-sistema)
5. [Usuarios y estructura de directorios](#5-usuarios-y-estructura-de-directorios)
6. [PostgreSQL 16](#6-postgresql-16)
7. [Python 3.12](#7-python-312)
8. [Node.js 20 LTS y PM2](#8-nodejs-20-lts-y-pm2)
9. [Nginx](#9-nginx)
10. [SSL con Let's Encrypt](#10-ssl-con-lets-encrypt)
11. [Clonar repositorio y estructura](#11-clonar-repositorio-y-estructura)
12. [Backend: FastAPI + uvicorn](#12-backend-fastapi--uvicorn)
13. [Frontend: Next.js standalone](#13-frontend-nextjs-standalone)
14. [Servicios: systemd + PM2](#14-servicios-systemd--pm2)
15. [Migración de datos desde MySQL](#15-migración-de-datos-desde-mysql)
16. [Fotos de jugadores](#16-fotos-de-jugadores)
17. [Backups automatizados](#17-backups-automatizados)
18. [Monitorización y alertas](#18-monitorización-y-alertas)
19. [Verificación final](#19-verificación-final)
20. [Mantenimiento continuo](#20-mantenimiento-continuo)
21. [Troubleshooting](#21-troubleshooting)
22. [Rollback](#22-rollback)

---

## 1. Requisitos previos

### Hardware

- **CPU:** 2+ cores (recomendado 4)
- **RAM:** Mínimo 2 GB (recomendado 4 GB para dev con PostgreSQL)
- **Disco:** 20 GB libres (`/` 10GB, `/var` 5GB, `/opt` 5GB)
- **Conexión:** Estable, ancho de banda mínimo 10 Mbps

### Dominio

- **Dominio:** ligavpv.com apuntando via DNS A record a la IP del servidor
- **DNS:** Verificar que resuelve correctamente:

```bash
nslookup ligavpv.com
# Esperado: la IP del servidor dedicado
```

### Puertos públicos

- **80 (HTTP):** Para solicitudes y renovación SSL de certbot
- **443 (HTTPS):** Tráfico HTTPS (todo el tráfico de producción)
- **SSH (22):** Acceso administrativo (cambiar a puerto no estándar en sección 4)

### Hosting

Este servidor es **dedicado** (no cloud). Esto significa:
- Sin auto-scaling: solo escalas si actualizas el servidor
- Reinicio manual si falla el hardware
- Responsabilidad total de backups y disaster recovery
- IP estática garantizada

---

## 2. Instalación de AlmaLinux 10

### 2.1. Descargar ISO

Descargar AlmaLinux 10 desde [almalinux.org](https://almalinux.org/):

```bash
# Desde tu máquina local, descarga la ISO mínima:
# https://repo.almalinux.org/almalinux/10/isos/x86_64/AlmaLinux-10-latest-x86_64-minimal.iso
# (2-3 GB)
```

### 2.2. Crear medio de instalación

Con USB o vía IPMI (si tu proveedor lo ofrece):

```bash
# En macOS/Linux, con USB insertado:
diskutil list
sudo dd if=AlmaLinux-10-latest-x86_64-minimal.iso of=/dev/rdiskX bs=4m
sudo diskutil eject /dev/diskX
```

### 2.3. Arranque e instalación

1. Reinicia el servidor y arranca desde USB/IPMI
2. Selecciona **"Install AlmaLinux 10"**
3. En la pantalla de instalación:
   - **Idioma:** English (o tu preferencia)
   - **Keyboard layout:** Spanish (si aplica)
   - **Time & Date:** Cambiar a **Europe/Madrid** (importante para logs)

### 2.4. Particionado

**IMPORTANTE:** Un buen particionado evita que un servicio llene el disco y tumbe otros.

En la sección **Storage Configuration** → **Automatic partitioning** → Custom:

```
/              → 10 GB (sistema + aplicación)
/var           → 5 GB (logs, datos temporales)
/opt           → 5 GB (aplicación VPV)
/home          → 1 GB (usuarios)
swap           → 2 GB (intercambio)
```

Si el instalador no lo permite, aceptar el default y después reajustar manualmente (véase sección 3).

### 2.5. Perfil de instalación

Selecciona **"Minimal Install"** (sin GUI, servidor headless).

### 2.6. Configuración de red

En **Network & Hostname:**
- **Hostname:** `vpv-prod` (o similar)
- **Ethernet:** Activar automáticamente (DHCP o IP estática según proveedor)

### 2.7. Root password

Establece una contraseña fuerte para root. Después la deshabilitaremos (sección 4).

### 2.8. Finalizar instalación

Esperar ~5-10 minutos. El sistema reiniciará automáticamente.

---

## 3. Configuración inicial del sistema

### 3.1. Acceso inicial

```bash
# Conéctate vía SSH desde tu máquina local:
ssh root@<IP_SERVIDOR>
# Ingresa la contraseña de root que configuraste
```

### 3.2. Actualizar sistema

```bash
sudo dnf update -y
sudo dnf install -y wget curl git vim nano
```

### 3.3. Configurar hostname

```bash
sudo hostnamectl set-hostname vpv-prod
echo "127.0.0.1  vpv-prod" | sudo tee -a /etc/hosts
```

### 3.4. Timezone

```bash
sudo timedatectl set-timezone Europe/Madrid
timedatectl
# Verificar que aparece "Europe/Madrid"
```

### 3.5. Locale

```bash
sudo dnf install -y langpacks-es
sudo localectl set-locale LANG=es_ES.UTF-8
```

### 3.6. Verificar particiones

```bash
df -h
# Esperado:
#   /       → 10G (o similar)
#   /var    → 5G
#   /opt    → 5G
```

Si el particionado es diferente y necesitas ajustar, consulta un especialista en LVM antes de continuar.

### 3.7. Actualización automática de seguridad

```bash
sudo dnf install -y dnf-automatic

# Editar configuración
sudo nano /etc/dnf/automatic.conf

# Cambiar estas líneas:
# apply_updates = yes      (aplicar actualizaciones automáticamente)
# emit_via = motd           (notificar vía motd)

# Habilitar y arrancar
sudo systemctl enable --now dnf-automatic.timer
sudo systemctl status dnf-automatic.timer
```

---

## 4. Seguridad del sistema

**IMPORTANTE:** Dedica tiempo a esta sección. Un servidor comprometido pierde todo.

### 4.1. SSH hardening

**IMPORTANTE:** Sigue estos pasos EN ORDEN. Si desactivas password antes de configurar la clave SSH, perderas acceso al servidor.

#### Paso 1: Crear usuario administrador (si solo tienes root)

```bash
useradd -m -s /bin/bash admin
passwd admin    # Pon una contraseña fuerte
usermod -aG wheel admin    # Grupo sudo en RHEL/AlmaLinux
```

#### Paso 2: Copiar tu clave publica SSH al servidor

Desde tu maquina local:

```bash
# Si no tienes clave SSH, crearla primero:
# ssh-keygen -t ed25519

# Copiar al servidor (aun con password):
ssh-copy-id admin@<IP_SERVIDOR>

# Verificar que puedes conectar sin password:
ssh admin@<IP_SERVIDOR>
```

#### Paso 3: Hardening de sshd_config

Una vez que confirmes que puedes conectar con clave SSH:

```bash
sudo nano /etc/ssh/sshd_config

# Cambiar estas lineas:
Port 2222                      # Puerto no estandar
PermitRootLogin no             # Prohibir login root
PasswordAuthentication no      # Solo claves SSH
PubkeyAuthentication yes       # Habilitar claves
```

#### Paso 4: Aplicar cambios SSH

```bash
sudo sshd -t      # Verificar sintaxis — NO reiniciar si hay error
sudo systemctl restart sshd
```

**ANTES de cerrar la sesion, abre OTRA terminal y verifica que el SSH sigue funcionando:**

```bash
# Desde tu maquina local:
ssh -p 2222 admin@<IP_SERVIDOR>
# Debe conectar sin pedir password. Si falla, revierte los cambios en la terminal actual.
```

### 4.2. Firewall (firewalld)

```bash
# Verificar estado
sudo systemctl status firewalld

# Si no está habilitado:
sudo systemctl enable --now firewalld

# Abrir puertos públicos
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=2222/tcp    # SSH (si cambiaste puerto)

# Deshabilitar SSH en puerto 22 (opcional)
sudo firewall-cmd --permanent --remove-service=ssh

# Aplicar cambios
sudo firewall-cmd --reload

# Verificar
sudo firewall-cmd --list-all
```

### 4.3. SELinux en modo enforcing

SELinux anade una capa de seguridad basada en permisos granulares. **Liga VPV lo usa**.

```bash
# Instalar herramientas SELinux (necesarias para setsebool, semanage, restorecon)
sudo dnf install -y policycoreutils-python-utils
```

```bash
# Verificar estado actual
getenforce
# Esperado: Enforcing (si no, continúa)

# Si está en Permissive o Disabled:
sudo nano /etc/selinux/config

# Cambiar:
SELINUX=enforcing
SELINUXTYPE=targeted

# Reiniciar para aplicar
sudo reboot
```

Después del reinicio, conecta y verifica:

```bash
sudo getenforce
# Debe decir: Enforcing
```

### 4.4. fail2ban

Protege contra ataques de fuerza bruta en SSH.

```bash
sudo dnf install -y fail2ban

# Configurar para SSH
sudo nano /etc/fail2ban/jail.local

# Añadir:
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = 2222
```

```bash
sudo systemctl enable --now fail2ban
sudo systemctl status fail2ban
```

Verificar que fail2ban monitorea SSH:

```bash
sudo fail2ban-client status sshd
```

---

## 5. Usuarios y estructura de directorios

### 5.1. Crear usuario vpv

```bash
# Usuario del sistema para la aplicación (sin login interactivo)
sudo useradd -r -m -d /opt/vpv -s /bin/bash vpv

# Verificar
id vpv
# Esperado: uid=XXX(vpv) gid=XXX(vpv) grupos=XXX(vpv)
```

### 5.2. Estructura de directorios

```bash
# Crear estructura
sudo mkdir -p /opt/vpv/{repo,backend,frontend,backups}
sudo mkdir -p /var/log/vpv

# Establecer propietario
sudo chown -R vpv:vpv /opt/vpv /var/log/vpv

# Permisos
sudo chmod 750 /opt/vpv
sudo chmod 755 /opt/vpv/backups

# Verificar
ls -la /opt/vpv
ls -la /var/log/vpv
```

### 5.3. Sudo para el usuario vpv

El usuario `vpv` necesita ejecutar algunos comandos con `sudo` sin contraseña (para systemd restart, etc).

```bash
# Crear sudoers file específico
sudo visudo -f /etc/sudoers.d/vpv

# Añadir estas líneas:
vpv ALL = (ALL) NOPASSWD: /usr/bin/systemctl restart vpv-backend, /usr/bin/systemctl stop vpv-backend, /usr/bin/systemctl start vpv-backend, /usr/bin/journalctl
vpv ALL = NOPASSWD: /usr/bin/pm2 restart *, /usr/bin/pm2 start *, /usr/bin/pm2 status, /usr/bin/pm2 stop

# Verificar sintaxis (importante)
sudo visudo -c
# Esperado: "parse successful"
```

---

## 6. PostgreSQL 16

### 6.1. Instalar PostgreSQL

```bash
# PostgreSQL desde AppStream
sudo dnf install -y postgresql-server postgresql-contrib

# Inicializar cluster de base de datos
sudo postgresql-setup --initdb
# Crea `/var/lib/pgsql/data/` y archivos de configuración

# Arrancar y habilitar
sudo systemctl enable --now postgresql

# Verificar
sudo systemctl status postgresql
```

### 6.2. Configurar autenticación SCRAM-SHA-256

La autenticación por defecto (`ident`) no funciona bien en producción. Cambiar a SCRAM-SHA-256.

```bash
# Editar pg_hba.conf
sudo nano /var/lib/pgsql/data/pg_hba.conf

# Buscar las líneas que comiencen con "local" y "host", y cambiar el METHOD:
# Reemplazar:
#   local   all             all                                     ident
#   host    all             all             127.0.0.1/32            ident
#   host    all             all             ::1/128                 ident
# Por:
#   local   all             all                                     scram-sha-256
#   host    all             all             127.0.0.1/32            scram-sha-256
#   host    all             all             ::1/128                 scram-sha-256

# Guardar y reiniciar
sudo systemctl restart postgresql
```

### 6.3. Tuning de PostgreSQL para 2-4 GB RAM

```bash
sudo nano /var/lib/pgsql/data/postgresql.conf

# Buscar y cambiar estos valores (descomentando si es necesario):
# Para 2 GB RAM:
shared_buffers = 512MB          # 25% de RAM
effective_cache_size = 1500MB   # 75% de RAM
work_mem = 32MB                 # shared_buffers / max_connections
maintenance_work_mem = 128MB

# Para 4 GB RAM:
shared_buffers = 1024MB
effective_cache_size = 3072MB
work_mem = 64MB
maintenance_work_mem = 256MB

# Otros valores útiles:
max_connections = 100
log_min_duration_statement = 1000  # Log queries > 1 segundo
log_lock_waits = on
```

Reiniciar:

```bash
sudo systemctl restart postgresql
```

### 6.4. Crear usuario y base de datos

```bash
sudo -u postgres psql <<'EOF'
-- Crear usuario con contraseña fuerte
CREATE USER vpv WITH PASSWORD 'CAMBIA_ESTO_POR_CONTRASEÑA_FUERTE_64_CARACTERES';

-- Crear base de datos
CREATE DATABASE ligavpv OWNER vpv ENCODING 'UTF8'
    LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8';

-- Permisos
GRANT ALL PRIVILEGES ON DATABASE ligavpv TO vpv;
ALTER DATABASE ligavpv OWNER TO vpv;
EOF
```

**Guarda la contraseña de PostgreSQL en un lugar seguro.** La necesitarás en la sección de variables de entorno.

### 6.5. Verificar conexión

```bash
# Como usuario vpv
sudo -u vpv psql -h 127.0.0.1 -d ligavpv -c "SELECT version();"

# Esperado:
# PostgreSQL 16.X on x86_64-pc-linux-gnu...
```

Si falla, verifica:

```bash
sudo -u postgres psql -c "SELECT * FROM pg_user WHERE usename='vpv';"
```

---

## 7. Python 3.12

### 7.1. Instalar Python 3.12

AlmaLinux 10 trae Python en AppStream:

```bash
sudo dnf install -y python3.12 python3.12-pip python3.12-devel

# Verificar
python3.12 --version
pip3.12 --version
```

### 7.2. Instalar herramientas de build

Necesarias para compilar dependencias Python con extensiones C:

```bash
sudo dnf install -y gcc gcc-c++ libpq-devel openssl-devel
```

---

## 8. Node.js 20 LTS y PM2

### 8.1. Instalar Node.js 20 LTS

```bash
# Habilitar módulo Node.js 20
sudo dnf module enable nodejs:20 -y

# Instalar
sudo dnf install -y nodejs npm

# Verificar
node --version    # v20.x.x
npm --version     # 10.x.x
```

### 8.2. Instalar PM2 globalmente

PM2 gestiona el proceso Next.js en producción.

```bash
sudo npm install -g pm2

# Verificar
pm2 --version
```

---

## 9. Nginx

### 9.1. Instalar Nginx

```bash
sudo dnf install -y nginx

# Habilitar SELinux booleans para que Nginx pueda conectarse al backend
sudo setsebool -P httpd_can_network_connect on

# Arrancar
sudo systemctl enable --now nginx
sudo systemctl status nginx
```

### 9.2. Copiar configuración de Liga VPV

**IMPORTANTE:** Este paso requiere que hayas clonado el repo (sección 11). Si aun no lo has hecho, salta este paso y vuelve aqui despues de la seccion 11.

```bash
sudo cp /opt/vpv/repo/deploy/nginx/ligavpv.conf /etc/nginx/conf.d/

# Verificar sintaxis
sudo nginx -t
# Esperado: "successful"

# Recargar configuración (sin downtime)
sudo systemctl reload nginx
```

---

## 10. SSL con Let's Encrypt

### 10.1. Instalar Certbot

```bash
sudo dnf install -y certbot python3-certbot-nginx
```

### 10.2. Obtener certificado

```bash
sudo certbot --nginx -d ligavpv.com -d www.ligavpv.com

# Te pedirá email y aceptar términos. Acepta.
# Certbot automáticamente:
# 1. Obtiene el certificado
# 2. Configura Nginx para HTTPS
# 3. Instala un timer de systemd para renovación automática
```

### 10.3. Verificar renovación automática

```bash
# Listar timers de systemd
sudo systemctl list-timers | grep certbot

# Hacer prueba de renovación (sin renovar realmente)
sudo certbot renew --dry-run
# Esperado: "Cert not yet due for renewal"
```

### 10.4. Verificar certificado

```bash
# Ver detalles del certificado
sudo certbot certificates

# Acceder vía HTTPS
curl -s -I https://ligavpv.com | grep SSL
# Si no tienes acceso a DNS aún, usar -k para ignorar cert:
curl -sk -I https://ligavpv.com | grep SSL
```

### 10.5. Firewall (recordatorio)

Ya lo hicimos en la sección 4, pero verificar:

```bash
sudo firewall-cmd --list-all | grep 'services\|ports'
# Debe incluir: http https
```

---

## 11. Clonar repositorio y estructura

### 11.1. Clonar como usuario vpv

```bash
# Cambiar a usuario vpv
sudo -u vpv -s

# Dentro de la shell de vpv:
cd /opt/vpv
git clone https://github.com/tu_usuario/vpv_ai.git repo
# (Reemplaza con la URL real de tu repositorio)

# Verificar
ls -la /opt/vpv/repo
```

### 11.2. Crear symlinks de backend

El backend necesita acceso a fuentes, migrations (Alembic), y datos estáticos.

```bash
# Como usuario vpv, crear estructura
cd /opt/vpv/backend

# Symlinks al repositorio (para que ediciones en repo se reflejen)
ln -s /opt/vpv/repo/backend/src ./src
ln -s /opt/vpv/repo/backend/alembic ./alembic
ln -s /opt/vpv/repo/backend/alembic.ini ./alembic.ini
ln -s /opt/vpv/repo/backend/pyproject.toml ./pyproject.toml

# Directorio para fotos (será creado después)
mkdir -p /opt/vpv/backend/static/players

# Verificar
ls -la /opt/vpv/backend
# Debe mostrar symlinks
```

---

## 12. Backend: FastAPI + uvicorn

### 12.1. Crear virtual environment

```bash
# Como usuario vpv
cd /opt/vpv/backend

python3.12 -m venv .venv
source .venv/bin/activate

# Actualizar pip
pip install --upgrade pip setuptools wheel
```

### 12.2. Instalar dependencias

```bash
# Dentro de venv, desde /opt/vpv/backend (los symlinks apuntan al repo)
pip install .
# Esto instala todas las dependencias especificadas en pyproject.toml
```

Tiempo estimado: 2-5 minutos.

### 12.3. Crear archivo .env

```bash
# Salir de venv
deactivate

# Como usuario vpv, crear .env
nano /opt/vpv/backend/.env
```

Copiar este contenido y completar los valores:

```ini
# Entorno
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Base de datos
DATABASE_URL=postgresql+asyncpg://vpv:TU_CONTRASEÑA_PG@localhost:5432/ligavpv
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# JWT (generar con: python3 -c "import secrets; print(secrets.token_urlsafe(64))")
JWT_SECRET_KEY=CAMBIA_ESTO_GENERAR_UNO_ALEATORIO_64_CARACTERES
JWT_EXPIRE_MINUTES=480

# CORS
CORS_ORIGINS=["https://ligavpv.com","https://www.ligavpv.com"]

# Invitaciones
INVITE_BASE_URL=https://ligavpv.com/registro
INVITE_EXPIRY_DAYS=7

# Telegram (llenar si usas notificaciones)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=TU_BOT_TOKEN_AQUI
TELEGRAM_CHAT_ID=TU_CHAT_ID_AQUI

# Scraping
SCRAPING_BASE_URL=https://www.futbolfantasy.com
SCRAPING_SEASON_SLUG=laliga-25-26
SCRAPING_POLL_INTERVAL_SECONDS=900
```

**Generar JWT_SECRET_KEY:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
# Copia el resultado y reemplázalo en .env
```

**Permisos:**

```bash
# Solo vpv puede leer el archivo (contiene contraseñas)
chmod 600 /opt/vpv/backend/.env
```

### 12.4. Ejecutar migraciones Alembic

```bash
# Como usuario vpv
cd /opt/vpv/backend
source .venv/bin/activate

# Stamp: marcar que ya tenemos las migraciones iniciales
alembic stamp head

# Upgrade: aplicar nuevas migraciones (si las hay)
alembic upgrade head

# Deactivate venv
deactivate
```

### 12.5. Verificar arranque manual

```bash
# Como usuario vpv
cd /opt/vpv/backend
source .venv/bin/activate

# Arrancar uvicorn (el servidor ASGI)
uvicorn src.app:app --host 127.0.0.1 --port 8000 --log-level info
```

El servidor debe mostrar:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

En otra terminal, verificar:

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
# Esperado: {"status":"healthy","database":true,...}
```

Si hay error de conexión a BD, verifica el .env y la contraseña PostgreSQL.

Ctrl+C para detener uvicorn.

---

## 13. Frontend: Next.js standalone

### 13.1. Instalar dependencias

```bash
# Como usuario vpv, ir al repo
cd /opt/vpv/repo/frontend

# Instalar todas las dependencias (incluidas devDependencies para build)
npm ci --production=false
```

Tiempo estimado: 3-5 minutos.

### 13.2. Crear archivo .env.production

Next.js necesita variables de entorno en build-time:

```bash
nano /opt/vpv/repo/frontend/.env.production
```

Contenido:

```ini
NEXT_PUBLIC_API_URL=https://ligavpv.com/api
NEXTAUTH_URL=https://ligavpv.com
API_INTERNAL_URL=http://127.0.0.1:8000/api
```

### 13.3. Build de Next.js

```bash
cd /opt/vpv/repo/frontend

# Variables de entorno
export NEXT_PUBLIC_API_URL=https://ligavpv.com/api

# Build (output: .next/standalone)
npm run build
# Tiempo estimado: 3-5 minutos

# Verificar output
ls -la .next/standalone/
```

### 13.4. Copiar a /opt/vpv/frontend

```bash
# Como usuario vpv (o root)
cd /opt/vpv/repo/frontend

# Limpiar destino anterior
rm -rf /opt/vpv/frontend

# Copiar standalone output
cp -r .next/standalone /opt/vpv/frontend

# Copiar static assets
cp -r .next/static /opt/vpv/frontend/.next/static

# Copiar public si existe
cp -r public /opt/vpv/frontend/public 2>/dev/null || true

# Ajustar permisos
sudo chown -R vpv:vpv /opt/vpv/frontend
```

### 13.5. Configurar NEXTAUTH_SECRET en PM2

Next.js standalone no lee archivos `.env` en runtime — las variables las inyecta PM2 via `ecosystem.config.js`.

```bash
nano /opt/vpv/ecosystem.config.js
```

Anadir `NEXTAUTH_SECRET` dentro de la seccion `env`:

```javascript
env: {
  // ... otras variables existentes ...
  NEXTAUTH_SECRET: "TU_SECRET_AQUI",
},
```

Generar el secret:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
# Copia el resultado y pegalo en ecosystem.config.js
```

**IMPORTANTE:** El archivo `ecosystem.config.js` contiene secrets. Protegerlo:

```bash
chmod 600 /opt/vpv/ecosystem.config.js
```

### 13.6. Verificar arranque manual

```bash
# Como usuario vpv
cd /opt/vpv/frontend

export NODE_ENV=production
export PORT=3000
export HOSTNAME=127.0.0.1
export NEXT_PUBLIC_API_URL=https://ligavpv.com/api
export NEXTAUTH_URL=https://ligavpv.com

node server.js
```

El servidor debe mostrar:

```
> ready - started server on 0.0.0.0:3000, url: http://127.0.0.1:3000
```

En otra terminal:

```bash
curl -s http://127.0.0.1:3000/ | head -20
# Debe devolver HTML del frontend
```

Ctrl+C para detener.

---

## 14. Servicios: systemd + PM2

### 14.1. Backend con systemd

#### Copiar unit file

```bash
sudo cp /opt/vpv/repo/deploy/systemd/vpv-backend.service /etc/systemd/system/
```

#### Editar si es necesario

```bash
sudo nano /etc/systemd/system/vpv-backend.service

# Verificar/cambiar:
# User=vpv
# WorkingDirectory=/opt/vpv/backend
# EnvironmentFile=/opt/vpv/backend/.env
# ExecStart=/opt/vpv/backend/.venv/bin/uvicorn src.app:app \
#     --host 127.0.0.1 \
#     --port 8000 \
#     --workers 4 \
#     --log-level info
```

#### Habilitar y arrancar

```bash
sudo systemctl daemon-reload
sudo systemctl enable vpv-backend
sudo systemctl start vpv-backend

# Verificar
sudo systemctl status vpv-backend
# Esperado: "active (running)"

# Ver logs
sudo journalctl -u vpv-backend -f --no-pager -n 20
```

Si falla, verifica:
- El .env existe y tiene permisos
- La BD PostgreSQL está accesible
- Las migraciones Alembic corrieron exitosamente

### 14.2. Frontend con PM2

#### Copiar ecosystem config

```bash
# PM2 necesita este archivo para conocer cómo arrancar el app
cp /opt/vpv/repo/deploy/pm2/ecosystem.config.js /opt/vpv/
```

#### Editar si es necesario

```bash
nano /opt/vpv/ecosystem.config.js

# Verificar:
# cwd: "/opt/vpv/frontend"
# script: "server.js"
# PORT: 3000
# HOSTNAME: 127.0.0.1
```

#### Arrancar con PM2

```bash
# Como usuario vpv
cd /opt/vpv

# Arrancar la aplicación
pm2 start ecosystem.config.js

# Ver estado
pm2 status
# Esperado: vpv-frontend en estado "online"

# Ver logs en tiempo real
pm2 logs vpv-frontend

# Guardar configuración de PM2 para reinicio automático
pm2 save

# Habilitar startup en boot
pm2 startup systemd -u vpv --hp /opt/vpv
# Esto imprime un comando sudo que DEBES ejecutar
# Cópialo y ejecuta:
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u vpv --hp /opt/vpv
```

Verificar que se inicia en boot:

```bash
sudo reboot
# Después de reiniciar, conectar y:
sudo -u vpv pm2 status
# vpv-frontend debe estar "online"
```

---

## 15. Migración de datos desde MySQL

**IMPORTANTE:** Este paso migra los datos históricos de la base de datos MySQL anterior a PostgreSQL.

### 15.1. Prerequisitos

- Acceso a la base de datos MySQL actual (servidor MySQL origen)
- O un dump MySQL disponible

### 15.2. Migración desde MySQL en vivo

Si la BD MySQL sigue activa:

```bash
# En el servidor de producción, ir a migration
cd /opt/vpv/repo/migration

# Crear venv para la migración
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configurar .env con credenciales reales
cp .env.example .env
nano .env
# Rellenar: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, PG_PASSWORD
```

```bash
# Dry-run primero (rollback automático, no persiste nada)
cd /opt/vpv/repo/migration/scripts
python migrate.py --dry-run

# Si el dry-run es exitoso, ejecutar migración real
python migrate.py

# Esperado: "Migration complete!" con 13 pasos (00-12)
```

El migrador ejecuta estos pasos en orden:
- 00: Crear schema (20 tablas)
- 01: Seed data (formaciones válidas)
- 02-10: Migrar datos desde MySQL (seasons, users, scoring, teams, matchdays, players, stats, lineups, scores)
- 11: Validación de integridad
- 12: Crear índices de rendimiento

Para reanudar desde un paso específico: `python migrate.py --step N`

### 15.3. Migración desde dump MySQL

Si no tienes acceso directo a MySQL, usar el dump con Docker:

```bash
# Instalar Docker (solo si necesitas esta opcion)
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker

# Levantar MySQL temporal con el dump
cd /opt/vpv/repo/migration
docker compose up -d mysql-source

# Esperar ~2 minutos a que cargue el dump
docker compose logs mysql-source | grep "ready for connections"

# Luego ejecutar migración (MySQL en localhost:3307)
cd scripts
python migrate.py
```

### 15.4. Verificar migración

```bash
# Como usuario vpv, conectar a PostgreSQL
psql -h 127.0.0.1 -U vpv -d ligavpv <<'EOF'
SELECT 'seasons' AS tabla, count(*) FROM seasons
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'players', count(*) FROM players
UNION ALL SELECT 'player_stats', count(*) FROM player_stats
UNION ALL SELECT 'matches', count(*) FROM matches
UNION ALL SELECT 'matchdays', count(*) FROM matchdays
UNION ALL SELECT 'lineups', count(*) FROM lineups
ORDER BY 1;
EOF
```

Valores esperados (según data histórica):
- seasons: 8
- users: 15
- players: 6000+
- player_stats: 200000+
- matches: 3000+
- matchdays: 250+
- lineups: variable

Si los números son muy bajos o cero, verifica:
- El .env de migration tiene credenciales correctas
- MySQL está accesible
- No hay errores en los logs de la migración

---

## 16. Fotos de jugadores

Las fotos se sirven desde `/opt/vpv/backend/static/players/` como archivos WebP 200x200px.

### 16.1. Crear directorio

```bash
mkdir -p /opt/vpv/backend/static/players
sudo chown -R vpv:vpv /opt/vpv/backend/static
sudo chmod 755 /opt/vpv/backend/static
sudo chmod 755 /opt/vpv/backend/static/players
```

### 16.2. Opción A: Copiar fotos existentes

Si tienes las fotos de un sistema anterior:

```bash
# Copiar
cp /ruta/anterior/fotos/*.webp /opt/vpv/backend/static/players/

# Ajustar permisos
sudo chown vpv:vpv /opt/vpv/backend/static/players/*
sudo chmod 644 /opt/vpv/backend/static/players/*
```

### 16.3. Opción B: Descargar via scraping

```bash
# Como usuario vpv
cd /opt/vpv/backend
source .venv/bin/activate

# Descargar fotos de la temporada 8 (actual)
python -m src.features.scraping.cli download-photos 8

# Salir de venv
deactivate
```

Tiempo estimado: 5-10 minutos (depende del ancho de banda).

### 16.4. Poblar campo photo_path en la BD

Después de descargar/copiar las fotos, actualizar la base de datos:

```bash
# Como usuario vpv
cd /opt/vpv/backend

# Generar SQLs de update basados en archivos del disco
ls /opt/vpv/backend/static/players/ | sed 's/\.webp$//' | \
  awk '{print "UPDATE players SET photo_path = '"'"'players/" $0 ".webp'"'"' WHERE slug = '"'"'" $0 "'"'"';" }' \
  > /tmp/update_photos.sql

# Aplicar a la BD
psql -h 127.0.0.1 -U vpv -d ligavpv -f /tmp/update_photos.sql

# Limpiar
rm /tmp/update_photos.sql

# Verificar (debe mostrar un número > 0)
psql -h 127.0.0.1 -U vpv -d ligavpv -c "SELECT count(*) FROM players WHERE photo_path IS NOT NULL;"
```

### 16.5. Verificar acceso via HTTPS

```bash
# Desde el servidor, probar una foto
curl -s -o /dev/null -w "%{http_code}" https://ligavpv.com/static/players/dani-parejo.webp
# Esperado: 200

# O desde tu máquina local
curl -sk -o /dev/null -w "%{http_code}" https://ligavpv.com/static/players/dani-parejo.webp
```

---

## 17. Backups automatizados

### 17.1. Configurar .pgpass

**IMPORTANTE:** Sin `.pgpass`, `pg_dump` pedira password interactivamente y el cron de backup fallara silenciosamente.

```bash
# Como usuario vpv
nano /opt/vpv/.pgpass
```

Contenido (una linea):

```
localhost:5432:ligavpv:vpv:TU_CONTRASEÑA_PG
```

```bash
chmod 600 /opt/vpv/.pgpass
```

Verificar que funciona sin pedir password:

```bash
sudo -u vpv pg_dump -U vpv -d ligavpv -F c -f /dev/null
# No debe pedir password
```

### 17.2. Script de backup

```bash
# Copiar script
sudo cp /opt/vpv/repo/deploy/scripts/backup_db.sh /opt/vpv/
sudo chmod +x /opt/vpv/backup_db.sh
sudo chown vpv:vpv /opt/vpv/backup_db.sh
```

### 17.3. Cron diario

```bash
# Como usuario vpv, editar crontab
sudo -u vpv crontab -e

# Añadir esta línea:
0 3 * * * /opt/vpv/backup_db.sh >> /var/log/vpv/backup.log 2>&1
```

Esto hace un backup diario a las 3:00 AM. Los backups se guardan en `/opt/vpv/backups/` con retención de 30 días.

### 17.4. Verificar backup manual

```bash
# Como usuario vpv, ejecutar manualmente
/opt/vpv/backup_db.sh

# Ver el resultado
ls -lh /opt/vpv/backups/
# Debe haber un archivo ligavpv_YYYYMMDD_HHMMSS.dump reciente
```

### 17.5. Logrotate

```bash
# Copiar configuración
sudo cp /opt/vpv/repo/deploy/logrotate/vpv /etc/logrotate.d/vpv

# Verificar sintaxis
sudo logrotate -d /etc/logrotate.d/vpv
```

Logrotate rotará los logs diariamente, mantendiendo 14 archivos comprimidos.

---

## 18. Monitorización y alertas

### 18.1. Verificar servicios regularmente

```bash
# Ver estado de servicios
sudo systemctl status vpv-backend postgresql nginx
sudo -u vpv pm2 status

# Ver logs en tiempo real
sudo journalctl -u vpv-backend -f
sudo -u vpv pm2 logs vpv-frontend

# Ver logs pasados
sudo journalctl -u vpv-backend --since "1 hour ago" | tail -50
```

### 18.2. Monitorización de PostgreSQL

```bash
# Conectar como usuario vpv
psql -h 127.0.0.1 -U vpv -d ligavpv

# Ver conexiones activas
SELECT datname, usename, pid, state FROM pg_stat_activity;

# Ver índices no usados
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

# Ver tamaño de la BD
SELECT pg_size_pretty(pg_database_size('ligavpv'));

# VACUUM para limpiar espacio muerto (ejecutar regularmente)
VACUUM ANALYZE;
```

### 18.3. Monitorización de disco

```bash
# Ver espacio disponible
df -h
# Alerta si alguna partición está > 80% llena

# Ver tamaño de directorios
du -sh /opt/vpv/*
du -sh /var/log/vpv/*
```

### 18.4. Health check con Telegram

Crear un script que alerta si algún servicio está caído:

```bash
nano /opt/vpv/health_check.sh
```

Contenido:

```bash
#!/bin/bash
# Health check para Liga VPV
# Uso: crontab: 0 * * * * /opt/vpv/health_check.sh

# Leer tokens del .env del backend (evita duplicar secrets)
TELEGRAM_BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN /opt/vpv/backend/.env | cut -d= -f2)
TELEGRAM_CHAT_ID=$(grep TELEGRAM_CHAT_ID /opt/vpv/backend/.env | cut -d= -f2)

send_alert() {
    local msg="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${msg}"
}

# Verificar backend
if ! systemctl is-active --quiet vpv-backend; then
    send_alert "ALERTA: vpv-backend está caído!"
    systemctl restart vpv-backend
fi

# Verificar frontend
if ! sudo -u vpv pm2 status vpv-frontend | grep -q "online"; then
    send_alert "ALERTA: vpv-frontend está caído!"
    sudo -u vpv pm2 restart vpv-frontend
fi

# Verificar BD
if ! pg_isready -h 127.0.0.1 -U vpv -d ligavpv > /dev/null 2>&1; then
    send_alert "ALERTA: PostgreSQL está caído!"
    systemctl restart postgresql
fi

# Verificar espacio en disco
DISK_USAGE=$(df /opt | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    send_alert "ALERTA: /opt está al ${DISK_USAGE}% de capacidad!"
fi
```

```bash
chmod +x /opt/vpv/health_check.sh

# Agregar a crontab del usuario vpv
sudo -u vpv crontab -e
# Añadir: 0 * * * * /opt/vpv/health_check.sh
```

---

## 19. Verificación final

**Checklist completo antes de considerar la instalación exitosa:**

### 19.1. Base de datos

```bash
# Conectar a PostgreSQL
psql -h 127.0.0.1 -U vpv -d ligavpv -c "SELECT count(*) as total_players FROM players;"

# Debe devolver un número > 0
```

### 19.2. Backend API

```bash
# Health check
curl -s https://ligavpv.com/api/health | python3 -m json.tool
# Esperado: {"status":"healthy","database":true,...}

# Temporadas
curl -s https://ligavpv.com/api/seasons | python3 -m json.tool | head -20

# Usuarios
curl -s https://ligavpv.com/api/users | python3 -m json.tool | head -10
```

Si alguno de estos falla con 502/503, verifica:

```bash
sudo systemctl status vpv-backend
sudo journalctl -u vpv-backend --no-pager -n 30
```

### 19.3. Frontend

```bash
# Acceder a https://ligavpv.com
curl -s -o /dev/null -w "%{http_code}" https://ligavpv.com
# Esperado: 200

# Ver el HTML
curl -sk https://ligavpv.com | head -20
```

### 19.4. Fotos de jugadores

```bash
# Verificar foto específica
curl -sk -o /dev/null -w "%{http_code}" https://ligavpv.com/static/players/dani-parejo.webp
# Esperado: 200

# Descargar y verificar tamaño
curl -sk -L https://ligavpv.com/static/players/dani-parejo.webp > /tmp/test.webp
file /tmp/test.webp
# Esperado: "WebP image data"
```

### 19.5. SSL/TLS

```bash
# Verificar certificado
curl -sk -I https://ligavpv.com | grep -i ssl

# Ver detalles del certificado
openssl s_client -connect ligavpv.com:443 < /dev/null 2>/dev/null | \
    openssl x509 -text -noout | grep -E "Subject:|Issuer:|Not Before|Not After"
```

### 19.6. Servicios

```bash
# Backend
sudo systemctl is-active vpv-backend
# Esperado: active

# Frontend
sudo -u vpv pm2 status
# Esperado: vpv-frontend en "online"

# PostgreSQL
sudo systemctl is-active postgresql
# Esperado: active

# Nginx
sudo systemctl is-active nginx
# Esperado: active
```

### 19.7. Firewall

```bash
# Verificar puertos abiertos
sudo firewall-cmd --list-all | grep -E "services|ports"
# Esperado: http, https

# Desde máquina local, intentar conectar (debe funcionar)
telnet ligavpv.com 443
# Esperado: conexión establecida
# (Ctrl+] luego quit para salir)
```

### 19.8. Logs sin errores graves

```bash
# Últimas 50 líneas del backend
sudo journalctl -u vpv-backend --no-pager -n 50 | grep -i "error\|warning\|critical"

# Si hay errores, investigar con todo el log
sudo journalctl -u vpv-backend -f
```

### 19.9. Backup funciona

```bash
# Ejecutar backup manualmente
sudo -u vpv /opt/vpv/backup_db.sh

# Verificar que existe
ls -lh /opt/vpv/backups/ | head -5
```

---

## 20. Mantenimiento continuo

### 20.1. Despliegues de nuevas versiones

Cuando tengas nuevas versiones en el repositorio:

```bash
cd /opt/vpv/repo
./deploy/scripts/deploy.sh
```

Este script:
1. Hace `git pull --ff-only`
2. Backend: instala deps + Alembic upgrade + systemd restart
3. Frontend: npm ci + build + PM2 restart
4. Health check automático

Tiempo estimado: 5-10 minutos sin downtime.

### 20.2. Migraciones Alembic

Si hay nuevas migraciones pendientes:

```bash
# Ver estado
cd /opt/vpv/backend
source .venv/bin/activate
alembic current
alembic history

# Aplicar (el deploy.sh lo hace automáticamente)
alembic upgrade head

# Revertir última si hay problema
alembic downgrade -1
```

### 20.3. Limpieza de logs

```bash
# Ver tamaño de logs
du -sh /var/log/vpv/

# Logrotate lo hace automáticamente, pero puedes forzarlo
sudo logrotate -f /etc/logrotate.d/vpv

# Ver histórico
ls -lh /var/log/vpv/
```

### 20.4. Limpiar backups viejos manualmente

```bash
# Los backups de > 30 días se borran automáticamente
# Pero si quieres borrar manualmente:
find /opt/vpv/backups -name "*.dump" -mtime +30 -delete

# Ver backups disponibles
ls -lht /opt/vpv/backups/
```

### 20.5. Actualizar certificado SSL

```bash
# Certbot lo hace automáticamente cada 60 días
# Pero puedes forzarlo:
sudo certbot renew --force-renewal

# Ver estado
sudo certbot certificates
```

### 20.6. Actualizar sistema operativo

```bash
# Ver actualizaciones disponibles
sudo dnf check-update

# Instalar (con precaución, puede requerir reboot)
sudo dnf update

# Si requiere reboot:
sudo reboot
```

### 20.7. PostgreSQL maintenance

Ejecutar regularmente (mensual):

```bash
# Conectar como vpv
psql -h 127.0.0.1 -U vpv -d ligavpv

# Limpiar espacio muerto y actualizar estadísticas
VACUUM ANALYZE;

# Ver tamaño actual
SELECT pg_size_pretty(pg_database_size('ligavpv'));

# Salir
\q
```

---

## 21. Troubleshooting

### Problema: 502 Bad Gateway

El Nginx no puede conectar al backend.

**Diagnosis:**

```bash
# Verificar que el backend está corriendo
sudo systemctl status vpv-backend

# Si está parado, iniciar
sudo systemctl start vpv-backend

# Ver logs
sudo journalctl -u vpv-backend -n 30

# Verificar que escucha en el puerto
netstat -tlnp | grep 8000

# Probar conexión localmente
curl -s http://127.0.0.1:8000/api/health
```

**Causas comunes:**
- Contraseña PostgreSQL incorrecta → revisar `/opt/vpv/backend/.env`
- BD no está accesible → `sudo systemctl restart postgresql`
- Puerto 8000 en uso → `lsof -i :8000`

### Problema: 403 Forbidden en fotos

Las fotos retornan 403.

**Diagnosis:**

```bash
# Verificar permisos de archivo
ls -la /opt/vpv/backend/static/players/ | head

# Verificar SELinux context
ls -laZ /opt/vpv/backend/static/players/ | head

# Si el contexto SELinux no es httpd_sys_content_t:
sudo semanage fcontext -a -t httpd_sys_content_t "/opt/vpv/backend/static(/.*)?"
sudo restorecon -Rv /opt/vpv/backend/static/
```

**Causas comunes:**
- Archivo no existe → verificar carpeta y nombre
- Permisos incorrectos → `sudo chmod 644 /opt/vpv/backend/static/players/*`
- SELinux bloquea → ver comando `restorecon` arriba. Las fotos las sirve uvicorn (no Nginx directamente), asi que `httpd_can_network_connect` ya debe estar `on` (seccion 9)

### Problema: Database connection refused

```
Error: could not connect to server: Connection refused
```

**Diagnosis:**

```bash
# PostgreSQL está corriendo?
sudo systemctl status postgresql

# Escucha en puerto 5432?
sudo -u postgres psql -c "SELECT 1"

# Verificar pg_hba.conf
sudo nano /var/lib/pgsql/data/pg_hba.conf
# Debe tener: local all all scram-sha-256

# Reiniciar PostgreSQL
sudo systemctl restart postgresql

# Probar conexión como vpv
psql -h 127.0.0.1 -U vpv -d ligavpv -c "SELECT 1"
```

### Problema: PM2 no inicia en reboot

Frontend desaparece después de reiniciar.

**Diagnosis:**

```bash
# Ver si PM2 startup está configurado
sudo systemctl list-unit-files | grep pm2

# Como usuario vpv
sudo -u vpv pm2 status

# Si no aparece:
sudo -u vpv pm2 start /opt/vpv/ecosystem.config.js
sudo -u vpv pm2 save
sudo -u vpv pm2 startup systemd -u vpv --hp /opt/vpv
# Ejecutar el comando sudo que muestre
```

### Problema: Certificado SSL expirado

```
curl: (60) SSL certificate problem: certificate has expired
```

**Diagnosis:**

```bash
# Ver fecha de expiración
sudo certbot certificates

# Si está expirado, renovar
sudo certbot renew --force-renewal

# Verificar renovación automática
sudo systemctl list-timers | grep certbot
```

### Problema: Disco lleno

```
No space left on device
```

**Diagnosis:**

```bash
# Ver qué ocupa espacio
du -sh /opt/vpv/*
du -sh /var/log/vpv/*
du -sh /var/lib/pgsql/data/

# Limpieza:
# 1. Logs viejos
sudo logrotate -f /etc/logrotate.d/vpv
rm /var/log/vpv/*.gz

# 2. Backups viejos
find /opt/vpv/backups -name "*.dump" -mtime +7 -delete

# 3. Archivos temporales
sudo rm -rf /tmp/*

# Ver resultado
df -h
```

### Problema: Backend lento, usa 100% CPU

**Diagnosis:**

```bash
# Ver consumo de CPU
top -p $(pgrep -f uvicorn)

# Ver queries lentas (requiere extension pg_stat_statements)
# Para habilitarla: ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
# Luego reiniciar PG y ejecutar: CREATE EXTENSION pg_stat_statements;
psql -h 127.0.0.1 -U vpv -d ligavpv <<'EOF'
SELECT query, calls, mean_exec_time FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 10;
EOF

# Si alguna query está lenta, optimizar índice o query
# Contactar al equipo de desarrollo

# Reiniciar backend
sudo systemctl restart vpv-backend
```

---

## 22. Rollback

Si algo sale mal después de un despliegue:

### 22.1. Rollback de código

```bash
# Ver commits recientes
cd /opt/vpv/repo
git log --oneline -5

# Volver a version anterior
git checkout <commit_hash>

# Redesplegar
./deploy/scripts/deploy.sh
```

### 22.2. Rollback de base de datos

```bash
# Listar backups disponibles
ls -lht /opt/vpv/backups/ | head -10

# Restaurar
/opt/vpv/repo/deploy/scripts/restore_db.sh /opt/vpv/backups/ligavpv_YYYYMMDD_HHMMSS.dump

# El script te pedirá confirmación y reiniciará el backend
```

### 22.3. Rollback de migración Alembic

```bash
# Ver migraciones históricas
cd /opt/vpv/backend
source .venv/bin/activate
alembic history

# Revertir última migración
alembic downgrade -1

# Reiniciar backend
sudo systemctl restart vpv-backend
```

---

## Guía rápida de comandos comunes

```bash
# Ver estado de todo
sudo systemctl status vpv-backend postgresql nginx
sudo -u vpv pm2 status

# Reiniciar servicios
sudo systemctl restart vpv-backend
sudo systemctl restart postgresql
sudo systemctl restart nginx
sudo -u vpv pm2 restart vpv-frontend

# Ver logs
sudo journalctl -u vpv-backend -f
sudo -u vpv pm2 logs vpv-frontend

# Backup manual
sudo -u vpv /opt/vpv/backup_db.sh

# Despliegue
cd /opt/vpv/repo
./deploy/scripts/deploy.sh

# Acceder a PostgreSQL
psql -h 127.0.0.1 -U vpv -d ligavpv

# Ejecutar Alembic
cd /opt/vpv/backend
source .venv/bin/activate
alembic upgrade head

# Health check
curl -s https://ligavpv.com/api/health | python3 -m json.tool
```

---

## Resumen de rutas en producción

| Recurso | Ruta |
|---------|------|
| Repositorio | `/opt/vpv/repo` |
| Backend (app) | `/opt/vpv/backend` |
| Backend (venv) | `/opt/vpv/backend/.venv` |
| Backend (variables env) | `/opt/vpv/backend/.env` |
| Backend (fotos) | `/opt/vpv/backend/static/players/` |
| Frontend | `/opt/vpv/frontend` |
| Logs | `/var/log/vpv/` |
| Backups | `/opt/vpv/backups/` |
| Nginx config | `/etc/nginx/conf.d/ligavpv.conf` |
| Systemd backend | `/etc/systemd/system/vpv-backend.service` |
| PM2 config | `/opt/vpv/ecosystem.config.js` |
| Logrotate | `/etc/logrotate.d/vpv` |

## Resumen de puertos

| Servicio | Puerto | Acceso | Protocolo |
|----------|--------|--------|-----------|
| Nginx (HTTP) | 80 | Público | HTTP |
| Nginx (HTTPS) | 443 | Público | HTTPS |
| FastAPI | 8000 | localhost solo | HTTP |
| Next.js | 3000 | localhost solo | HTTP |
| PostgreSQL | 5432 | localhost solo | TCP |
| SSH | 2222 | Público (restringido) | SSH |

---

## Checklist de seguridad final

- [ ] SSH: root login deshabilitado
- [ ] SSH: solo autenticación por clave
- [ ] SSH: puerto no estándar (2222)
- [ ] Firewall: solo 80, 443, SSH abiertos
- [ ] SELinux: enforcing
- [ ] fail2ban: activo
- [ ] Actualizaciones automáticas: configuradas
- [ ] Certificado SSL: válido y configurado para renovación automática
- [ ] Backups: ejecutados diariamente, retención de 30 días
- [ ] PostgreSQL: contraseña fuerte, scram-sha-256
- [ ] JWT_SECRET_KEY: > 64 caracteres aleatorios
- [ ] CORS_ORIGINS: solo https://ligavpv.com
- [ ] DEBUG: false en backend
- [ ] ENVIRONMENT: production
- [ ] Logs: monitorizados, rotados diariamente
- [ ] Monitorización: health check configurado

---

**Fin de la Guía de Producción**

Para soporte, contactar al equipo de desarrollo o revisar los logs con:
```bash
sudo journalctl -u vpv-backend -f
sudo -u vpv pm2 logs vpv-frontend
```
