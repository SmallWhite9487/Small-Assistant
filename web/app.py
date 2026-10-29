"""Flask front end for Small-Assistant.

Run from the repository root with either:

    python web/app.py
    flask --app web.app run --debug

The web app keeps its own data in web/ (words.csv, Notes/, user_weights/), so
it never changes the Tkinter app's files. Review weights are stored per device
in user_weights/<CODE>.csv, where CODE comes from a cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

WEB_DIR = Path(__file__).resolve().parent
ROOT = WEB_DIR.parent
for path in (str(ROOT), str(WEB_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from services import (  # noqa: E402
    AIChecker,
    ApiError,
    ConjugationService,
    NoteService,
    WeightService,
    WordService,
)

load_dotenv(ROOT / ".env")

app = Flask(__name__)

# Behind a reverse proxy / tunnel every request appears to come from the proxy.
# WEB_PROXY_HOPS is how many trusted proxies sit in front of the app (0 = none,
# so spoofed X-Forwarded-For headers are ignored).
PROXY_HOPS = max(0, int(os.getenv("WEB_PROXY_HOPS", "0") or 0))
if PROXY_HOPS:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=PROXY_HOPS, x_proto=PROXY_HOPS, x_host=PROXY_HOPS)

if not app.logger.handlers or app.logger.level == logging.NOTSET:
    app.logger.setLevel(logging.INFO)
app.json.ensure_ascii = False
app.json.sort_keys = False
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

app.secret_key = os.getenv("WEB_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("WEB_COOKIE_SECURE", "") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
MAX_FAILURES = 5
LOCKOUT_SECONDS = 300
failed_logins: dict[str, list[float]] = {}


def access_hash() -> str:
    """SHA-256 hex digest of the access key, read from WEB_ACCESS_KEY_SHA256 in .env."""
    return os.getenv("WEB_ACCESS_KEY_SHA256", "").strip().lower()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def locked_out(client: str) -> int:
    """Seconds left on a lockout for this client, or 0."""
    now = time.time()
    recent = [t for t in failed_logins.get(client, []) if now - t < LOCKOUT_SECONDS]
    failed_logins[client] = recent
    if len(recent) >= MAX_FAILURES:
        return int(LOCKOUT_SECONDS - (now - recent[0])) + 1
    return 0


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def require_access():
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            abort(403)
    if not HASH_PATTERN.fullmatch(access_hash()):
        if request.path.startswith("/api/"):
            return jsonify(error="Access key is not configured."), 503
        return (
            "Access key is not configured. Run `python3 web/app.py --set-key` "
            "and restart the server.",
            503,
        )
    if request.endpoint in {"login", "static"} or session.get("authenticated"):
        return None
    if request.path.startswith("/api/"):
        return jsonify(error="Please sign in first."), 401
    return redirect(url_for("login", next=request.full_path.rstrip("?")))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    next_url = request.values.get("next", "/")
    if not next_url.startswith("/") or next_url.startswith("//") or "\\" in next_url:
        next_url = "/"
    if request.method == "POST":
        client = request.remote_addr or "unknown"
        wait = locked_out(client)
        token_ok = hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", ""))
        if wait:
            error = f"Too many attempts. Try again in {wait // 60 + 1} minute(s)."
        elif not token_ok:
            error = "The page expired. Please try again."
        elif hmac.compare_digest(hash_key(request.form.get("key", "")), access_hash()):
            failed_logins.pop(client, None)
            session.clear()
            session.permanent = True
            session["authenticated"] = True
            return redirect(next_url)
        else:
            failed_logins.setdefault(client, []).append(time.time())
            app.logger.warning("Failed sign-in from %s", client)
            error = "Incorrect access key."
    return render_template("login.html", error=error, next_url=next_url), (401 if error else 200)


@app.post("/logout")
def logout():
    if hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", "")):
        session.clear()
    return redirect(url_for("login"))


words = WordService()
notes = NoteService()
weights = WeightService()

PAGES = {
    "/": ("home", "Your words"),
    "/review": ("review", "Review"),
    "/revision": ("revision", "Revision"),
    "/notes": ("notes", "Notes"),
    "/composition": ("composition", "Composition"),
    "/conjugation": ("conjugation", "Conjugation"),
    "/word-check": ("word_check", "Check words"),
}


def page(route: str, template: str):
    def view():
        name, title = PAGES[route]
        return render_template(f"{template}.html", page=name, page_title=title)

    view.__name__ = f"page_{name}"
    return view


for route, (name, _title) in PAGES.items():
    app.add_url_rule(route, endpoint=f"page_{name}", view_func=page(route, name))


def body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Expected a JSON object.")
    return data


# ---- words ---------------------------------------------------------------


@app.get("/api/words")
def api_words():
    items = words.all()
    today = date.today().isoformat()
    return jsonify(
        words=items,
        stats={
            "total": len(items),
            "added_today": sum(1 for item in items if item["added_on"] == today),
            "flagged": sum(1 for item in items if item["check_ai"] == "True"),
        },
    )


@app.post("/api/words")
def api_word_create():
    return jsonify(word=words.create(body())), 201


@app.put("/api/words/<word_id>")
def api_word_update(word_id: str):
    return jsonify(word=words.update(word_id, body()))


@app.delete("/api/words/<word_id>")
def api_word_delete(word_id: str):
    words.delete(word_id)
    return jsonify(ok=True)


@app.patch("/api/words/<word_id>/check")
def api_word_check(word_id: str):
    data = body()
    if not isinstance(data.get("check_ai"), bool):
        raise ApiError("check_ai must be true or false.")
    return jsonify(word=words.set_check(word_id, data["check_ai"]))


@app.post("/api/words/apply")
def api_words_apply():
    changes = body().get("changes")
    return jsonify(words=words.apply_corrections(changes))


@app.get("/api/weights")
def api_weights():
    ids = {word["id"] for word in words.all()}
    return jsonify(weights=weights.load(g.device_code, ids), device=g.device_code)


@app.put("/api/weights/<word_id>")
def api_weight_set(word_id: str):
    if word_id not in {word["id"] for word in words.all()}:
        raise ApiError("Unknown word.", 404)
    value = weights.set(g.device_code, word_id, body().get("weight"))
    return jsonify(id=word_id, weight=value)


@app.delete("/api/weights")
def api_weights_reset():
    weights.reset(g.device_code)
    return jsonify(ok=True)


# ---- AI ------------------------------------------------------------------


@app.post("/api/ai/check")
def api_ai_check():
    provider = AIChecker.provider(body())
    flagged = words.flagged()
    if not flagged:
        raise ApiError("No words are marked for checking.")
    snapshot = [
        {
            "id": item["id"],
            "word": item["word"],
            "reading": item["reading"],
            "meaning": item["meaning"],
        }
        for item in flagged
    ]
    from modules.ai_service import AIService

    try:
        suggestions = AIService.word_suggestions(snapshot, provider)
    except ValueError as error:
        raise ApiError(str(error)) from error
    except OSError as error:
        raise ApiError(f"The AI service could not be reached: {error}", 502) from error

    known = {item["id"] for item in words.all()}
    suggestions = [item for item in suggestions if item["id"] in known]
    words.clear_flags({item["id"] for item in suggestions})
    return jsonify(suggestions=suggestions, checked=len(suggestions))


@app.post("/api/ai/composition")
def api_ai_composition():
    return jsonify(AIChecker.composition(body()))


# ---- conjugation ---------------------------------------------------------


@app.get("/api/conjugation")
def api_conjugation():
    text = request.args.get("text", "")
    if not isinstance(text, str):
        raise ApiError("Text must be a string.")
    if len(text) > 100:
        raise ApiError("That input is too long.")
    mode = 1 if request.args.get("mode") in {"1", "adjective", "noun"} else 0
    return jsonify(ConjugationService.payload(text, mode))


# ---- notes ---------------------------------------------------------------


@app.get("/api/notes")
def api_notes():
    return jsonify(notes=notes.list())


@app.get("/api/notes/<path:name>")
def api_note_read(name: str):
    return jsonify(note=notes.read(name))


@app.post("/api/notes")
def api_note_save():
    return jsonify(note=notes.save(body()))


@app.delete("/api/notes/<path:name>")
def api_note_delete(name: str):
    notes.delete(name)
    return jsonify(ok=True)


# ---- errors --------------------------------------------------------------


@app.errorhandler(ApiError)
def handle_api_error(error: ApiError):
    return jsonify(error=error.message), error.status


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    if request.path.startswith("/api/"):
        return jsonify(error=error.description), error.code or 500
    return render_template("404.html", page="", page_title="Not found"), error.code or 404


@app.errorhandler(Exception)
def handle_unexpected(error: Exception):
    app.logger.exception("Unhandled error on %s", request.path)
    if request.path.startswith("/api/"):
        return jsonify(error="Something went wrong on the server."), 500
    return render_template("404.html", page="", page_title="Not found"), 500


@app.after_request
def access_log(response):
    if request.endpoint != "static":
        app.logger.info(
            "%s %s %s -> %s", request.remote_addr or "unknown", request.method, request.path, response.status_code
        )
    return response


@app.before_request
def identify_device():
    code = request.cookies.get("sa_device", "")
    g.new_device = not WeightService.valid_code(code)
    g.device_code = weights.new_code() if g.new_device else code


@app.after_request
def security_headers(response):
    if getattr(g, "new_device", False) and request.endpoint != "static":
        response.set_cookie(
            "sa_device",
            g.device_code,
            max_age=60 * 60 * 24 * 365 * 5,
            httponly=True,
            samesite="Lax",
            secure=app.config["SESSION_COOKIE_SECURE"],
        )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.endpoint != "static":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def set_access_key() -> None:
    """Prompt for an access key and store only its SHA-256 hash in .env."""
    import getpass

    key = getpass.getpass("New access key: ")
    if len(key) < 8:
        sys.exit("Use at least 8 characters.")
    if key != getpass.getpass("Repeat access key: "):
        sys.exit("The keys did not match.")
    line = f"WEB_ACCESS_KEY_SHA256={hash_key(key)}"
    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    lines = [item for item in lines if not item.startswith("WEB_ACCESS_KEY_SHA256=")]
    env_path.write_text("\n".join([*lines, line]) + "\n", encoding="utf-8")
    print(f"Saved the SHA-256 hash to {env_path}. Restart the server to apply it.")


if __name__ == "__main__":
    if "--set-key" in sys.argv:
        set_access_key()
        sys.exit(0)
    load_dotenv(ROOT / ".env")
    if not HASH_PATTERN.fullmatch(access_hash()):
        print("Warning: WEB_ACCESS_KEY_SHA256 is not set; run `python3 web/app.py --set-key`.")
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5003")),
        debug=os.getenv("FLASK_DEBUG", "") == "1",
    )
