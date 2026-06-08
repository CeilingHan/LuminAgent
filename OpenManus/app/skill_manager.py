"""
Skill manager — user-defined workflow templates stored as Markdown files.

Skills are prompt templates + tool specifications that get injected into the
Agent's system prompt when a user's input matches trigger keywords.

Storage: data/skills/*.md (YAML frontmatter + Markdown body)
"""
import re
import threading
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.logger import logger

# ── Skill definition model (lightweight dict-based) ──
# Each skill is a dict:
# {
#   "name": str,               # unique slug (filename without .md)
#   "description": str,         # one-line — used for matching
#   "tools": [str],            # recommended tools
#   "trigger_keywords": [str], # when any match user input, this skill activates
#   "content": str,            # Markdown body — injected as system prompt
#   "created_at": str,
#   "updated_at": str,
#   "source_url": str or None, # if loaded from URL, the source
# }


class SkillManager:
    """Singleton manager for user-defined skills.

    Skills are stored as Markdown files:
    - YAML frontmatter: name, description, tools, trigger_keywords
    - Body: the system prompt content
    """

    _instance: Optional["SkillManager"] = None
    _lock = threading.Lock()

    def __new__(cls, skills_dir: Optional[Path] = None) -> "SkillManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, skills_dir: Optional[Path] = None):
        if hasattr(self, "_initialized") and self._initialized:
            if skills_dir:
                self._dir = skills_dir
                self._dir.mkdir(parents=True, exist_ok=True)
                self._cache: dict[str, dict] = {}
                self._load_all()
            return

        self._initialized = True
        self._dir = skills_dir or (Path(__file__).resolve().parent.parent / "data" / "skills")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict] = {}
        self._load_all()

    # ── Load / Scan ────────────────────────────────────────

    def _load_all(self) -> None:
        """Scan the skills directory and load all .md files into cache."""
        self._cache = {}
        if not self._dir.exists():
            return
        for fp in sorted(self._dir.glob("*.md")):
            try:
                skill = self._parse_file(fp)
                if skill:
                    self._cache[skill["name"]] = skill
            except Exception as e:
                logger.warning(f"Failed to load skill {fp.name}: {e}")
        logger.info(f"Loaded {len(self._cache)} skills from {self._dir}")

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter. Returns (frontmatter, body)."""
        if not content.startswith("---"):
            return {}, content
        lines = content.split("\n")
        fm_lines = []
        body_start = 0
        found = False
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                body_start = i + 1
                found = True
                break
            fm_lines.append(line)
            if i > 40:
                break
        fm_text = "\n".join(fm_lines)
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            fm = {}
        body = "\n".join(lines[body_start:]) if found else content
        return fm, body

    def _parse_file(self, filepath: Path) -> Optional[dict]:
        """Parse a single .md skill file."""
        raw = filepath.read_text(encoding="utf-8")
        fm, body = self._parse_frontmatter(raw)
        name = fm.get("name", filepath.stem)
        return {
            "name": self._safe_name(name),
            "description": str(fm.get("description", "")),
            "tools": fm.get("tools", []),
            "trigger_keywords": [k.strip().lower() for k in fm.get("trigger_keywords", [])],
            "content": body.strip(),
            "created_at": fm.get("created_at", datetime.now().isoformat()),
            "updated_at": fm.get("updated_at", datetime.now().isoformat()),
            "source_url": fm.get("source_url"),
        }

    def _build_frontmatter(self, skill: dict) -> str:
        """Build YAML frontmatter string from a skill dict."""
        fm = {
            "name": skill["name"],
            "description": skill["description"],
            "tools": skill.get("tools", []),
            "trigger_keywords": skill.get("trigger_keywords", []),
            "updated_at": skill.get("updated_at", datetime.now().isoformat()),
            "created_at": skill.get("created_at", datetime.now().isoformat()),
        }
        if skill.get("source_url"):
            fm["source_url"] = skill["source_url"]
        return yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # ── CRUD ───────────────────────────────────────────────

    def list_all(self) -> list[dict]:
        """Return all skills (from cache)."""
        self._load_all()  # Refresh from disk
        return sorted(self._cache.values(), key=lambda s: s["updated_at"], reverse=True)

    def get(self, name: str) -> Optional[dict]:
        """Get a single skill by name."""
        name = self._safe_name(name)
        self._load_all()
        return self._cache.get(name)

    def create_or_update(self, skill_data: dict) -> dict:
        """Create or update a skill. skill_data should have at minimum: name, content."""
        name = self._safe_name(skill_data.get("name", ""))
        if not name:
            raise ValueError("name is required")

        now = datetime.now().isoformat()

        existing = self._cache.get(name)
        if existing:
            # Update
            existing["description"] = skill_data.get("description", existing["description"])
            existing["tools"] = skill_data.get("tools", existing["tools"])
            existing["trigger_keywords"] = [
                k.strip().lower()
                for k in skill_data.get("trigger_keywords", existing.get("trigger_keywords", []))
            ]
            existing["content"] = skill_data.get("content", existing["content"])
            existing["updated_at"] = now
            skill = existing
            action = "updated"
        else:
            skill = {
                "name": name,
                "description": skill_data.get("description", ""),
                "tools": skill_data.get("tools", []),
                "trigger_keywords": [
                    k.strip().lower()
                    for k in skill_data.get("trigger_keywords", [])
                ],
                "content": skill_data.get("content", ""),
                "created_at": now,
                "updated_at": now,
                "source_url": skill_data.get("source_url"),
            }
            action = "created"

        # Write file
        fm = self._build_frontmatter(skill)
        file_content = f"---\n{fm}---\n\n{skill['content'].strip()}\n"
        filepath = self._dir / f"{name}.md"
        filepath.write_text(file_content, encoding="utf-8")

        self._cache[name] = skill
        logger.info(f"Skill {action}: {name}")
        skill["action"] = action
        return skill

    def delete(self, name: str) -> bool:
        """Delete a skill file and remove from cache."""
        name = self._safe_name(name)
        filepath = self._dir / f"{name}.md"
        existed = filepath.exists()
        if existed:
            filepath.unlink()
        self._cache.pop(name, None)
        if existed:
            logger.info(f"Skill deleted: {name}")
        return existed

    # ── URL Loading ────────────────────────────────────────

    async def load_from_url(self, url: str) -> dict:
        """Download a skill markdown file from a URL and register it."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status} fetching {url}")
                raw = await resp.text()

        fm, body = self._parse_frontmatter(raw)
        name = fm.get("name") or self._safe_name(url.rsplit("/", 1)[-1].replace(".md", ""))
        if not name:
            raise ValueError("Could not determine skill name from URL or frontmatter")

        return self.create_or_update({
            "name": name,
            "description": fm.get("description", f"Loaded from {url}"),
            "tools": fm.get("tools", []),
            "trigger_keywords": fm.get("trigger_keywords", []),
            "content": body.strip(),
            "source_url": url,
        })

    # ── Matching ───────────────────────────────────────────

    def find_matching(self, user_input: str) -> list[dict]:
        """Find skills whose trigger_keywords match the user's input.

        Returns matching skills sorted by keyword match count (descending).
        """
        input_lower = user_input.lower()
        matches = []
        for skill in self._cache.values():
            triggers = skill.get("trigger_keywords", [])
            if not triggers:
                continue
            # Count how many trigger keywords match
            hit_count = sum(1 for kw in triggers if kw in input_lower)
            if hit_count > 0:
                matches.append((hit_count, skill))

        # Sort by match count descending
        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:3]]  # top 3

    def get_matching_context(self, user_input: str) -> str:
        """Get skill system prompt context for matching skills.

        Returns a formatted string to inject into the system prompt,
        or empty string if no skills match.
        """
        matching = self.find_matching(user_input)
        if not matching:
            return ""

        parts = ["<active-skills>\n"]
        for skill in matching:
            parts.append(f"<!-- Skill: {skill['name']} — {skill['description']} -->\n")
            parts.append(skill["content"])
            parts.append("\n\n")
        parts.append("</active-skills>\n")
        return "".join(parts)

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _safe_name(name: str) -> str:
        """Sanitize a name into a safe filename slug."""
        name = name.replace("\\", "/").split("/")[-1]
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "-", name)
        safe = re.sub(r"-+", "-", safe).strip("-")
        return safe or "untitled"


# ── Singleton accessor ──

_skill_manager: Optional[SkillManager] = None


def get_skill_manager(skills_dir: Optional[Path] = None) -> SkillManager:
    """Get or create the singleton SkillManager."""
    global _skill_manager
    if _skill_manager is None:
        if skills_dir is None:
            skills_dir = Path(__file__).resolve().parent.parent / "data" / "skills"
        _skill_manager = SkillManager(skills_dir)
    return _skill_manager
