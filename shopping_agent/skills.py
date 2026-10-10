"""Load only fixed, versioned package resources, never model-selected paths."""

from importlib.resources import files


def load_skills() -> str:
    root = files("shopping_agent").joinpath("skills")
    return "\n\n".join(
        root.joinpath(name + ".md").read_text(encoding="utf-8")
        for name in ("consultar", "altas", "cambios", "propuestas")
    )
