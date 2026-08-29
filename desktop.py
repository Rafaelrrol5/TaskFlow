import ctypes
import logging
import os
import secrets
import socket
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


APP_NAME = "TaskFlow"
HOST = "127.0.0.1"


def resource_path(*parts):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def user_data_path():
    override = os.getenv("TASKFLOW_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def prepare_directories():
    data_dir = user_data_path()
    logs_dir = data_dir / "logs"
    webview_dir = data_dir / "webview"
    for directory in (data_dir, logs_dir, webview_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return data_dir, logs_dir, webview_dir


def configure_logging(logs_dir):
    handler = RotatingFileHandler(
        logs_dir / "taskflow.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def load_or_create_secret(data_dir):
    secret_file = data_dir / "secret.key"
    if secret_file.exists():
        secret = secret_file.read_text(encoding="utf-8").strip()
        if len(secret) >= 32:
            return secret

    secret = secrets.token_urlsafe(48)
    temporary = secret_file.with_suffix(".tmp")
    temporary.write_text(secret, encoding="utf-8")
    os.replace(temporary, secret_file)
    return secret


def configure_environment(data_dir):
    database_path = data_dir / "taskflow.db"
    os.environ["APP_ENV"] = "desktop"
    os.environ["FLASK_DEBUG"] = "0"
    os.environ["TASKFLOW_DESKTOP"] = "1"
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    os.environ["SECRET_KEY"] = load_or_create_secret(data_dir)
    return database_path


def apply_migrations(app):
    from flask_migrate import upgrade

    migrations_dir = resource_path("migrations")
    if not migrations_dir.is_dir():
        raise RuntimeError("Os arquivos de migration não foram encontrados.")
    with app.app_context():
        upgrade(directory=str(migrations_dir))


class LocalServer:
    def __init__(self, app):
        from waitress import create_server

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((HOST, 0))
        listener.listen(100)
        self.port = listener.getsockname()[1]
        self.url = f"http://{HOST}:{self.port}/"
        self.server = create_server(
            app,
            sockets=[listener],
            threads=6,
            clear_untrusted_proxy_headers=True,
        )
        self.thread = threading.Thread(
            target=self.server.run,
            name="taskflow-waitress",
            daemon=True,
        )

    def start(self):
        self.thread.start()

    def wait_until_ready(self, timeout=12):
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            if not self.thread.is_alive():
                raise RuntimeError("O servidor local foi encerrado durante a inicialização.")
            try:
                with urlopen(self.url, timeout=0.5) as response:
                    if response.status == 200:
                        return
            except (OSError, URLError) as error:
                last_error = error
            time.sleep(0.1)
        raise RuntimeError("O servidor local não respondeu a tempo.") from last_error

    def stop(self):
        self.server.close()
        self.server.task_dispatcher.shutdown(cancel_pending=True, timeout=5)
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            logging.getLogger(APP_NAME).warning("A thread do servidor não encerrou no prazo.")


def show_error(message):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except Exception:
        pass


def run():
    data_dir, logs_dir, webview_dir = prepare_directories()
    configure_logging(logs_dir)
    logger = logging.getLogger(APP_NAME)
    server = None

    try:
        database_path = configure_environment(data_dir)
        logger.info("Inicializando o TaskFlow")

        from app import app

        apply_migrations(app)
        logger.info("Banco preparado em %s", database_path)

        server = LocalServer(app)
        server.start()
        server.wait_until_ready()
        logger.info("Servidor local pronto em %s", server.url)

        if "--self-test" in sys.argv:
            logger.info("Autoteste desktop concluído")
            return 0

        import webview

        webview.create_window(
            APP_NAME,
            server.url,
            width=1280,
            height=800,
            min_size=(900, 600),
            resizable=True,
        )
        webview.start(
            debug=False,
            private_mode=False,
            storage_path=str(webview_dir),
        )
        logger.info("Janela encerrada pelo usuário")
        return 0
    except Exception:
        logger.exception("Falha ao iniciar o TaskFlow")
        if "--self-test" not in sys.argv:
            show_error(
                "Não foi possível iniciar o TaskFlow.\n\n"
                f"Consulte o log em:\n{logs_dir / 'taskflow.log'}"
            )
        return 1
    finally:
        if server is not None:
            server.stop()
            logger.info("Servidor local encerrado")


if __name__ == "__main__":
    raise SystemExit(run())

