"""Saving and loading project files: atomic writes, rotating backups, checked loading."""
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .model import Project, ProjectFileError, project_from_dict, project_to_dict

BACKUPS_KEPT = 10


def backup_dir(path: Path) -> Path:
    return path.parent / f"{path.stem}_yedekler"


def save_project(project: Project, path, backups: int = BACKUPS_KEPT) -> None:
    """Write atomically: a crash or power cut mid-save never leaves a half-written project file."""
    path = Path(path)
    data = json.dumps(project_to_dict(project), ensure_ascii=False, indent=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and backups > 0:
        bdir = backup_dir(path)
        bdir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, bdir / f"{path.stem}-{stamp}{path.suffix}")
        old = sorted(bdir.glob(f"{path.stem}-*{path.suffix}"))
        for extra in old[:-backups]:
            extra.unlink()
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_project(path) -> Project:
    """Read and check a project file; any problem raises ProjectFileError with a Turkish message."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ProjectFileError(f"Proje dosyası bulunamadı: {path}") from None
    except UnicodeDecodeError:
        raise ProjectFileError("Proje dosyası okunamadı: dosya bir ders programı projesi değil.") from None
    except OSError as e:
        raise ProjectFileError(f"Proje dosyası açılamadı: {e.strerror}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProjectFileError(f"Proje dosyası bozuk (satır {e.lineno}). Yedeklerden birini açmayı deneyin: "
                               f"{backup_dir(path)}") from None
    return project_from_dict(data)
