from pathlib import Path
import os


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Preserve already-defined environment variables.
        os.environ.setdefault(key, value)


def pytest_configure() -> None:
    root = Path(__file__).resolve().parents[1]
    _load_dotenv(root / ".env")

    # Ensure tests have a local database URL even when .env is missing.
    os.environ.setdefault("DATABASE_URL", "sqlite:///./livros.db")
    os.environ.setdefault("MEU_USUARIO", "lucas")
    os.environ.setdefault("MINHA_SENHA", "123456")
