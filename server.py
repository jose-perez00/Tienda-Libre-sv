import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DB_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "tablas" / "usuarios.db"))
PBKDF2_ITERATIONS = 310_000
SESSION_COOKIE = "tienda_sesion"
SESSION_MAX_AGE = 7 * 24 * 3600  # 7 días


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    with connect_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_email TEXT NOT NULL COLLATE NOCASE,
            product_id TEXT NOT NULL DEFAULT '',
            product TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            attended INTEGER NOT NULL DEFAULT 0,
            buyer_id TEXT NOT NULL DEFAULT ''
        )""")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_seller ON messages (seller_email, created_at DESC)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_unique "
            "ON messages (seller_email, product_id, buyer_id)"
        )


def hash_token(token):
    """Las sesiones se guardan hasheadas: la cookie nunca se almacena en claro."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_session_cookie(header):
    """Extrae el token de sesión de la cabecera Cookie."""
    for parte in str(header or "").split(";"):
        nombre, _, valor = parte.strip().partition("=")
        if nombre == SESSION_COOKIE and valor:
            return valor
    return ""


class StoreHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".webmanifest": "application/manifest+json",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Solicitud inválida.")
        if length <= 0 or length > 65536:
            raise ValueError("La solicitud está vacía o es demasiado grande.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("El formato de la solicitud no es válido.")
        if not isinstance(data, dict):
            raise ValueError("El formato de la solicitud no es válido.")
        return data

    def current_user(self):
        """Devuelve la fila del usuario dueño de la sesión, o None."""
        token = parse_session_cookie(self.headers.get("Cookie"))
        if not token:
            return None
        with connect_db() as conn:
            row = conn.execute(
                "SELECT u.id, u.name, u.email FROM sessions s "
                "JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.expires_at > ?",
                (hash_token(token), int(datetime.now(timezone.utc).timestamp())),
            ).fetchone()
        return row

    def start_session(self, user_id):
        """Crea una sesión y devuelve la cabecera Set-Cookie correspondiente."""
        token = secrets.token_urlsafe(32)
        expira = int(datetime.now(timezone.utc).timestamp()) + SESSION_MAX_AGE
        with connect_db() as conn:
            conn.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (int(datetime.now(timezone.utc).timestamp()),),
            )
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?,?,?)",
                (hash_token(token), user_id, expira),
            )
        return (
            f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; "
            f"Max-Age={SESSION_MAX_AGE}"
        )

    def end_session(self):
        """Invalida la sesión actual y devuelve la cabecera Set-Cookie de borrado."""
        token = parse_session_cookie(self.headers.get("Cookie"))
        if token:
            with connect_db() as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    def do_POST(self):
        path = urlsplit(self.path).path

        if path == "/api/logout":
            cookie = self.end_session()
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/messages":
            self.handle_create_message()
            return

        if path.startswith("/api/messages/") and path.endswith("/attended"):
            self.handle_mark_attended(path)
            return

        if path not in ("/api/register", "/api/login"):
            self.send_json(404, {"error": "Ruta de API no encontrada."})
            return
        try:
            data = self.read_json()
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
            return

        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            self.send_json(400, {"error": "Escribe un correo electrónico válido."})
            return
        if path == "/api/register":
            name = str(data.get("name", "")).strip()
            if not name or len(name) > 120:
                self.send_json(400, {"error": "Escribe un nombre válido."})
                return
            if len(password) < 6 or len(password) > 1024:
                self.send_json(400, {"error": "La contraseña debe tener al menos 6 caracteres."})
                return
            salt = os.urandom(16)
            try:
                with connect_db() as conn:
                    cursor = conn.execute(
                        "INSERT INTO users (name,email,password_hash,password_salt,created_at) VALUES (?,?,?,?,?)",
                        (name, email, password_hash(password, salt), salt.hex(), now_iso())
                    )
                    user_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                self.send_json(409, {"error": "Ya existe una cuenta con ese correo electrónico."})
                return
            self.send_user_session(201, user_id, name, email)
            return

        with connect_db() as conn:
            user = conn.execute(
                "SELECT id,name,email,password_hash,password_salt FROM users WHERE email=? COLLATE NOCASE",
                (email,)
            ).fetchone()
        if not user:
            self.send_json(401, {"error": "Correo o contraseña incorrectos."})
            return
        try:
            salt = bytes.fromhex(user["password_salt"])
        except ValueError:
            self.send_json(500, {"error": "No se pudo validar la cuenta. Contacta al administrador."})
            return
        candidate = password_hash(password, salt)
        if not hmac.compare_digest(candidate, user["password_hash"]):
            self.send_json(401, {"error": "Correo o contraseña incorrectos."})
            return
        self.send_user_session(200, user["id"], user["name"], user["email"])

    def send_user_session(self, status, user_id, name, email):
        """Responde con el usuario y arranca la sesión por cookie."""
        cookie = self.start_session(user_id)
        body = json.dumps(
            {"user": {"id": user_id, "name": name, "email": email}}, ensure_ascii=False
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def handle_create_message(self):
        """POST /api/messages: registra la consulta de un comprador."""
        try:
            data = self.read_json()
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
            return

        seller_email = str(data.get("seller_email", "")).strip().lower()
        product_id = str(data.get("product_id", "")).strip()
        buyer_id = str(data.get("buyer_id", "")).strip()
        product = str(data.get("product", "")).strip()
        message = str(data.get("message", "")).strip()
        try:
            price = float(data.get("price", 0) or 0)
        except (TypeError, ValueError):
            price = 0.0

        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", seller_email) or len(seller_email) > 254:
            self.send_json(400, {"error": "El vendedor indicado no es válido."})
            return
        if not product_id or len(product_id) > 200:
            self.send_json(400, {"error": "No se pudo identificar el producto."})
            return
        if not buyer_id or len(buyer_id) > 120:
            self.send_json(400, {"error": "No se pudo identificar al comprador."})
            return
        if not message or len(message) > 1000:
            self.send_json(400, {"error": "El mensaje está vacío o es demasiado largo."})
            return

        with connect_db() as conn:
            existe = conn.execute(
                "SELECT 1 FROM users WHERE email=? COLLATE NOCASE", (seller_email,)
            ).fetchone()
            if not existe:
                self.send_json(404, {"error": "El vendedor no tiene una cuenta registrada."})
                return
            try:
                conn.execute(
                    "INSERT INTO messages "
                    "(seller_email,product_id,buyer_id,product,price,message,attended,created_at) "
                    "VALUES (?,?,?,?,?,?,0,?)",
                    (seller_email, product_id, buyer_id, product[:200], price, message, now_iso()),
                )
            except sqlite3.IntegrityError:
                self.send_json(200, {"ok": True, "duplicate": True, "email_sent": False})
                return

        self.send_json(201, {"ok": True, "duplicate": False, "email_sent": False,
                             "email_status": "not_configured"})

    def handle_list_messages(self):
        """GET /api/messages: bandeja del vendedor autenticado."""
        user = self.current_user()
        if not user:
            self.send_json(401, {"error": "Inicia sesión para ver tus mensajes."})
            return
        with connect_db() as conn:
            filas = conn.execute(
                "SELECT id,product,price,message,attended,created_at FROM messages "
                "WHERE seller_email=? COLLATE NOCASE ORDER BY created_at DESC, id DESC",
                (user["email"],),
            ).fetchall()
        mensajes = [
            {
                "id": fila["id"],
                "product": fila["product"],
                "price": fila["price"],
                "message": fila["message"],
                "attended": bool(fila["attended"]),
                "created_at": fila["created_at"],
            }
            for fila in filas
        ]
        self.send_json(200, {"messages": mensajes})

    def handle_mark_attended(self, path):
        """POST /api/messages/<id>/attended"""
        user = self.current_user()
        if not user:
            self.send_json(401, {"error": "Inicia sesión para gestionar tus mensajes."})
            return
        message_id = path[len("/api/messages/"):-len("/attended")].strip("/")
        if not message_id.isdigit():
            self.send_json(400, {"error": "Mensaje inválido."})
            return
        with connect_db() as conn:
            cursor = conn.execute(
                "UPDATE messages SET attended=1 WHERE id=? AND seller_email=? COLLATE NOCASE",
                (int(message_id), user["email"]),
            )
        if cursor.rowcount == 0:
            self.send_json(404, {"error": "Mensaje no encontrado."})
            return
        self.send_json(200, {"ok": True})

    def handle_delete_message(self, path):
        """DELETE /api/messages/<id>"""
        user = self.current_user()
        if not user:
            self.send_json(401, {"error": "Inicia sesión para borrar mensajes."})
            return
        message_id = path[len("/api/messages/"):].strip("/")
        if not message_id.isdigit():
            self.send_json(400, {"error": "Mensaje inválido."})
            return
        with connect_db() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE id=? AND seller_email=? COLLATE NOCASE",
                (int(message_id), user["email"]),
            )
        if cursor.rowcount == 0:
            self.send_json(404, {"error": "Mensaje no encontrado."})
            return
        self.send_json(200, {"ok": True})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            if path == "/api/session":
                user = self.current_user()
                if not user:
                    self.send_json(401, {"error": "No hay sesión activa."})
                    return
                self.send_json(200, {"user": {"id": user["id"], "name": user["name"], "email": user["email"]}})
                return
            if path == "/api/messages":
                self.handle_list_messages()
                return
            self.send_json(404, {"error": "Ruta de API no encontrada."})
            return
        super().do_GET()

    def do_DELETE(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/messages/") and not path.endswith("/attended"):
            self.handle_delete_message(path)
            return
        self.send_json(404, {"error": "Ruta de API no encontrada."})

    def send_head(self):
        requested_path = urlsplit(self.path).path
        blocked_suffixes = (".py", ".php", ".db", ".sqlite", ".sqlite3", ".docx")
        if (requested_path == "/server.py" or requested_path.startswith("/tablas/") or requested_path == "/tablas"
                or (any(part.startswith(".") for part in requested_path.split("/"))
                    and requested_path != "/.well-known/assetlinks.json")
                or requested_path.lower().endswith(blocked_suffixes)):
            self.send_error(404)
            return None
        if requested_path.startswith("/api/"):
            self.send_error(404, "Ruta de API no encontrada.")
            return None
        return super().send_head()


if __name__ == "__main__":
    initialize_db()
    server = ThreadingHTTPServer((HOST, PORT), StoreHandler)
    print(f"Tienda Libre disponible en {HOST}:{PORT}")
    print(f"Base de datos SQLite: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()
