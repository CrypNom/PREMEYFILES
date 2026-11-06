"""
app.py - The PREMEYFILES public website (Flask).

Run it with:   python app.py
"""
import mimetypes

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

import config
import database as db
import utils
from api import api
from utils import ValidationError

app = Flask(__name__)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    MAX_CONTENT_LENGTH=(config.HARD_MAX_UPLOAD_MB + config.MAX_THUMBNAIL_MB + 2) * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=config.COOKIE_SECURE,
    WTF_CSRF_TIME_LIMIT=None,
    JSON_SORT_KEYS=False,
)
if config.TRUST_PROXY:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# CSRF protection for every form on the website. The admin API uses
# Authorization headers instead of cookies, so it is exempt.
csrf = CSRFProtect(app)
csrf.exempt(api)

app.register_blueprint(api)
app.teardown_appcontext(db.close_db)

db.init_db()
db.bootstrap_admin_from_env()


# ------------------------------------------------------------------ template helpers
@app.context_processor
def inject_globals():
    settings = db.get_settings()
    return {
        "site": settings,
        "nav_categories": db.query("SELECT id, name FROM categories ORDER BY name"),
        "format_size": utils.format_size,
        "format_date": utils.format_date,
    }


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ------------------------------------------------------------------ pages
@app.route("/")
def home():
    latest, _ = utils.search_projects(limit=6)
    popular, _ = utils.search_projects(sort="popular", limit=3)
    categories = db.query(
        "SELECT c.id, c.name, c.description, COUNT(p.id) AS projects "
        "FROM categories c LEFT JOIN projects p ON p.category_id = c.id "
        "GROUP BY c.id ORDER BY c.name"
    )
    stats = db.query(
        "SELECT (SELECT COUNT(*) FROM projects) AS projects, "
        "(SELECT COALESCE(SUM(download_count),0) FROM projects) AS downloads, "
        "(SELECT COUNT(*) FROM categories) AS categories",
        one=True,
    )
    return render_template("index.html", latest=latest, popular=popular, categories=categories, stats=stats)


@app.route("/projects")
def projects():
    q = utils.clean_text(request.args.get("q", ""), 100)
    category_id = request.args.get("category", type=int)
    language_id = request.args.get("language", type=int)
    sort = "popular" if request.args.get("sort") == "popular" else "new"
    page = max(1, request.args.get("page", 1, type=int))
    per_page = config.PROJECTS_PER_PAGE

    items, total = utils.search_projects(q, category_id, language_id, sort, per_page, (page - 1) * per_page)
    pages = max(1, -(-total // per_page))
    return render_template(
        "projects.html", projects=items, total=total, q=q, category_id=category_id,
        language_id=language_id, sort=sort, page=page, pages=pages,
        languages=db.query("SELECT id, name FROM languages ORDER BY name"),
    )


@app.route("/project/<int:project_id>")
def project_detail(project_id):
    project = utils.get_project(project_id)
    if not project:
        abort(404)
    related, _ = utils.search_projects(category_id=project["category_id"], limit=4) if project["category_id"] else ([], 0)
    related = [p for p in related if p["id"] != project_id][:3]
    return render_template("project.html", project=project, related=related)


@app.route("/download/<int:project_id>")
def download(project_id):
    row = db.query(
        "SELECT f.stored_name, f.original_name FROM files f "
        "JOIN projects p ON p.id = f.project_id WHERE p.id = ?", (project_id,), one=True)
    if not row or not utils.STORED_NAME_RE.match(row["stored_name"]):
        abort(404)
    if not (config.FILES_DIR / row["stored_name"]).is_file():
        abort(404)
    if request.method == "GET":
        db.execute("UPDATE projects SET download_count = download_count + 1 WHERE id = ?", (project_id,))
        db.execute("INSERT INTO downloads (project_id, ip_hash) VALUES (?, ?)",
                   (project_id, utils.hash_ip(request.remote_addr)))
    # Always sent as a download (attachment) and never executed or rendered by the server.
    return send_from_directory(config.FILES_DIR, row["stored_name"], as_attachment=True,
                               download_name=row["original_name"],
                               mimetype="application/octet-stream")


@app.route("/thumbnails/<name>")
def thumbnail(name):
    if not utils.STORED_NAME_RE.match(name):
        abort(404)
    ext = name.rsplit(".", 1)[1]
    if ext not in config.THUMBNAIL_EXTENSIONS:
        abort(404)
    response = send_from_directory(config.THUMBS_DIR, name, mimetype=mimetypes.types_map.get("." + ext))
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        try:
            if request.form.get("website"):          # hidden "honeypot" field: bots fill it in
                return redirect(url_for("contact"))
            name = utils.clean_text(request.form.get("name"), 80, "Name", required=True)
            email = utils.clean_email(request.form.get("email"))
            message = utils.clean_text(request.form.get("message"), 3000, "Message", required=True, min_len=5)
            recent = db.query("SELECT COUNT(*) AS n FROM messages WHERE created_at >= datetime('now', '-1 hour')",
                              one=True)["n"]
            if recent >= 50:
                raise ValidationError("Too many messages right now. Please try again later.")
            db.execute("INSERT INTO messages (name, email, message) VALUES (?, ?, ?)", (name, email, message))
            flash("Thank you! Your message was sent.", "success")
            return redirect(url_for("contact") + "#contact-form")
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_template("contact.html", form=request.form), 400
    return render_template("contact.html", form={})


@app.route("/api/public/search")
def public_search():
    """Small JSON endpoint used by the live search box (JavaScript)."""
    q = utils.clean_text(request.args.get("q", ""), 100)
    if len(q) < 2:
        return jsonify([])
    items, _ = utils.search_projects(q, limit=6)
    return jsonify([{"id": p["id"], "title": p["title"], "category": p["category"],
                     "url": url_for("project_detail", project_id=p["id"])} for p in items])


# ------------------------------------------------------------------ errors
@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found."}), 404
    return render_template("error.html", code=404, message="We couldn't find that page."), 404


@app.errorhandler(413)
def too_large(_e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "The upload is too large for this server."}), 413
    return render_template("error.html", code=413, message="That upload is too large."), 413


@app.errorhandler(405)
def bad_method(_e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Method not allowed."}), 405
    return render_template("error.html", code=405, message="That action is not allowed."), 405


@app.errorhandler(CSRFError)
def csrf_error(_e):
    flash("Your form expired. Please try again.", "error")
    return redirect(request.referrer or url_for("home"))


@app.errorhandler(500)
def server_error(_e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Server error. Check the server window for details."}), 500
    return render_template("error.html", code=500, message="Something went wrong on our side."), 500


if __name__ == "__main__":
    if db.admin_count() == 0:
        print("\n[PREMEYFILES] No admin account yet. Run:  python create_admin.py\n")
    app.run(host=config.HOST, port=config.PORT, debug=False)
