import os


def _load_dotenv(path):
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _get_data_dir():
    data_dir = os.environ.get("DATA_DIR", "").strip()
    if not data_dir:
        data_dir = os.path.join(BASE_DIR, "instance")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


DATA_DIR = _get_data_dir()


def _build_default_db_uri(data_dir):
    db_path = os.path.join(data_dir, "database.db")
    db_path = db_path.replace(os.sep, "/")
    return f"sqlite:///{db_path}"

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    DATA_DIR = DATA_DIR
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or _build_default_db_uri(DATA_DIR)
    UPLOAD_ROOT = os.environ.get('UPLOAD_ROOT') or os.path.join(DATA_DIR, "uploads")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
