from .esicup import load_esicup
from .sparrow import load_sparrow


def load_any(path, **kw):
    """확장자로 형식을 판별해 Instance로 읽는다."""
    import json
    from pathlib import Path

    from ..model import Instance

    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".xml":
        return load_esicup(p)
    if ext == ".dxf":
        from .dxf_reader import load_dxf

        return load_dxf(p, **kw)
    if ext == ".svg":
        from .svg_reader import load_svg

        return load_svg(p, **kw)
    if ext == ".json":
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("format", "").startswith("nesting-instance/"):
            return Instance.from_dict(d)
        if "strip_height" in d:
            return load_sparrow(p, **{k: v for k, v in kw.items() if k == "continuous_step"})
    raise ValueError(f"지원하지 않는 형식: {p.name}")


__all__ = ["load_sparrow", "load_esicup", "load_any"]
