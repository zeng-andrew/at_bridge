# AT Bridge

> MCP server for AI-driven AT command debugging over serial port.

AT Bridge 是一个 [Model Context Protocol](https://modelcontextprotocol.io/) 服务器，让 AI 助手能够通过 COM/串口直接与 IoT 模组通信，进行 AT 命令调试。内置可维护的芯片平台知识库，实测过的命令自动沉淀。

## Features

- **串口通信** — 自动探测可用 COM 口，支持主流波特率，可配置校验位/流控
- **AT 命令调试** — 发送 AT 命令并解析响应，自动补全 AT 前缀
- **批量测试** — 一次性发送命令列表，自动分类 PASS/ERR/CME
- **知识库** — 按芯片平台分层存储 AT 命令（含语法、返回值含义、实测数据），支持搜索和持续积累
- **双层存储** — 包内 YAML 只读（随版本分发），用户数据写到 `%APPDATA%`（跨版本保留）

## Quick Start

```bash
uv sync
uv run python main.py
```

## MCP Configuration

```json
{
  "mcpServers": {
    "at-bridge": {
      "command": "uv",
      "args": ["run", "--directory", "path/to/at_bridge", "python", "main.py"]
    }
  }
}
```

## Tools

### Serial Communication

| Tool | Description |
|---|---|
| `at_list_ports` | 枚举 COM/串口，含 VID/PID、制造商、描述 |
| `at_auto_detect` | 自动探测 — 扫描所有端口，试多种波特率，找出响应 AT 的设备 |
| `at_configure` | 配置波特率、数据位、校验位、停止位、流控 |
| `at_open_port` / `at_close_port` | 打开/关闭串口连接 |
| `at_send_command` | 发送单条 AT 命令，自动补全 `AT` 前缀，解析响应 |
| `at_batch_test` | 批量测试 — 一次发送命令列表，自动分类结果 |

### Knowledge Base

| Tool | Description |
|---|---|
| `at_knowledge_search` | 按关键词/平台/标签搜索命令库 |
| `at_knowledge_list` | 列出全部命令，可按平台过滤 |
| `at_knowledge_add` | 添加/更新命令到指定芯片平台 |
| `at_knowledge_chipsets` | 查看可用的芯片平台列表 |
| `at_knowledge_stats` | 知识库统计：条目数、来源分布 |

## Chipsets

芯片平台知识库位于 `src/at_bridge/chipsets/`，按平台分层：

| 文件 | 内容 |
|---|---|
| `_3gpp.yaml` | 3GPP 标准 AT 命令（49 条），只读基础库 |
| `asr.yaml` | ASR 平台私有命令与平台特性 |
| `quectel.yaml` | 移远 EC200x 等私有命令（48 条） |
| `_custom.yaml` | 用户自定义命令，自动创建于 `%APPDATA%/at-bridge/chipsets/` |

加载顺序：`_3gpp` → 平台文件 → `_custom`（后者覆盖同名 key）。

## Project Structure

```
at_bridge/
  main.py                    # Entry point — MCP server on stdio
  src/at_bridge/
    server.py                # MCP server: 12 tool definitions + handlers
    serial_handler.py        # Serial I/O + batch test engine
    knowledge_store.py       # YAML knowledge base CRUD with two-layer storage
    chipsets/                # Platform command libraries
      _3gpp.yaml / asr.yaml / quectel.yaml
```
