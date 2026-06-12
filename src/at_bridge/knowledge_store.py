"""AT command knowledge base using YAML chipset files.

Two-layer architecture:
  1. Package layer (read-only, ships with the package):
     src/at_bridge/chipsets/
       _3gpp.yaml       Base — 3GPP standard commands
       asr.yaml         ASR platform commands
       quectel.yaml     Quectel vendor commands

  2. User data layer (writable, auto-created):
     ~/.at-bridge/chipsets/   (Linux / macOS)
     %APPDATA%/at-bridge/chipsets/  (Windows)
       _custom.yaml     User-added commands
       *.yaml           Vendor overrides (same key = override package version)

Load order: package layer → user layer (last wins on same key).
Writes always go to user layer, package layer stays pristine.
"""

import os
import re
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# ── Data model ──────────────────────────────────────────────────────────


@dataclass
class ParamDef:
    """Parameter definition for an AT command."""

    name: str
    type: str = "string"  # int | string
    default: object = None
    required: bool = False


@dataclass
class CommandEntry:
    """A single AT command entry loaded from a YAML file."""

    key: str  # YAML key / slug, e.g. "at+csq"
    command: str  # The actual AT command, e.g. "AT+CSQ" or "AT+IPR={baud}"
    name: str  # Short Chinese name, e.g. "信号质量"
    description: str  # Full description including return value meanings
    standard: str = "3gpp"  # "3gpp" | "vendor" | "custom"
    expect: list = field(default_factory=list)  # Expected response patterns
    timeout: float = 1.0
    retry: int = 1
    params: list[dict] = field(default_factory=list)
    type: str = ""  # "" = AT command, "urc" = passive URC wait, "data" = raw send
    end_rn: bool = True  # Append \r\n after command
    source_file: str = ""  # Which YAML file this came from (set at load time)
    from_user: bool = False  # True if loaded from user data layer (should persist)

    @property
    def category(self) -> str:
        """Derived category from standard field."""
        return {"3gpp": "标准(3GPP)", "vendor": "厂商私有", "custom": "自定义"}.get(
            self.standard, self.standard
        )

    @property
    def tags(self) -> list:
        """Derived tags from entry fields."""
        tags = []
        if self.type == "urc":
            tags.append("urc")
        if self.type == "data":
            tags.append("data")
        if self.params:
            tags.append("带参数")
        if self.source_file:
            tags.append(self.source_file.replace(".yaml", ""))
        return tags

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "command": self.command,
            "name": self.name,
            "description": self.description,
            "standard": self.standard,
            "category": self.category,
            "expect": self.expect,
            "timeout": self.timeout,
            "retry": self.retry,
            "params": self.params,
            "type": self.type or "command",
            "end_rn": self.end_rn,
            "source_file": self.source_file,
            "tags": self.tags,
        }


# ── Knowledge store ─────────────────────────────────────────────────────


