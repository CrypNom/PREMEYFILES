# Install guide (Windows, step by step)

Every command below is for **Windows Command Prompt (CMD)**. To open it: press the Windows key,
type `cmd`, press Enter.

> Shortcut: the `.bat` files in the main folder do steps 3-7 for you. This guide explains what they do.

## 1. Install Python

1. Download Python 3.10 or newer: https://www.python.org/downloads/
2. Run the installer. **Tick "Add python.exe to PATH"** (first screen), then *Install Now*.
3. Check it worked - open a **new** CMD window:

```cmd
python --version
python -c "import tkinter; print('Tkinter OK')"
```

You should see a version number and `Tkinter OK`. If `tkinter` is missing, run the Python installer again
→ *Modify* → make sure **tcl/tk and IDLE** is ticked.

## 2. Put the project somewhere simple

Unzip `PREMEYFILES.zip`, for example to `C:\PREMEYFILES`. Then:

```cmd
cd C:\PREMEYFILES
```

## 3. Create a virtual environment (a private box for the packages)

```cmd
python -m venv venv
```

## 4. Install the dependencies

```cmd
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r website\requirements.txt
venv\Scripts\python -m pip install -r admin_software\requirements.txt
```

## 5. Create your settings file

```cmd
copy .env.example .env
notepad .env
```

On your own computer you can leave everything empty. (A secret key is generated automatically.)

## 6. Create the admin account (you choose the username and password)

```cmd
cd website
..\venv\Scripts\python create_admin.py
```

Password: at least 8 characters. It is hidden while you type and only a hash is stored. Run the same
command later to **reset** a forgotten password.

## 7. Run the website

```cmd
cd C:\PREMEYFILES\website
..\venv\Scripts\python -m waitress --listen=127.0.0.1:5000 app:app
```

Open http://127.0.0.1:5000 in your browser. Keep this window open - closing it stops the website.
(`python app.py` also works for quick tests.) The database file `database\premeyfiles.db` is created
automatically.

## 8. Run the desktop admin app (second CMD window)

```cmd
cd C:\PREMEYFILES\admin_software
..\venv\Scripts\python main.py
```

On the login screen enter:

| Field | Value |
|-------|-------|
| Website address | `http://127.0.0.1:5000` |
| Username / Password | the admin account from step 6 |

## 9. How the two programs connect

The admin app sends your username and password to `POST /api/login` on the website. The website answers
with a temporary token; the admin app sends that token with every action. **The website is the only place
data lives** - so changes are instantly public. To manage an online site, just type its address
(`https://www.yourdomain.com`) instead of `http://127.0.0.1:5000`.

## 10. Publish your first project

1. Admin app → **Publish New**.
2. **Choose file...** → pick a ZIP. The title is suggested from the file name.
3. Fill in description, pick a category and languages (Ctrl+click for several), optionally add a thumbnail.
4. Click **Publish** - watch the progress bar. Refresh the website: it is there.

To delete: **All Projects** → click the project → **Delete** → confirm. It disappears from the website and
the stored file is erased.

## Settings you can change in the admin app

**Website Content** screen: website name, headline, about text, footer, contact email, **allowed file
extensions** (add e.g. `go` or `rs`), and the **maximum upload size** in MB. Executable types
(`exe, dll, msi, com, scr, bat, cmd, vbs, ps1, lnk`) can never be enabled.

## Where is everything stored?

| What | Where |
|------|-------|
| Database | `database\premeyfiles.db` |
| Uploaded source code | `website\uploads\files` (random names) |
| Thumbnails | `website\uploads\thumbnails` |
| Your settings | `.env` |

## Back up

```cmd
cd C:\PREMEYFILES
5_BACKUP.bat
```

creates `backups\premeyfiles_DATE.zip` with the database and all uploads. To restore: stop the website,
unzip the backup over the main folder, start the website again. Copy backups to another drive or cloud
storage regularly.
