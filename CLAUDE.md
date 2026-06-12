# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AT Bridge is an MCP (Model Context Protocol) server that enables AI assistants to communicate with hardware devices via COM/serial port for AT command debugging. Built with Python 3.12+, `pyserial` for serial communication, and the `mcp` Python SDK.

## Commands

```bash
# Install dependencies
uv sync

# Run MCP server (stdio transport)
uv run python main.py

# Quick import verification
uv run python -c "from src.at_bridge.serial_handler import SerialHandler; print(SerialHandler().list_ports())"
```

## Architecture

```
main.py                        # Entry point -- runs MCP server on stdio
src/at_bridge/
  __init__.py                  # Package metadata
  server.py                    # MCP server: 11 tool definitions + handlers
  serial_handler.py            # Serial port I/O (list, open, close, send AT, auto-detect)
  knowledge_store.py           # AT command knowledge base CRUD (YAML-based)
  chipsets/                    # Platform-specific command libraries (shipped with package)
    _3gpp.yaml                 #   3GPP standard base (read-only)
    asr.yaml                   #   ASR platform commands (writable via MCP)
    quectel.yaml               #   Quectel vendor commands (writable via MCP)
    _custom.yaml               #   User scratchpad (auto-created on first add)
```

- **`serial_handler.py`** -- Low-level serial I/O using `pyserial`. `PortConfig` dataclass + `SerialHandler` class owns connection state. All serial operations go through this.
- **`knowledge_store.py`** -- `KnowledgeStore` class manages JSON file persistence. `ATCommand` and `ResponseField` dataclasses define the schema. Supports search (name/description/tags/category), add-or-merge-update, category stats.
- **`server.py`** -- MCP server layer. Defines 10 tools via `@server.list_tools()` and `@server.call_tool()`. Global `handler` (SerialHandler) and `kb` (KnowledgeStore) instances. Runs via stdio transport.

## MCP Tools

### Serial Communication

| Tool | Purpose |
|---|---|
| `at_list_ports` | Enumerate COM/serial ports with VID/PID, manufacturer, description |
| `at_auto_detect` | Probe all available ports, try common baud rates, find AT-responding devices |
| `at_configure` | Set baudrate, parity, stop bits, flow control before or after opening |
| `at_open_port` | Open a named COM port |
| `at_close_port` | Close current connection |
| `at_send_command` | Send AT command (AT prefix auto-prepended), read parsed response |

### Knowledge Base (AT Command Library)

| Tool | Purpose |
|---|---|
| `at_knowledge_search` | Search by keyword/standard/tags across all chipset files |
| `at_knowledge_chipsets` | List available chipset platforms (writable vs read-only) |
| `at_knowledge_add` | Add/update a command, specifying target `chipset` (e.g. "asr", "quectel") |
| `at_knowledge_list` | List all commands, optionally filtered by standard |
| `at_knowledge_stats` | Statistics: total commands, per-source-file breakdown, by standard |

## Serial Handler Design

- Single `SerialHandler` instance -- not thread-safe, designed for sequential tool calls within one MCP session.
- `send_at_command` sends `AT<cmd>\r\n`, reads line-by-line until `OK`/`ERROR`/`+CME ERROR` or timeout.
- Configuration is preserved across open/close cycles.
- `auto_detect` saves/restores existing connection state; tries 8 common baud rates per port.

## Knowledge Base Design

- Stored as YAML files in `chipsets/` with per-platform layering:
  - `_3gpp.yaml` = 3GPP standard base (read-only)
  - `asr.yaml` / `quectel.yaml` = vendor platform files (writable via MCP)
  - `_custom.yaml` = user scratchpad (writable, loaded last for overrides)
- **Load order**: `_3gpp` → vendor files (alpha) → `_custom` (last wins on same key).
- **Update path**: AI calls `at_knowledge_chipsets` → picks target platform → `at_knowledge_add {chipset:"asr", key:..., command:...}` → writes to `chipsets/asr.yaml`.
- Each entry: key (slug), command (AT string with `{param}` vars), name, description, expect[], timeout, retry, params[], type, standard.
