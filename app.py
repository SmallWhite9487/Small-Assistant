"""Flask front end for Small-Assistant.

Run from the repository root with either:

    python app.py
    flask --app app run --debug

Vocabulary lives in words.csv and notes in Notes/ at the repository root.
Learning data is stored in named profiles under user_data/, and device codes
are kept in each profile CSV.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import re
import secrets
import sys
import threading
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
ROOT = WEB_DIR
LOCALES_DIR = WEB_DIR / "locales"
for path in (str(ROOT),):
    if path not in sys.path:
        sys.path.insert(0, path)

from services import (  # noqa: E402
    AIChecker,
    ApiError,
    ConjugationService,
    GrammarService,
    MachineTranslationService,
    NoteService,
    UserDataService,
    WordService,
)
from modules.ai_service import AIService, AIServiceError  # noqa: E402
from modules.random_number import collect_sources, float_from_sources, integer_from_sources, validate_bounds  # noqa: E402
from modules.second_simplified import to_second_simplified  # noqa: E402

load_dotenv(ROOT / ".env")

app = Flask(__name__)

# Behind a reverse proxy / tunnel every request appears to come from the proxy.
# WEB_PROXY_HOPS is how many trusted proxies sit in front of the app (0 = none,
# so spoofed X-Forwarded-For headers are ignored).
PROXY_HOPS = max(0, int(os.getenv("WEB_PROXY_HOPS", "0") or 0))
if PROXY_HOPS:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=PROXY_HOPS, x_proto=PROXY_HOPS, x_host=PROXY_HOPS)



class CloudflareRealIP:
    """Use Cloudflare's CF-Connecting-IP when the request really came through
    a local cloudflared tunnel.

    cloudflared connects from the same machine, so the socket peer is loopback.
    Cloudflare overwrites the header on the public side, so visitors cannot
    spoof it; the loopback check stops other remote peers from doing so.
    """

    HEADERS = ("HTTP_CF_CONNECTING_IP", "HTTP_TRUE_CLIENT_IP")

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        try:
            peer = ipaddress.ip_address(environ.get("REMOTE_ADDR", ""))
        except ValueError:
            peer = None
        if peer is not None and peer.is_loopback:
            for key in self.HEADERS:
                try:
                    real = ipaddress.ip_address(environ.get(key, "").strip())
                except ValueError:
                    continue
                environ["werkzeug.proxy_fix.orig"] = {"REMOTE_ADDR": environ["REMOTE_ADDR"]}
                environ["REMOTE_ADDR"] = str(real)
                break
        return self.wsgi_app(environ, start_response)


if os.getenv("WEB_TRUST_CLOUDFLARE", "1") != "0":
    app.wsgi_app = CloudflareRealIP(app.wsgi_app)

app.logger.setLevel(logging.INFO)
if not logging.getLogger().handlers and not app.logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("small_assistant").setLevel(logging.INFO)

# Werkzeug's own request line would still print the tunnel's address.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

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


class RequestLogCoalescer:
    def __init__(self, logger: logging.Logger, idle_seconds: float = 0.75) -> None:
        self.logger = logger
        self.idle_seconds = idle_seconds
        self.lock = threading.Lock()
        self.message = ""
        self.count = 0
        self.timer: threading.Timer | None = None

    def record(self, message: str) -> None:
        with self.lock:
            if self.message and self.message != message:
                self._flush_locked()
            self.message = message
            self.count += 1
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.idle_seconds, self.flush)
            self.timer.daemon = True
            self.timer.start()

    def flush(self) -> None:
        with self.lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self.message:
            return
        suffix = f" x{self.count}" if self.count > 1 else ""
        self.logger.info("%s%s", self.message, suffix)
        self.message = ""
        self.count = 0
        self.timer = None


request_log = RequestLogCoalescer(app.logger)


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
            "Access key is not configured. Run `python3 app.py --set-key` "
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
grammar = GrammarService()
notes = NoteService()
user_data = UserDataService()

PAGES = {
    "/": ("home", "Your words"),
    "/review": ("review", "Review"),
    "/revision": ("revision", "Revision"),
    "/counter-quiz": ("counter_quiz", "Mini tests"),
    "/stats": ("stats", "Statistics"),
    "/notes": ("notes", "Notes"),
    "/composition": ("composition", "Composition"),
    "/conjugation": ("conjugation", "Conjugation"),
    "/word-check": ("word_check", "Check words"),
    "/grammar": ("grammar", "Grammar"),
    "/grammar/review": ("grammar_review", "Grammar review"),
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


# ---- localisation -------------------------------------------------------


@app.get("/api/locales/<language>")
def api_locale(language: str):
    if language == "dev":
        with (LOCALES_DIR / "en.json").open(encoding="utf-8") as file:
            return jsonify(translations={key: key for key in app.json.loads(file.read())})
    if language not in {"en", "zh-TW", "zh-CN", "zh-2jian", "ko", "ja"}:
        raise ApiError("Unsupported language.", 404)
    try:
        with (LOCALES_DIR / f"{language}.json").open(encoding="utf-8") as file:
            data = app.json.loads(file.read())
    except (OSError, ValueError) as error:
        raise ApiError(f"Could not load language resources: {error}", 500) from error
    if not isinstance(data, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in data.items()):
        raise ApiError("Language resources are invalid.", 500)
    return jsonify(translations=data)


# ---- learning profiles --------------------------------------------------


@app.get("/api/profiles")
def api_profiles():
    return jsonify(profile=user_data.profile_for_device(g.device_code), profiles=user_data.profiles())


@app.post("/api/profiles")
def api_profile_create():
    profile = user_data.create_profile(body().get("name"), g.device_code)
    return jsonify(profile=profile), 201


@app.post("/api/profiles/select")
def api_profile_select():
    profile = user_data.select_profile(body().get("name"), g.device_code)
    return jsonify(profile=profile)


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


def known_item_ids() -> set[str]:
    return {item["id"] for item in words.all()} | {item["id"] for item in grammar.all()}


@app.get("/api/weights")
def api_weights():
    ids = {word["id"] for word in words.all()}
    return jsonify(weights=user_data.weights(g.device_code, ids), device=g.device_code)


@app.put("/api/weights/<word_id>")
def api_weight_set(word_id: str):
    if word_id not in known_item_ids():
        raise ApiError("Unknown word.", 404)
    value = user_data.set_weight(g.device_code, word_id, body().get("weight"))
    return jsonify(id=word_id, weight=value)


@app.delete("/api/weights")
def api_weights_reset():
    user_data.reset(g.device_code)
    return jsonify(ok=True)


@app.get("/api/study/stats")
def api_study_stats():
    items = words.all()
    return jsonify(user_data.statistics(g.device_code, {item["id"] for item in items}))


@app.post("/api/study/<word_id>/grade")
def api_study_grade(word_id: str):
    if word_id not in known_item_ids():
        raise ApiError("Unknown word.", 404)
    data = body()
    progress = user_data.grade(
        g.device_code,
        word_id,
        data.get("rating"),
        data.get("correct"),
        data.get("duration"),
    )
    return jsonify(progress=progress)


# ---- grammar -------------------------------------------------------------


@app.get("/api/grammar")
def api_grammar():
    items = grammar.all()
    today = date.today().isoformat()
    return jsonify(
        items=items,
        stats={
            "total": len(items),
            "added_today": sum(1 for item in items if item["added_on"] == today),
            "flagged": sum(1 for item in items if item["check_ai"] == "True"),
        },
    )


@app.post("/api/grammar")
def api_grammar_create():
    return jsonify(item=grammar.create(body())), 201


@app.put("/api/grammar/<item_id>")
def api_grammar_update(item_id: str):
    return jsonify(item=grammar.update(item_id, body()))


@app.delete("/api/grammar/<item_id>")
def api_grammar_delete(item_id: str):
    grammar.delete(item_id)
    return jsonify(ok=True)


@app.patch("/api/grammar/<item_id>/check")
def api_grammar_check_flag(item_id: str):
    data = body()
    if not isinstance(data.get("check_ai"), bool):
        raise ApiError("check_ai must be true or false.")
    return jsonify(item=grammar.set_check(item_id, data["check_ai"]))


@app.post("/api/grammar/apply")
def api_grammar_apply():
    return jsonify(items=grammar.apply_corrections(body().get("changes")))


@app.post("/api/ai/grammar-check")
def api_ai_grammar_check():
    data = body()
    provider = AIChecker.provider(data)
    ids = data.get("ids")
    if ids is None:
        queued = [item for item in grammar.all() if item["check_ai"] == "True"]
    else:
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 20
            or not all(isinstance(item_id, str) for item_id in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ApiError("ids must contain between 1 and 20 unique IDs.")
        queued = [item for item in grammar.all() if item["id"] in set(ids)]
        if len(queued) != len(ids):
            raise ApiError("One of the requested grammar points no longer exists.", 409)
    if not queued:
        raise ApiError("No grammar points are marked for checking.")
    queued = queued[:20]
    try:
        suggestions = AIService.grammar_suggestions(
            queued, provider, AIChecker.language_name(data.get("language"))
        )
    except ValueError as error:
        raise ApiError(str(error)) from error
    except OSError as error:
        raise ApiError(f"The AI service could not be reached: {error}", 502) from error
    return jsonify(suggestions=suggestions, checked=len(suggestions))


# ---- AI ------------------------------------------------------------------


@app.post("/api/ai/check")
def api_ai_check():
    data = body()
    provider = AIChecker.provider(data)
    word_ids = data.get("word_ids")
    if word_ids is None:
        queued = words.flagged()
    else:
        if (
            not isinstance(word_ids, list)
            or not word_ids
            or len(word_ids) > AIService.WORD_CHECK_BATCH_SIZE
            or not all(isinstance(word_id, str) for word_id in word_ids)
            or len(set(word_ids)) != len(word_ids)
        ):
            raise ApiError("word_ids must contain between 1 and 50 unique word IDs.")
        requested = set(word_ids)
        queued = [word for word in words.all() if word["id"] in requested]
        if len(queued) != len(requested):
            raise ApiError("One of the requested words no longer exists.", 409)
    if not queued:
        raise ApiError("No words are marked for checking.")
    snapshot = [
        {
            "id": item["id"],
            "word": item["word"],
            "reading": item["reading"],
            "meaning": item["meaning"],
            "part_of_speech": item["part_of_speech"],
        }
        for item in queued
    ]
    try:
        suggestions = AIService.word_suggestions(
            snapshot, provider, AIChecker.language_name(data.get("language"))
        )
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

@app.post("/api/translate/meaning")
def api_translate_meaning():
    data = body()
    return jsonify(translation=MachineTranslationService.meaning(data.get("meaning"), data.get("language")))


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
    cause = error.__cause__
    app.logger.log(
        logging.ERROR if error.status >= 500 else logging.WARNING,
        "%s %s -> %s: %s%s",
        request.method,
        request.path,
        error.status,
        error.message,
        f" (caused by {cause!r})" if cause else "",
        exc_info=(type(cause), cause, cause.__traceback__) if cause and error.status >= 500 else None,
    )
    return jsonify(error=error.message), error.status


@app.errorhandler(AIServiceError)
def handle_ai_error(error: AIServiceError):
    app.logger.error("%s %s -> %s: %s (caused by %r)", request.method, request.path, error.status, error.message, error.__cause__)
    return jsonify(error=error.message), error.status


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    if (error.code or 500) >= 500 or error.code in {400, 403, 405, 413}:
        app.logger.warning("%s %s -> %s %s", request.method, request.path, error.code, error.description)
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
        request_log.record(
            "%s %s %s -> %s"
            % (request.remote_addr or "unknown", request.method, request.path, response.status_code)
        )
    return response


@app.before_request
def identify_device():
    code = request.cookies.get("sa_device", "")
    g.new_device = not UserDataService.valid_code(code)
    g.device_code = user_data.new_code() if g.new_device else code


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

@app.post("/api/ping/random")
def ping_random():
    data = body()
    minimum = data.get("minimum", 0)
    maximum = data.get("maximum", 1)
    number_type = data.get("number_type", "int")
    try:
        validate_bounds(minimum, maximum, number_type)
    except ValueError as error:
        raise ApiError(str(error)) from error
    sources, warnings = collect_sources(request.remote_addr)
    for warning in warnings:
        app.logger.warning("Random number source: %s", warning)
    generate = integer_from_sources if number_type == "int" else float_from_sources
    return jsonify(
        value=generate(sources, minimum, maximum),
        sources=list(sources),
        warnings=warnings,
    )


@app.get("/ping")
def ping():
    if request.args.get("probe") == "1":
        return jsonify(ip=request.remote_addr, pong=True)
    return render_template(
        "ping.html", page="", page_title="Connection test", user_ip=request.remote_addr
    )

if __name__ == "__main__":
    if "--set-key" in sys.argv:
        set_access_key()
        sys.exit(0)
    load_dotenv(ROOT / ".env")
    if not HASH_PATTERN.fullmatch(access_hash()):
        print("Warning: WEB_ACCESS_KEY_SHA256 is not set; run `python3 app.py --set-key`.")
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5003")),
        debug=os.getenv("FLASK_DEBUG", "") == "1",
    )
