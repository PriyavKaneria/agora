from __future__ import annotations

from pathlib import Path
import tomllib

from orchestrator.models import ProjectProfile


TEXT_FILE_EXTS = {".md", ".txt", ".markdown"}
IMAGE_FILE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def load_project_profile(project_dir: str) -> ProjectProfile:
    base = Path(project_dir)
    if not base.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    profile_path = base / "profile.toml"
    profile = {}
    if profile_path.exists():
        with profile_path.open("rb") as f:
            profile = tomllib.load(f)

    notes_parts: list[str] = []
    image_paths: list[str] = []

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in TEXT_FILE_EXTS:
            try:
                notes_parts.append(f"# File: {path.relative_to(base)}\n{path.read_text(encoding='utf-8')}")
            except UnicodeDecodeError:
                continue
        elif suffix in IMAGE_FILE_EXTS:
            image_paths.append(str(path))

    product_name = profile.get("product_name", base.name)
    target_audience = profile.get("target_audience", "General users looking for help with a specific problem.")
    value_props = profile.get("value_props", [])
    key_phrases = profile.get("key_phrases", [])
    forbidden_claims = profile.get("forbidden_claims", [])

    return ProjectProfile(
        project_id=base.name,
        product_name=product_name,
        target_audience=target_audience,
        value_props=value_props,
        key_phrases=key_phrases,
        forbidden_claims=forbidden_claims,
        source_notes="\n\n".join(notes_parts)[:60_000],
        image_paths=image_paths,
    )

