"""
Persistent memory manager — file-based Markdown + YAML frontmatter,
referencing Claude Code's memory design.

Hot layer:  MEMORY.md (index) — always loaded into context (~60 lines)
Warm layer: memory/*.md (topic files) — loaded on demand (≤60 lines each)
Cold layer: data/sessions/*.json — search-only archives
"""
import re
import threading
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.logger import logger
from app.schema import MemoryItem, MemoryType

# ── Constants ──

MAX_INDEX_LINES = 80         # hard cap for MEMORY.md
MAX_FILE_LINES = 60          # soft cap per topic file
MAX_FRONTMATTER_LINES = 30   # max lines to scan for YAML frontmatter
INDEX_HEADER = "# LuminAgent Memory Index\n\n"


class MemoryManager:
    """Singleton manager for persistent file-based memory.

    Lifecycle:
    1. At session start: load_index() reads MEMORY.md
    2. During session: read_memory() / write_memory() / delete_memory()
    3. At session end: extract_from_conversation() auto-captures new facts
    4. Periodically: consolidate() merges & prunes
    """

    _instance: Optional["MemoryManager"] = None
    _lock = threading.Lock()

    def __new__(cls, memory_dir: Optional[Path] = None) -> "MemoryManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, memory_dir: Optional[Path] = None):
        if hasattr(self, "_initialized") and self._initialized:
            if memory_dir and memory_dir != self._dir:
                # Re-init with new dir
                self._dir = memory_dir
                self._dir.mkdir(parents=True, exist_ok=True)
                self._index: list[MemoryItem] = []
                self.load_index()
            return

        self._initialized = True
        self._dir = memory_dir or (Path(__file__).resolve().parent.parent / "data" / "memory")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index: list[MemoryItem] = []
        self.load_index()

    # ── Index management ────────────────────────────────────

    def load_index(self) -> list[MemoryItem]:
        """Parse MEMORY.md → list of MemoryItem (stubs — description only).

        Format:
            - [Title](file.md) — one-line description
        """
        index_path = self._dir / "MEMORY.md"
        if not index_path.exists():
            self._index = []
            return []

        items = []
        try:
            content = index_path.read_text(encoding="utf-8")
            # Match: - [Title](file.md) — description
            pattern = re.compile(r"^\s*-\s*\[([^\]]+)\]\(([^)]+\.md)\)\s*[—\-]\s*(.+)$", re.MULTILINE)
            for m in pattern.finditer(content):
                title = m.group(1).strip()
                filename = m.group(2).strip()
                desc = m.group(3).strip()
                name = filename.replace(".md", "")
                items.append(MemoryItem(
                    name=name,
                    description=desc,
                    type=MemoryType.PROJECT,
                    content="",
                    metadata={"title": title},
                ))
        except Exception as e:
            logger.warning(f"Failed to parse MEMORY.md: {e}")

        self._index = items
        return items

    def write_index(self) -> None:
        """Write self._index back to MEMORY.md. Trims to MAX_INDEX_LINES."""
        lines = [INDEX_HEADER]
        for item in self._index:
            title = item.metadata.get("title", item.name.replace("-", " ").title())
            lines.append(f"- [{title}]({item.name}.md) — {item.description}\n")

        # Trim to limit
        if len(lines) > MAX_INDEX_LINES:
            lines = lines[:MAX_INDEX_LINES]
            lines.append(f"\n<!-- Index trimmed at {MAX_INDEX_LINES} lines. Older memories archived. -->\n")

        index_path = self._dir / "MEMORY.md"
        index_path.write_text("".join(lines), encoding="utf-8")

    def add_to_index(self, item: MemoryItem) -> None:
        """Add or update an entry in the index. Deduplicates by name."""
        # Remove existing entry with same name
        self._index = [i for i in self._index if i.name != item.name]
        self._index.append(item)
        # Sort by updated_at descending
        self._index.sort(key=lambda i: i.updated_at, reverse=True)
        self.write_index()

    def remove_from_index(self, name: str) -> None:
        """Remove an entry from the index."""
        self._index = [i for i in self._index if i.name != name]
        self.write_index()

    # ── File CRUD ───────────────────────────────────────────

    def read_memory(self, name: str) -> Optional[MemoryItem]:
        """Read a single .md memory file, parse frontmatter."""
        safe_name = self._safe_filename(name)
        filepath = self._dir / f"{safe_name}.md"
        if not filepath.exists():
            return None

        try:
            content = filepath.read_text(encoding="utf-8")
            frontmatter, body = self._parse_frontmatter(content)

            return MemoryItem(
                name=safe_name,
                description=frontmatter.get("description", ""),
                type=MemoryType(frontmatter.get("metadata", {}).get("type", "project")),
                content=body.strip(),
                metadata=frontmatter.get("metadata", {}),
                links=frontmatter.get("links", []),
                created_at=frontmatter.get("created_at", ""),
                updated_at=frontmatter.get("updated_at", ""),
            )
        except Exception as e:
            logger.warning(f"Failed to read memory {name}: {e}")
            return None

    def write_memory(self, item: MemoryItem) -> None:
        """Write/update a .md memory file. Auto-updates index."""
        safe_name = self._safe_filename(item.name)
        item.name = safe_name
        item.updated_at = datetime.now().isoformat()
        if not item.created_at:
            item.created_at = item.updated_at

        # Build YAML frontmatter
        fm = {
            "name": item.name,
            "description": item.description,
            "metadata": {
                **item.metadata,
                "type": item.type.value,
                "updated": item.updated_at,
            },
        }
        if item.links:
            fm["links"] = item.links

        yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
        body = item.content.strip()

        # Full file content
        file_content = f"---\n{yaml_str}---\n\n{body}\n"

        # Enforce max lines (soft cap — warn, don't truncate)
        line_count = file_content.count("\n")
        if line_count > MAX_FILE_LINES:
            logger.info(f"Memory '{item.name}' is {line_count} lines (soft cap: {MAX_FILE_LINES})")

        filepath = self._dir / f"{safe_name}.md"
        filepath.write_text(file_content, encoding="utf-8")

        # Update index
        self.add_to_index(item)
        logger.info(f"Memory written: {item.name}")

    def delete_memory(self, name: str) -> bool:
        """Delete a memory file and its index entry."""
        safe_name = self._safe_filename(name)
        filepath = self._dir / f"{safe_name}.md"
        if filepath.exists():
            filepath.unlink()
        self.remove_from_index(safe_name)
        logger.info(f"Memory deleted: {safe_name}")
        return True

    def list_all(self) -> list[MemoryItem]:
        """List all indexed memories with full content."""
        results = []
        # Read full content for each indexed item
        for item in self._index:
            full = self.read_memory(item.name)
            if full:
                results.append(full)
            else:
                results.append(item)  # stub from index
        return results

    def get_index_context(self) -> str:
        """Return MEMORY.md content as a string for LLM context injection."""
        index_path = self._dir / "MEMORY.md"
        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
            return f"<memory-index>\n{content}\n</memory-index>\n\n"
        return ""

    def get_relevant_context(self, query: str = "", limit: int = 5) -> str:
        """Get memory context for LLM: MEMORY.md index + most recent files.

        Simple implementation: returns index + most recently updated files.
        Advanced LLM-based relevance selection is Phase 2.
        """
        parts = []

        # Always include the index
        index_content = self.get_index_context()
        if index_content:
            parts.append(index_content)

        # Include recently updated memory files
        if self._index:
            recent = sorted(self._index, key=lambda i: i.updated_at, reverse=True)[:limit]
            parts.append("<relevant-memories>\n")
            for item in recent:
                full = self.read_memory(item.name)
                if full and full.content:
                    parts.append(f"<!-- {item.name} — {item.description} -->\n")
                    parts.append(full.content[:1500])  # cap per file
                    parts.append("\n\n")
                else:
                    parts.append(f"- [{item.metadata.get('title', item.name)}]({item.name}.md) — {item.description}\n")
            parts.append("</relevant-memories>\n")

        return "".join(parts)

    # ── Search ──────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[MemoryItem]:
        """Simple keyword search over memory files. Phase 2 adds LLM/Milvus."""
        query_lower = query.lower()
        results = []

        for item in self._index:
            full = self.read_memory(item.name)
            if not full:
                continue
            score = 0
            # Score by keyword matches
            if query_lower in item.name.lower():
                score += 10
            if query_lower in item.description.lower():
                score += 5
            if query_lower in full.content.lower():
                score += 3
            if score > 0:
                results.append((score, full))

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    # ── Auto-extraction ─────────────────────────────────────

    async def extract_from_conversation(
        self, messages: list, today_str: str = ""
    ) -> list[MemoryItem]:
        """Extract new memories from conversation using LLM. Phase 3.

        For now, this is a stub — full automatic extraction will be Phase 3.
        """
        logger.info("Memory extraction from conversation skipped (Phase 3 feature)")
        return []

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from markdown content.

        Returns (frontmatter_dict, body_text).
        """
        if not content.startswith("---"):
            return {}, content

        lines = content.split("\n")
        fm_lines = []
        body_start = 0
        found_end = False

        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                body_start = i + 1
                found_end = True
                break
            fm_lines.append(line)
            if i > MAX_FRONTMATTER_LINES:
                break

        fm_text = "\n".join(fm_lines)
        try:
            frontmatter = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            frontmatter = {}

        body = "\n".join(lines[body_start:]) if found_end else content
        return frontmatter, body

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Sanitize a slug into a safe filename (no path traversal)."""
        # Remove any path separators, keep only alphanumeric, dash, underscore
        name = name.replace("\\", "/").split("/")[-1]
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "-", name)
        safe = re.sub(r"-+", "-", safe).strip("-")
        return safe or "untitled"


# ── Singleton accessor ──

_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(memory_dir: Optional[Path] = None) -> MemoryManager:
    """Get or create the singleton MemoryManager."""
    global _memory_manager
    if _memory_manager is None:
        if memory_dir is None:
            memory_dir = Path(__file__).resolve().parent.parent / "data" / "memory"
        _memory_manager = MemoryManager(memory_dir)
    return _memory_manager