class KnowledgeStore:
    """Manages AT command knowledge from chipsets/*.yaml files."""

    # Package chipsets: read-only, shipped with the code
    _PKG_DIR = Path(__file__).resolve().parent / "chipsets"

    @staticmethod
    def _user_data_dir() -> Path:
        """Platform-appropriate user data directory for writable chipsets."""
        import platform
        system = platform.system()
        if system == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif system == "Darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            base = Path(xdg)
        return base / "at-bridge" / "chipsets"

    def __init__(self, chipsets_dir: Optional[str] = None, user_dir: Optional[str] = None):
        """
        Args:
            chipsets_dir: Override the read-only package chipsets directory.
            user_dir: Override the writable user data directory.
        """
        self._pkg_dir = Path(chipsets_dir) if chipsets_dir else self._PKG_DIR
        self._user_dir = Path(user_dir) if user_dir else self._user_data_dir()
        self._user_dir.mkdir(parents=True, exist_ok=True)

        self._commands: OrderedDict[str, CommandEntry] = OrderedDict()
        self._load()

    # ── Loading ──────────────────────────────────────────────────────

    def _load(self):
        """Load YAML files from two layers: package (RO) then user data (RW).

        Package layer loads first, user layer overrides on same key.
        Files prefixed with _ (like _3gpp, _custom) are special: _3gpp is
        always loaded first as base; _custom is always loaded last.
        """
        def _load_from(directory: Path, readonly: bool):
            if not directory.exists():
                return
            all_files = sorted(directory.glob("*.yaml"))
            # Sort: _3gpp first, _custom last, others alphabetically in between
            base = [f for f in all_files if f.name == "_3gpp.yaml"]
            custom = [f for f in all_files if f.name == "_custom.yaml"]
            others = [f for f in all_files if f not in base and f not in custom]
            ordered_files = base + others + custom

            for yaml_file in ordered_files:
                try:
                    self._load_file(yaml_file, readonly)
                except yaml.YAMLError as e:
                    print(f"[knowledge_store] WARNING: failed to parse {yaml_file}: {e}")

        _load_from(self._pkg_dir, readonly=True)
        _load_from(self._user_dir, readonly=False)

    def _load_file(self, yaml_file: Path, readonly: bool = True):
        """Load entries from a single YAML file.

        Top-level keys become command slugs.  Entries with the same key
        in later-loaded files override earlier ones.
        """
        text = yaml_file.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            return

        source = yaml_file.name
        from_user = str(yaml_file.resolve()).startswith(str(self._user_dir.resolve()))

        for key, raw in data.items():
            if not isinstance(raw, dict):
                continue

            entry = CommandEntry(
                key=key,
                command=raw.get("command", ""),
                name=raw.get("name", key),
                description=raw.get("description", ""),
                standard=raw.get("standard", "custom"),
                expect=raw.get("expect", []),
                timeout=float(raw.get("timeout", 1.0)),
                retry=int(raw.get("retry", 1)),
                params=raw.get("params", []),
                type=raw.get("type", ""),
                end_rn=raw.get("end_rn", True),
                source_file=source,
                from_user=from_user,
            )
            self._commands[key] = entry

    def reload(self):
        """Reload all YAML files (useful after external edits)."""
        self._commands.clear()
        self._load()

    # ── Searching / querying ─────────────────────────────────────────

    def search(
        self,
        query: str = "",
        category: str = "",
        standard: str = "",
        tags: list = None,
    ) -> list[dict]:
        """Search commands by text, category, standard, or tags.

        Args:
            query: Free-text search across key, name, description, command.
            category: Filter by category label (e.g. "标准(3GPP)", "厂商私有").
            standard: Filter by standard field ("3gpp", "vendor", "custom").
            tags: Filter by derived tags (any match).

        Returns:
            List of matching command dicts.
        """
        results = []
        query_lower = query.lower().strip() if query else ""

        for entry in self._commands.values():
            ed = entry.to_dict()

            if standard and entry.standard != standard:
                continue
            if category and entry.category != category:
                continue
            if tags:
                entry_tags_lower = [t.lower() for t in entry.tags]
                if not any(t.lower() in entry_tags_lower for t in tags):
                    continue

            if query_lower:
                searchable = " ".join([
                    entry.key.lower(),
                    entry.name.lower(),
                    entry.description.lower(),
                    entry.command.lower(),
                    entry.standard.lower(),
                    " ".join(entry.tags).lower(),
                ])
                if query_lower not in searchable:
                    continue

            results.append(ed)

        return results

    def get(self, key: str) -> Optional[dict]:
        """Get a single command by its YAML key (slug)."""
        entry = self._commands.get(key.strip())
        return entry.to_dict() if entry else None

    def list_all(self, standard: str = "", category: str = "") -> list[dict]:
        """List all commands, optionally filtered by standard or category."""
        entries = list(self._commands.values())
        if standard:
            entries = [e for e in entries if e.standard == standard]
        if category:
            entries = [e for e in entries if e.category == category]
        return [e.to_dict() for e in entries]

    def get_by_source(self) -> dict[str, list[dict]]:
        """Group commands by their source YAML file."""
        groups: dict[str, list[dict]] = OrderedDict()
        for entry in self._commands.values():
            src = entry.source_file or "unknown"
            groups.setdefault(src, []).append(entry.to_dict())
        return groups

    def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        sources = self.get_by_source()
        by_standard: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for e in self._commands.values():
            by_standard[e.standard] = by_standard.get(e.standard, 0) + 1
            by_category[e.category] = by_category.get(e.category, 0) + 1

        return {
            "total_commands": len(self._commands),
            "source_files": [
                {"file": name, "count": len(cmds)}
                for name, cmds in sources.items()
            ],
            "by_standard": by_standard,
            "by_category": by_category,
            "package_dir": str(self._pkg_dir),
            "user_dir": str(self._user_dir),
        }

    # ── Adding / updating custom commands ─────────────────────────────

    def list_chipsets(self) -> list[dict]:
        """List available chipset files from both package and user layers.

        Returns list of {name, file, path, count, writable, layer} dicts.
        """
        result = []
        seen = set()

        # User layer first (writable)
        for yf in sorted(self._user_dir.glob("*.yaml")):
            name = yf.stem
            seen.add(name)
            count = sum(1 for e in self._commands.values() if e.source_file == yf.name)
            result.append({
                "name": name, "file": yf.name, "path": str(yf),
                "count": count, "writable": True,
                "layer": "user",
            })

        # Package layer (read-only, only if not already in user)
        if self._pkg_dir.exists():
            for yf in sorted(self._pkg_dir.glob("*.yaml")):
                name = yf.stem
                if name in seen:
                    continue
                count = sum(1 for e in self._commands.values() if e.source_file == yf.name)
                result.append({
                    "name": name, "file": yf.name, "path": str(yf),
                    "count": count, "writable": False,
                    "layer": "package",
                })

        return result

    def add_or_update(self, command_data: dict, chipset: str = "_custom") -> dict:
        """Add or update a command entry in the specified chipset YAML file.

        Args:
            command_data: Dict with CommandEntry-compatible fields.
                Required: key, command.
                Optional: name, description, standard, expect, timeout, retry,
                          params, type, end_rn.
            chipset: Target chipset name (e.g. "asr", "quectel", "_custom").
                     The entry is written to chipsets/{chipset}.yaml.
                     Default "_custom" = user scratchpad.

        Returns:
            The saved command dict.

        Raises:
            ValueError: If key or command is missing, or chipset is read-only.
        """
        key = command_data.get("key", "").strip()
        if not key:
            raise ValueError("'key' is required (the YAML slug, e.g. 'at+csq')")

        command = command_data.get("command", "").strip()
        if not command:
            raise ValueError("'command' is required (the AT command string)")

        # Resolve target file name
        target_file = f"{chipset}.yaml" if not chipset.endswith(".yaml") else chipset

        # _3gpp.yaml is the base library — always read-only
        if chipset == "_3gpp" or target_file == "_3gpp.yaml":
            raise ValueError(
                "_3gpp.yaml is the base library and cannot be modified. "
                "Use a vendor chipset name (e.g. 'asr', 'quectel') or '_custom'."
            )

        # Build the entry — always marked as user data
        entry = CommandEntry(
            key=key,
            command=command,
            name=command_data.get("name", key),
            description=command_data.get("description", ""),
            standard=command_data.get("standard", "vendor"),
            expect=command_data.get("expect", []),
            timeout=float(command_data.get("timeout", 1.0)),
            retry=int(command_data.get("retry", 1)),
            params=command_data.get("params", []),
            type=command_data.get("type", ""),
            end_rn=command_data.get("end_rn", True),
            source_file=target_file,
            from_user=True,
        )

        # Store in memory
        self._commands[key] = entry

        # Persist to the target chipset file
        self._save_chipset(chipset)

        return entry.to_dict()

    def delete(self, key: str) -> bool:
        """Delete a command entry (only from writable chipset files).

        Args:
            key: The YAML key/slug to delete.

        Returns:
            True if deleted, False if not found or in read-only file.
        """
        entry = self._commands.get(key.strip())
        if entry is None:
            return False

        # Can only delete entries that came from the user layer
        if not entry.from_user:
            return False

        chipset = entry.source_file.replace(".yaml", "")
        del self._commands[key]
        self._save_chipset(chipset)
        return True

    def _save_chipset(self, chipset: str):
        """Write entries belonging to a specific chipset file to USER data dir.

        Never writes to the package directory — user data always goes to
        the platform-appropriate writable location.
        """
        target_file = f"{chipset}.yaml" if not chipset.endswith(".yaml") else chipset
        target_path = self._user_dir / target_file

        # Collect only user-origin entries for this chipset
        entries = OrderedDict()
        for key, entry in self._commands.items():
            if entry.source_file == target_file and entry.from_user:
                entries[key] = self._entry_to_raw(entry)

        self._user_dir.mkdir(parents=True, exist_ok=True)

        # Build YAML
        lines = []
        if chipset == "_custom":
            lines.append("# 自定义 AT 命令（通过 at_knowledge_add 添加）")
            lines.append("# 此文件中的条目会覆盖基础库中的同名字段")
        else:
            lines.append(f"# {chipset.upper()} 平台 AT 命令")
            lines.append(f"# 通过 MCP at_knowledge_add 维护")
        lines.append("")
        lines.append(f"# 更新时间: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"# 条目数: {len(entries)}")
        lines.append("")

        if not entries:
            lines.append("# 暂无命令")
            lines.append("")
            target_path.write_text("\n".join(lines), encoding="utf-8")
            return

        yaml_text = yaml.dump(
            _ordered_to_plain(dict(entries)),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )
        lines.append(yaml_text)
        target_path.write_text("\n".join(lines), encoding="utf-8")

    def _entry_to_raw(self, entry: CommandEntry) -> dict:
        """Convert a CommandEntry to a dict suitable for YAML serialization."""
        d = OrderedDict()
        if entry.type:
            d["type"] = entry.type
        d["command"] = entry.command
        d["name"] = entry.name
        d["description"] = entry.description
        if entry.params:
            d["params"] = entry.params
        d["expect"] = entry.expect
        d["timeout"] = entry.timeout
        if entry.retry != 1:
            d["retry"] = entry.retry
        if not entry.end_rn:
            d["end_rn"] = False
        d["standard"] = entry.standard
        return d


# ── Helpers ──────────────────────────────────────────────────────────────


def _ordered_to_plain(obj):
    """Recursively convert OrderedDict to plain dict for clean YAML output."""
    if isinstance(obj, OrderedDict):
        return {k: _ordered_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _ordered_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_ordered_to_plain(v) for v in obj]
    return obj


def parse_at_response(response_text: str, fields: list[dict]) -> dict:
    """Parse a raw AT response against known response_fields definitions.

    Args:
        response_text: Raw response text from the device.
        fields: List of field definitions from a CommandEntry (name, description).

    Returns:
        Dict mapping field names to extracted values (best-effort).
    """
    result = {}
    lines = response_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or line == "OK" or line == "ERROR":
            continue
        # Try to match colon-separated fields like "+CSQ: 25,99"
        if ":" in line:
            prefix, values = line.split(":", 1)
            parts = [v.strip() for v in values.split(",")]
            for i, field in enumerate(fields):
                if i < len(parts):
                    result[field.get("name", f"field_{i}")] = parts[i]
    return result
