# Admin API reference (for the curious)

All routes except login need the header `Authorization: Bearer <token>`. Answers are JSON:
`{"ok": true, ...}` or `{"ok": false, "error": "message"}`.

| Method & path | Purpose |
|---------------|---------|
| `POST /api/login` `{username, password}` | returns `token` |
| `POST /api/logout`, `GET /api/me`, `POST /api/change-password` | session / account |
| `GET /api/dashboard` | totals, top projects, downloads per day |
| `GET /api/projects?q=&category=` | list / search |
| `GET /api/projects/<id>` | one project + last-30-days downloads |
| `POST /api/projects` (multipart: `title, description, category_id, language_ids, file, thumbnail`) | publish |
| `PUT /api/projects/<id>` (same fields, all optional, `remove_thumbnail=1`) | update |
| `DELETE /api/projects/<id>` | delete project and its files |
| `GET/POST/PUT/DELETE /api/categories[/<id>]` | categories |
| `GET/POST/PUT/DELETE /api/languages[/<id>]` | language tags |
| `GET/PUT /api/settings` | website text, allowed extensions, max upload size |
| `GET /api/messages`, `POST /api/messages/<id>/read`, `DELETE /api/messages/<id>` | contact messages |

Public (no login): `GET /download/<id>`, `GET /api/public/search?q=`.
