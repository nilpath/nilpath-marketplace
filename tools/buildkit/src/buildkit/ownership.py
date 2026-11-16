"""Build-owned paths and byte/mode snapshots, without renderer dependencies."""

from pathlib import Path
import stat


REGISTRIES = (
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    ".github/plugin/marketplace.json",
)
OWNED_PATHS = (Path("dist"), *(Path(p) for p in REGISTRIES))


def owns(path: str) -> bool:
    return any(path == str(p) or path.startswith(str(p) + "/") for p in OWNED_PATHS)


def snapshot(root: Path) -> dict[str, tuple[str, bytes]]:
    result = {}
    for rel in OWNED_PATHS:
        target = root / rel
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Build-owned path escape: {target}")
        paths = sorted(target.rglob("*")) if target.is_dir() else [target]
        for path in paths:
            if path.is_symlink():
                raise ValueError(f"Build-owned symlink: {path}")
            if not path.exists() or path.is_dir():
                continue
            mode = path.stat().st_mode
            if not stat.S_ISREG(mode):
                raise ValueError(f"Build-owned nonregular file: {path}")
            result[path.relative_to(root).as_posix()] = (
                "100755" if mode & 0o111 else "100644", path.read_bytes(),
            )
    return result
