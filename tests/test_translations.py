"""Consistency checks of the interface texts."""

import json
from pathlib import Path
from typing import Any

import pytest

from deep_cube_protocol import Intensity, Program

COMPONENT_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "deep_cube"
TRANSLATIONS = sorted((COMPONENT_DIR / "translations").glob("*.json"))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _keys(node: Any, prefix: str = "") -> set[str]:
    """Return the dotted paths of all strings in a translation tree."""
    if not isinstance(node, dict):
        return {prefix}
    return {
        key
        for name, child in node.items()
        for key in _keys(child, f"{prefix}.{name}" if prefix else name)
    }


def test_required_languages_exist() -> None:
    """English and Russian are always shipped."""
    assert {"en.json", "ru.json"} <= {path.name for path in TRANSLATIONS}


def test_english_matches_strings() -> None:
    """Home Assistant reads en.json for custom integrations; keep it in sync."""
    assert _load(COMPONENT_DIR / "translations" / "en.json") == _load(
        COMPONENT_DIR / "strings.json"
    )


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda path: path.stem)
def test_translation_is_complete(path: Path) -> None:
    """Every language has exactly the keys of strings.json."""
    assert _keys(_load(path)) == _keys(_load(COMPONENT_DIR / "strings.json"))


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda path: path.stem)
def test_options_are_translated(path: Path) -> None:
    """Every program and intensity has a name in every language."""
    strings = _load(path)
    programs = {program.value for program in Program}
    intensities = {intensity.value for intensity in Intensity}
    assert set(strings["entity"]["select"]["program"]["state"]) == programs
    assert set(strings["selector"]["program"]["options"]) == programs
    assert set(strings["entity"]["select"]["intensity"]["state"]) == intensities
    assert set(strings["selector"]["intensity"]["options"]) == intensities
    assert programs < set(strings["entity"]["sensor"]["current_program"]["state"])
