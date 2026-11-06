# Troubleshooting

| Problem | Fix |
|---------|-----|
| `'python' is not recognized` | Reinstall Python and tick **Add python.exe to PATH**; open a *new* CMD window. |
| `No module named tkinter` | Re-run the Python installer → Modify → tick **tcl/tk and IDLE**. |
| `No module named flask` / `requests` | Use the virtual environment: `venv\Scripts\python ...` (see INSTALL_GUIDE step 4). |
| Admin says *Cannot reach the website* | Start `3_START_WEBSITE.bat` first; check the address (`http://127.0.0.1:5000`, no typos, `https://` online). |
| *Wrong username or password* | Reset with `2_CREATE_ADMIN.bat` (same username resets the password). After 5 wrong tries wait 5 minutes. |
| *Your session has expired* | Normal after 12 hours (change `TOKEN_HOURS`). Log in again. |
| *'.xyz' files are not allowed* | Add the extension in admin → **Website Content** → *Allowed file extensions*. Executables can never be added. |
| *The file is too large* / upload error 413 | Raise *Maximum upload size* in **Website Content** (cannot exceed `MAX_UPLOAD_MB_LIMIT`). Behind nginx also raise `client_max_body_size`. |
| Port 5000 already in use | Set `PORT=5001` in `.env` and use `http://127.0.0.1:5001`; update the 3_START_WEBSITE.bat number too. |
| Uploads vanish after redeploy online | The host has no persistent disk. Point `DATABASE_PATH` / `UPLOAD_DIR` to a persistent volume. |
| Website text did not change | Hard-refresh the browser (Ctrl+F5). |
| Forgot to back up | Run `5_BACKUP.bat` now; see DEPLOYMENT_GUIDE for server backups. |
