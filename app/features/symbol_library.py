"""Symbol library feature slice."""

from pathlib import Path
from typing import Iterable, List, Tuple


def save_symbol_templates(symbol_dir: Path, uploaded_files: Iterable) -> List[str]:
    """Save uploaded symbol templates and return saved filenames."""
    symbol_dir.mkdir(parents=True, exist_ok=True)
    saved: List[str] = []
    for sym_file in uploaded_files:
        save_path = symbol_dir / sym_file.name
        with open(save_path, "wb") as f:
            f.write(sym_file.getbuffer())
        saved.append(sym_file.name)
    return saved


def list_symbol_templates(symbol_dir: Path) -> List[Path]:
    """List all PNG symbol templates in library."""
    symbol_dir.mkdir(parents=True, exist_ok=True)
    return sorted(symbol_dir.glob("*.png"))


def delete_symbol_template(symbol_path: Path) -> Tuple[bool, str]:
    """Delete one symbol template."""
    if not symbol_path.exists():
        return False, "檔案不存在"
    symbol_path.unlink(missing_ok=True)
    return True, "已刪除"
