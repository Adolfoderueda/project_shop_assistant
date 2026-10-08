import re
from importlib.resources import files
from pathlib import Path

import pytest

from shopping_agent.skills import load_skills


def test_skill_resources_are_fixed_and_attributed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    guides = [files('shopping_agent').joinpath('skills', name + '.md').read_text(encoding='utf-8')
              for name in ('consultar', 'altas', 'cambios', 'propuestas')]
    assert load_skills() == '\n\n'.join(guides)
    for guide in guides:
        assert 0 < len(guide.split()) <= 500
        assert not re.search(r'(?i)(ejecuta comandos|escribe (?:archivos|ficheros)|subprocess|INSERT INTO)', guide)
    with pytest.raises(TypeError):
        load_skills('untrusted-path')
    root = Path(__file__).resolve().parents[1]
    notice = (root / 'third_party/shopping-list-skill/NOTICE.md').read_text(encoding='utf-8')
    license_text = (root / 'third_party/shopping-list-skill/LICENSE').read_text(encoding='utf-8')
    assert 'https://github.com/ajeenkya/shopping-list-skill' in notice
    assert 'e37617947cd8e8aa095c5a358c9005bb2ac1c6fd' in notice
    assert 'references/commands.md' in notice and 'MIT' in notice
    assert 'Copyright (c) 2026 Ajeenkya Bhatalkar' in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text
