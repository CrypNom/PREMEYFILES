# Deployment guide: putting PREMEYFILES online

The website needs a host that can run **Python** and has a **persistent disk** (so the SQLite database and
uploaded files survive restarts). Plans, prices and menu names of hosting companies change - treat the
host-specific steps below as a guide and check your host's current documentation.

## What you must set online (environment variables)

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | long random text: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | creates your first admin on first start (password ≥ 8 chars). Remove afterwards. |
| `DATABASE_PATH` | file on the persistent disk, e.g. `/var/data/premeyfiles.db` |
| `UPLOAD_DIR` | folder on the persistent disk, e.g. `/var/data/uploads` |
| `TRUST_PROXY` | `1` |
| `COOKIE_SECURE` | `1` |
| `MAX_UPLOAD_MB_LIMIT` | biggest upload allowed, e.g. `200` |

**Start command** (same on every host): 

```
cd website && waitress-serve --host=0.0.0.0 --port=$PORT app:app
```

Build command: `pip install -r website/requirements.txt`. Use Python 3.10+.

**Important:** run exactly **one** instance/worker of the site (SQLite is a single-file database).

## Option A - A platform host (Render, Railway, Fly.io, ...)

1. Put the project in a private GitHub repository (the included `.gitignore` keeps `.env`, the database and
   uploads out of it). From the project folder:
   ```cmd
   git init
   git add .
   git commit -m "PREMEYFILES"
   ```
   then create an empty private repo on GitHub and push (GitHub shows the exact commands).
2. Create a new **Web Service** from the repository, with the build/start commands above.
3. Add a **persistent disk / volume**, mounted at e.g. `/var/data`. Without it, every redeploy erases
   your uploads and database.
4. Add the environment variables from the table.
5. Deploy. Open the address the host gives you, e.g. `https://premeyfiles.onrender.com`.
6. In the admin app type that address on the login screen and log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
   Then delete those two variables on the host and change your password under *Website Content*.

Free plans usually have no persistent disk and may sleep when idle; choose a plan with a disk for real use.

## Option B - Your own Linux server (VPS, Ubuntu)

```bash
sudo apt update && sudo apt install -y python3 python3-venv nginx git
sudo mkdir -p /srv/premeyfiles /var/data/premeyfiles && cd /srv/premeyfiles
# upload/unzip the project here, then:
python3 -m venv venv
venv/bin/pip install -r website/requirements.txt
```

Create `/etc/premeyfiles.env` (readable only by root: `sudo chmod 600 /etc/premeyfiles.env`):

```
SECRET_KEY=paste-your-long-random-key
ADMIN_USERNAME=youradmin
ADMIN_PASSWORD=a-long-password
DATABASE_PATH=/var/data/premeyfiles/premeyfiles.db
UPLOAD_DIR=/var/data/premeyfiles/uploads
TRUST_PROXY=1
COOKIE_SECURE=1
MAX_UPLOAD_MB_LIMIT=200
```

`/etc/systemd/system/premeyfiles.service`:

```
[Unit]
Description=PREMEYFILES
After=network.target

[Service]
WorkingDirectory=/srv/premeyfiles/website
EnvironmentFile=/etc/premeyfiles.env
ExecStart=/srv/premeyfiles/venv/bin/waitress-serve --listen=127.0.0.1:8000 app:app
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /var/data/premeyfiles /srv/premeyfiles
sudo systemctl daemon-reload && sudo systemctl enable --now premeyfiles
```

`/etc/nginx/sites-available/premeyfiles` (then link it into `sites-enabled` and `sudo nginx -t && sudo systemctl reload nginx`):

```
server {
    server_name yourdomain.com www.yourdomain.com;
    client_max_body_size 200m;          # must be >= your biggest upload
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_request_buffering off;
    }
}
```

Free HTTPS certificate:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## Connect a custom domain

1. Buy a domain from any registrar.
2. **Platform host:** in the service's *Custom Domains* section add `yourdomain.com` / `www.yourdomain.com`; it shows
   the DNS records to create (usually a `CNAME` for `www` and an `A`/`ALIAS` record for the bare domain).
   **VPS:** create an `A` record pointing `yourdomain.com` and `www` to your server's IP address.
3. Add those records in your registrar's DNS panel. Changes take minutes to a few hours.
4. Make sure HTTPS is active (platform hosts issue it automatically; on a VPS use certbot above).
5. In the admin app use `https://yourdomain.com` as the website address.

## Make the desktop admin manage the online site

Nothing to change in the admin app: type your online address on the login screen. The address is remembered
(the password never is). Always use `https://` online so your password and uploads are encrypted.

## Persistent file storage - checklist

- `DATABASE_PATH` and `UPLOAD_DIR` point to a disk/volume that survives restarts and redeploys.
- Check after the first deploy: upload a test project, restart the service, confirm it is still there.
- Uploaded files are stored with random names; the original name is kept in the database and used for the download.

## Backups

- **Windows (local):** `5_BACKUP.bat`.
- **Server:** back up the database with SQLite's safe copy, and copy the uploads folder:
  ```bash
  sqlite3 /var/data/premeyfiles/premeyfiles.db ".backup '/backup/premeyfiles-$(date +%F).db'"
  tar czf /backup/uploads-$(date +%F).tar.gz -C /var/data/premeyfiles uploads
  ```
  (install with `sudo apt install sqlite3`). Automate with `cron`, e.g. daily at 03:00, and keep copies
  off the server (another provider or your PC).
- **Platform hosts:** use the host's disk snapshot/backup feature if offered, plus regular manual copies.
- **Restore:** stop the site, put the `.db` file and uploads folder back in the same locations, start the site.

## Security checklist before going public

- [ ] Strong `SECRET_KEY`, strong admin password, HTTPS on.
- [ ] `ADMIN_PASSWORD` removed from the environment after first start.
- [ ] `COOKIE_SECURE=1`, `TRUST_PROXY=1` (only behind a real proxy/host).
- [ ] You only upload files you have the right to distribute.
- [ ] Regular backups tested by restoring once.
