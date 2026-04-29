# openmanus/tools/obsidian_full_tool.py
import os
import re
import shutil
from typing import Optional, List, Dict, Any
from pathlib import Path
from .base import BaseTool

class ObsidianFullTool(BaseTool):
    """
    完整实现 obsidian-mcp 所有功能的 OpenManus 工具
    支持：增删改查、标签管理、文件移动、目录操作
    """
    name: str = "obsidian"
    description: str = "管理 Obsidian 笔记库，支持创建/读取/编辑/删除笔记、目录操作、标签管理、搜索等"

    def __init__(self, vault_path: str):
        super().__init__()
        self.vault = Path(vault_path).resolve()
        if not self.vault.exists():
            raise FileNotFoundError(f"Vault 路径不存在: {self.vault}")

    def call(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        params = params or {}
        method = method.lower().replace("-", "_")
        
        handlers = {
            "add_tags": self.add_tags,
            "create_directory": self.create_directory,
            "create_note": self.create_note,
            "delete_note": self.delete_note,
            "edit_note": self.edit_note,
            "list_available_vaults": self.list_available_vaults,
            "manage_tags": self.manage_tags,
            "move_note": self.move_note,
            "read_note": self.read_note,
            "remove_tags": self.remove_tags,
            "rename_tag": self.rename_tag,
            "search_vault": self.search_vault,
        }

        if method not in handlers:
            return {"error": f"不支持的方法: {method}"}
        
        return handlers[method](**params)

    # ------------------------------
    # 工具实现
    # ------------------------------
    def _resolve_path(self, rel_path: str) -> Path:
        """解析相对路径为绝对路径，防止路径穿越"""
        abs_path = (self.vault / rel_path).resolve()
        if not abs_path.is_relative_to(self.vault):
            raise PermissionError("路径超出 Vault 范围")
        return abs_path

    def read_note(self, path: str) -> Dict:
        abs_path = self._resolve_path(path)
        if not abs_path.exists() or not abs_path.is_file():
            return {"error": "文件不存在"}
        try:
            content = abs_path.read_text(encoding="utf-8")
            return {"content": content, "path": path}
        except Exception as e:
            return {"error": f"读取失败: {str(e)}"}

    def create_note(self, path: str, content: str = "") -> Dict:
        abs_path = self._resolve_path(path)
        if abs_path.exists():
            return {"error": "文件已存在"}
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        return {"status": "created", "path": path}

    def edit_note(self, path: str, content: str) -> Dict:
        abs_path = self._resolve_path(path)
        if not abs_path.exists():
            return {"error": "文件不存在"}
        abs_path.write_text(content, encoding="utf-8")
        return {"status": "updated", "path": path}

    def delete_note(self, path: str) -> Dict:
        abs_path = self._resolve_path(path)
        if not abs_path.exists():
            return {"error": "文件不存在"}
        abs_path.unlink()
        return {"status": "deleted", "path": path}

    def move_note(self, source: str, destination: str) -> Dict:
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        if not src.exists():
            return {"error": "源文件不存在"}
        if dst.exists():
            return {"error": "目标文件已存在"}
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {"status": "moved", "from": source, "to": destination}

    def create_directory(self, path: str) -> Dict:
        abs_path = self._resolve_path(path)
        abs_path.mkdir(parents=True, exist_ok=True)
        return {"status": "created", "path": path}

    def add_tags(self, path: str, tags: List[str]) -> Dict:
        abs_path = self._resolve_path(path)
        if not abs_path.exists():
            return {"error": "文件不存在"}
        content = abs_path.read_text(encoding="utf-8")
        # 匹配 YAML frontmatter
        fm_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
        match = fm_pattern.match(content)
        if match:
            fm_content = match.group(1)
            body = content[match.end():]
            # 解析 tags
            tag_pattern = re.compile(r"tags:\s*(.*)", re.MULTILINE)
            tag_match = tag_pattern.search(fm_content)
            if tag_match:
                existing_tags = [t.strip() for t in tag_match.group(1).split(",")]
                new_tags = list(set(existing_tags + tags))
                updated_fm = tag_pattern.sub(f"tags: {', '.join(new_tags)}", fm_content)
            else:
                updated_fm = fm_content + f"\ntags: {', '.join(tags)}"
            new_content = f"---\n{updated_fm}\n---\n{body}"
        else:
            new_content = f"---\ntags: {', '.join(tags)}\n---\n{content}"
        abs_path.write_text(new_content, encoding="utf-8")
        return {"status": "tags added", "path": path, "tags": tags}

    def remove_tags(self, path: str, tags: List[str]) -> Dict:
        abs_path = self._resolve_path(path)
        if not abs_path.exists():
            return {"error": "文件不存在"}
        content = abs_path.read_text(encoding="utf-8")
        fm_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
        match = fm_pattern.match(content)
        if match:
            fm_content = match.group(1)
            body = content[match.end():]
            tag_pattern = re.compile(r"tags:\s*(.*)", re.MULTILINE)
            tag_match = tag_pattern.search(fm_content)
            if tag_match:
                existing_tags = [t.strip() for t in tag_match.group(1).split(",")]
                new_tags = [t for t in existing_tags if t not in tags]
                if new_tags:
                    updated_fm = tag_pattern.sub(f"tags: {', '.join(new_tags)}", fm_content)
                else:
                    updated_fm = tag_pattern.sub("", fm_content)
                new_content = f"---\n{updated_fm}\n---\n{body}"
                abs_path.write_text(new_content, encoding="utf-8")
        return {"status": "tags removed", "path": path, "removed": tags}

    def manage_tags(self, path: str, add: Optional[List[str]] = None, remove: Optional[List[str]] = None) -> Dict:
        if add:
            self.add_tags(path, add)
        if remove:
            self.remove_tags(path, remove)
        return {"status": "tags managed", "path": path}

    def rename_tag(self, old_tag: str, new_tag: str) -> Dict:
        count = 0
        for md_file in self.vault.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            fm_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
            match = fm_pattern.match(content)
            if match:
                fm_content = match.group(1)
                tag_pattern = re.compile(r"tags:\s*(.*)", re.MULTILINE)
                tag_match = tag_pattern.search(fm_content)
                if tag_match:
                    tags = [t.strip() for t in tag_match.group(1).split(",")]
                    if old_tag in tags:
                        tags = [new_tag if t == old_tag else t for t in tags]
                        updated_fm = tag_pattern.sub(f"tags: {', '.join(tags)}", fm_content)
                        new_content = f"---\n{updated_fm}\n---\n{content[match.end():]}"
                        md_file.write_text(new_content, encoding="utf-8")
                        count += 1
        return {"status": "tag renamed", "old": old_tag, "new": new_tag, "files_updated": count}

    def list_available_vaults(self) -> Dict:
        # 这里返回当前配置的 Vault，如需多 Vault 可扩展
        return {"vaults": [str(self.vault)]}

    def search_vault(self, query: str) -> Dict:
        matches = []
        for md_file in self.vault.rglob("*.md"):
            rel_path = str(md_file.relative_to(self.vault))
            if query.lower() in rel_path.lower():
                matches.append(rel_path)
            else:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                if query.lower() in content.lower():
                    matches.append(rel_path)
        return {"matches": matches[:100]}