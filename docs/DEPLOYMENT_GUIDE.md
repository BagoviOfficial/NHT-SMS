# Production Deployment Guide — NHT-SMS

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  
**Target Environment:** Ubuntu 22.04 / 24.04 LTS VPS (Cloud or On-Premises)  
**Release Candidate:** v1.0.0-rc1  

---

## 1. Hardware & System Prerequisites

### Minimum Server Specifications
- **Operating System:** Ubuntu 22.04 LTS or Ubuntu 24.04 LTS (64-bit x86_64 or aarch64)
- **Compute:** 2 vCPU cores minimum (4 vCPU recommended)
- **Memory (RAM):** 4 GB RAM minimum (8 GB recommended for high-volume Celery concurrency)
- **Storage:** 40 GB NVMe / SSD minimum (with dedicated volume for backups and private documents)
- **Networking:** Static public IPv4 address, DNS A-Record mapped to `nht-sms.northernhighways.co.ke`
- **Firewall Ports:** Open Inbound TCP `80` (HTTP), `443` (HTTPS), and `22` (SSH via key-only authentication)

---

## 2. Option A: Docker Compose Deployment (Recommended)

Docker Compose provides an isolated, reproducible multi-container deployment encompassing web application, Celery workers, Celery beat, PostgreSQL 16, Redis 7, and Nginx.

### Step 1: Install Docker Engine & Compose Plugin
```bash
# Update Ubuntu package index
sudo apt update && sudo apt upgrade -y

# Install Docker dependencies
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Compose plugin
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable Docker on system boot
sudo systemctl enable --now docker
```

### Step 2: Clone Codebase & Configure Environment
```bash
# Clone the repository
git clone https://github.com/northernhighways/nht-sms.git /opt/nht-sms
cd /opt/nht-sms

# Copy production environment template
cp .env.production.example .env.production

# Edit environment configuration
nano .env.production
```
*Mandatory settings to configure:*
- `SECRET_KEY`: Set to a strong 50+ character cryptographic random string.
- `POSTGRES_PASSWORD`: Strong database password.
- `ALLOWED_HOSTS`: Set to your production domain(s) (e.g. `nht-sms.northernhighways.co.ke,sacco.northernhighways.co.ke`).
- `MPESA_*`: Live Safaricom Daraja credentials.
- `AT_*` / `WHATSAPP_*`: Messaging API credentials.

### Step 3: Install SSL Certificates
Place your production SSL certificate and private key in `./docker/nginx/certs/`:
- `docker/nginx/certs/fullchain.pem`
- `docker/nginx/certs/privkey.pem`

*(Alternatively, obtain free certificates via Certbot on the host as described in Section 4).*

### Step 4: Build and Launch Containers
```bash
# Build and start all 6 containers in detached mode
docker compose up -d --build

# Verify container statuses
docker compose ps
```

### Step 5: Seed Baseline Master Data
```bash
# Seed initial administrator, document types, billing catalogue, and chart of accounts
docker compose exec web python manage.py seed_sacco_admin
docker compose exec web python manage.py seed_document_types
docker compose exec web python manage.py seed_billing_services
docker compose exec web python manage.py seed_chart_of_accounts
docker compose exec web python manage.py seed_notification_templates
```

---

## 3. Option B: Bare-Metal Ubuntu VPS Deployment

For organizations running direct native systemd services without containerization.

### Step 1: Install System Packages
```bash
sudo apt update && sudo apt install -y \
    python3-venv python3-pip python3-dev \
    postgresql postgresql-contrib \
    redis-server \
    nginx certbot python3-certbot-nginx \
    libpq-dev gcc curl git ufw
```

### Step 2: Configure PostgreSQL 16
```bash
sudo -u postgres psql -c "CREATE DATABASE nht_sms_db;"
sudo -u postgres psql -c "CREATE USER nht_sms_user WITH PASSWORD 'your_strong_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE nht_sms_db TO nht_sms_user;"
sudo -u postgres psql -c "ALTER DATABASE nht_sms_db OWNER TO nht_sms_user;"
```

