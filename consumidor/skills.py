"""Skills: catálogo (nome e descrição de cada SKILL.md) e a ferramenta que carrega uma skill sob demanda."""

from pathlib import Path

import yaml
from langchain.tools import tool

from . import config


def read_skills(skills_dir: Path = config.SKILLS_DIR) -> dict[str, dict]:
    skills = {}
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        _, front, body = path.read_text(encoding="utf-8").split("---", 2)
        meta = yaml.safe_load(front)
        skills[meta["name"]] = {"description": meta["description"], "body": body.strip()}
    return skills


def catalog(skills: dict[str, dict]) -> str:
    return "\n".join(f"- {name}: {info['description']}" for name, info in skills.items())


def make_load_skill(skills: dict[str, dict]):
    @tool
    def load_skill(name: str) -> str:
        """Carrega as instruções completas de uma skill do catálogo pelo nome. Chame antes de começar a tarefa da skill."""
        if name not in skills:
            return f"Skill '{name}' não existe. Skills disponíveis: {', '.join(skills)}."
        return f"# Skill {name}\n\n{skills[name]['body']}"

    return load_skill