### Step 3: Configure Redis
```bash
sudo systemctl enable --now redis-server
# Test Redis responsiveness
redis-cli ping  # Expects PONG
```

### Step 4: Provision Application Directory & Virtual Environment
```bash
# Create dedicated directory owned by www-data
sudo mkdir -p /var/www/nht-sms
sudo chown -R www-data:www-data /var/www/nht-sms

# Clone codebase
sudo -u www-data git clone https://github.com/northernhighways/nht-sms.git /var/www/nht-sms
cd /var/www/nht-sms

# Create Python virtual environment
sudo -u www-data python3 -m venv venv
sudo -u www-data ./venv/bin/pip install --upgrade pip
sudo -u www-data ./venv/bin/pip install -r requirements/production.txt

# Configure .env.production
sudo -u www-data cp .env.production.example .env.production
sudo -u www-data nano .env.production
```

### Step 5: Execute Migrations & Collect Static Assets
```bash
sudo -u www-data ./venv/bin/python manage.py migrate --noinput
sudo -u www-data ./venv/bin/python manage.py collectstatic --noinput --clear
```

### Step 6: Install Systemd Services
```bash
# Copy systemd unit files
sudo cp docker/systemd/nht-sms-gunicorn.service /etc/systemd/system/
sudo cp docker/systemd/nht-sms-celery-worker.service /etc/systemd/system/
sudo cp docker/systemd/nht-sms-celery-beat.service /etc/systemd/system/

# Reload systemd daemon and enable services
sudo systemctl daemon-reload
sudo systemctl enable --now nht-sms-gunicorn
sudo systemctl enable --now nht-sms-celery-worker
sudo systemctl enable --now nht-sms-celery-beat

# Verify running state
sudo systemctl status nht-sms-gunicorn
```

---

## 4. Nginx Reverse Proxy & Let's Encrypt SSL/TLS

### Step 1: Install Nginx Configuration
```bash
sudo cp docker/nginx/nht_sacco_vps.conf /etc/nginx/sites-available/nht_sacco
sudo ln -s /etc/nginx/sites-available/nht_sacco /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

### Step 2: Issue Let's Encrypt SSL Certificate
```bash
sudo certbot --nginx -d nht-sms.northernhighways.co.ke -d sacco.northernhighways.co.ke
# Test automated renewal
sudo certbot renew --dry-run
```

### Step 3: Test and Reload Nginx
```bash
sudo nginx -t
sudo systemctl restart nginx
```

---

## 5. Post-Deployment Smoke Testing & Health Verification

Run these validation checks immediately following deployment:

1. **Liveness Probe:**
   ```bash
   curl -I https://nht-sms.northernhighways.co.ke/health/live/
   # Expect: HTTP/2 200 OK, {"status": "alive", "service": "NHT-SMS"}
   ```
2. **Readiness Probe:**
   ```bash
   curl -I https://nht-sms.northernhighways.co.ke/health/ready/
   # Expect: HTTP/2 200 OK, {"status": "ready", "database": "connected"}
   ```
3. **Django Production Security Check:**
   ```bash
   python manage.py check --deploy
   # Expect: System check identified no issues (0 silenced).
   ```

---

## 6. Zero-Downtime Updates & Rollback Runbook

### Rolling Update
```bash
cd /opt/nht-sms (or /var/www/nht-sms)
git pull origin main
docker compose up -d --build
# Or on bare-metal:
# ./venv/bin/pip install -r requirements/production.txt
# ./venv/bin/python manage.py migrate --noinput
# ./venv/bin/python manage.py collectstatic --noinput
# sudo systemctl restart nht-sms-gunicorn nht-sms-celery-worker nht-sms-celery-beat
```

### Rollback Runbook
If an update introduces unexpected regressions:
```bash
# 1. Revert git commit
git checkout <previous_known_good_commit_tag>

# 2. Rebuild and restart services
docker compose up -d --build

# 3. If schema changes need restoring:
./scripts/restore_db.sh backups/db/<pre_update_backup>.sql.gz --force
```
