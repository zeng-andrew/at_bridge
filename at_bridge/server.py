"""MCP server exposing AT command tools for COM port device communication."""

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .serial_handler import SerialHandler
from .knowledge_store import KnowledgeStore

# --- Global state ---
handler = SerialHandler()
kb = KnowledgeStore()

# --- MCP Server ---
server = Server("at-bridge")


@server.list_tools()
async def list_tools() -> list:
    """List available MCP tools."""
    return [
        {
            "name": "at_list_ports",
            "description": "列出系统中所有可用的 COM/串口设备。返回端口名、描述、硬件ID、VID/PID 等信息。",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "at_configure",
            "description": "配置串口通信参数（波特率、数据位、校验位、停止位、流控等）。打开端口前或打开后均可调用。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "baudrate": {
                        "type": "integer",
                        "description": "波特率，常用值: 9600, 115200, 921600, 1000000。默认 115200。",
                        "default": 115200,
                    },
                    "bytesize": {
                        "type": "integer",
                        "description": "数据位: 5, 6, 7, 8。默认 8。",
                        "default": 8,
                    },
                    "parity": {
                        "type": "string",
                        "description": "校验位: N(无), E(偶校验), O(奇校验), M(标记), S(空格)。默认 N。",
                        "default": "N",
                    },
                    "stopbits": {
                        "type": "number",
                        "description": "停止位: 1, 1.5, 2。默认 1。",
                        "default": 1,
                    },
                    "timeout": {
                        "type": "number",
                        "description": "读取超时(秒)。默认 1.0。",
                        "default": 1.0,
                    },
                    "rtscts": {
                        "type": "boolean",
                        "description": "硬件流控 RTS/CTS。默认 false。",
                        "default": False,
                    },
                    "xonxoff": {
                        "type": "boolean",
                        "description": "软件流控 XON/XOFF。默认 false。",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "at_open_port",
            "description": "打开指定的 COM 口，建立与设备的串口连接。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "port": {
                        "type": "string",
                        "description": "串口设备名。Windows: COM3, COM4 等; Linux: /dev/ttyUSB0, /dev/ttyACM0 等。",
                    },
                },
                "required": ["port"],
            },
        },
        {
            "name": "at_close_port",
            "description": "关闭当前打开的 COM 口连接。",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "at_auto_detect",
            "description": "自动探测所有可用 COM 口，逐一尝试连接并发送 AT 测试命令，找出有响应的设备。适合在不确定设备连接到哪个端口时使用。会尝试多种常见波特率。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "baudrates": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要尝试的波特率列表。默认: 115200, 9600, 921600, 460800, 230400, 57600, 38400, 19200。",
                    },
                    "probe_timeout": {
                        "type": "number",
                        "description": "每次尝试的超时秒数，越小越快但可能漏掉响应慢的设备。默认 0.5。",
                        "default": 0.5,
                    },
                    "test_command": {
                        "type": "string",
                        "description": "用于探测的 AT 命令。默认 'AT'。",
                        "default": "AT",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "at_send_command",
            "description": "发送 AT 命令到已连接的设备并读取响应。这是调试 AT 命令的核心工具。命令会自动补全 AT 前缀（如输入 'CSQ' 会发送 'AT+CSQ'）。支持标准 AT 命令、扩展 AT+ 命令等。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要发送的 AT 命令。例如: 'AT', 'AT+CGMI', 'AT+CSQ', 'AT+CREG?', 或省略 AT 前缀如 'CGMI', '+CSQ'。",
                    },
                    "read_until": {
                        "type": "string",
                        "description": "可选。读到指定字符串后停止等待更多响应。",
                    },
                },
                "required": ["command"],
            },
        },
        {
            "name": "at_batch_test",
            "description": "批量测试 AT 命令。发送一组 AT 命令到已连接的设备，一次性返回所有结果（含自动分类：PASS/OK/ERR/CME）。比逐条调用 at_send_command 高效得多，适合验证知识库中的命令列表。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要测试的 AT 命令列表。例如 ['AT', 'AT+CSQ', 'AT+CGMI']。每条约 4ms，大批量建议按类别分组，每组 20-30 条。",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "每条命令的超时秒数。默认 1.0。",
                        "default": 1.0,
                    },
                },
                "required": ["commands"],
            },
        },
        {
            "name": "at_knowledge_search",
            "description": "搜索 AT 命令知识库。支持按关键词（key/命令名/描述）和来源（3gpp/vendor/custom）过滤。适合在不确定命令是什么时查找相关 AT 命令。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词。搜索范围: key(如'csq')、命令名、描述、AT指令字符串。例如 '信号', 'tcp', 'CGMI'。留空返回所有命令。",
                    },
                    "standard": {
                        "type": "string",
                        "description": "按标准过滤: 3gpp(标准命令), vendor(厂商私有), custom(自定义)。",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签过滤（匹配任一标签即可）。例 ['urc', 'quectel']。",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "at_knowledge_chipsets",
            "description": "列出所有可用的芯片平台知识库文件。AI 应先调用此工具了解有哪些平台，然后通过 at_knowledge_add 将命令添加到对应的平台文件。",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "at_knowledge_add",
            "description": "向知识库添加/更新一条 AT 命令。存储到指定芯片平台文件（如 asr、quectel）或 _custom 中。通过 at_knowledge_chipsets 查看可用的平台名。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "YAML slug/key，如 'at+csq', 'at+qcell'。必须唯一。",
                    },
                    "command": {
                        "type": "string",
                        "description": "实际 AT 指令字符串。如 'AT+CSQ', 'AT+QCELL?'。支持 {param} 变量占位。",
                    },
                    "name": {
                        "type": "string",
                        "description": "中文简短名称，如 '信号质量'。",
                    },
                    "description": {
                        "type": "string",
                        "description": "功能描述，包含返回值含义。支持多行文本。",
                    },
                    "chipset": {
                        "type": "string",
                        "description": "目标芯片平台。通过 at_knowledge_chipsets 查看可选列表。默认为 '_custom'（用户暂存区）。常用: asr, quectel。",
                    },
                    "standard": {
                        "type": "string",
                        "description": "来源: 3gpp / vendor / custom。默认 vendor。",
                    },
                    "expect": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "期望响应模式列表。如 ['+CSQ:', 'OK']。",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "超时秒数。默认 1.0。",
                    },
                    "retry": {
                        "type": "integer",
                        "description": "重试次数。默认 1。",
                    },
                    "params": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "参数列表。每个参数含 name/type/default/required。",
                    },
                    "type": {
                        "type": "string",
                        "description": "命令类型: 空=AT命令, urc=被动URC等待, data=透传数据。",
                    },
                },
                "required": ["key", "command"],
            },
        },
        {
            "name": "at_knowledge_list",
            "description": "列出知识库中所有 AT 命令（可按来源过滤）。显示 key、名称、期望响应等摘要信息。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "standard": {
                        "type": "string",
                        "description": "按来源过滤: 3gpp / vendor / custom。不填则全部。",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "at_knowledge_stats",
            "description": "查看知识库统计信息：命令总数、各 YAML 源文件条目数、来源分布。",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Handle tool calls."""

    if name == "at_list_ports":
        ports = handler.list_ports()
        if not ports:
            return [{"type": "text", "text": "未找到任何串口设备。"}]
        text = f"找到 {len(ports)} 个串口设备:\n\n"
        for i, p in enumerate(ports, 1):
            text += f"  {i}. {p['device']} - {p['description']}\n"
            if p.get("manufacturer"):
                text += f"     制造商: {p['manufacturer']}\n"
            if p.get("vid"):
                text += f"     VID/PID: {p['vid']}/{p['pid']}\n"
            if p.get("serial_number"):
                text += f"     SN: {p['serial_number']}\n"
            text += f"     HWID: {p['hwid']}\n\n"
        return [{"type": "text", "text": text.strip()}]

    elif name == "at_configure":
        config = handler.configure(**arguments)
        return [{"type": "text", "text": f"串口配置已更新:\n{_format_config(config)}"}]

    elif name == "at_open_port":
        port = arguments["port"]
        try:
            result = handler.open(port)
            return [{"type": "text", "text": f"已连接到 {port}\n{_format_config(result['config'])}"}]
        except Exception as e:
            return [{"type": "text", "text": f"打开端口 {port} 失败: {e}"}]

    elif name == "at_close_port":
        result = handler.close()
        if result["status"] == "disconnected":
            return [{"type": "text", "text": f"已断开端口 {result['port']}。"}]
        return [{"type": "text", "text": "当前没有打开的端口。"}]

    elif name == "at_auto_detect":
        baudrates = arguments.get("baudrates")
        probe_timeout = arguments.get("probe_timeout", 0.5)
        test_command = arguments.get("test_command", "AT")

        try:
            discovered = handler.auto_detect(
                baudrates=baudrates,
                probe_timeout=probe_timeout,
                test_command=test_command,
            )
        except Exception as e:
            return [{"type": "text", "text": f"自动探测失败: {e}"}]

        if not discovered:
            return [{"type": "text", "text": (
                "未发现任何可响应的 AT 设备。\n\n"
                "可能原因:\n"
                "  - 设备未连接或未上电\n"
                "  - 设备使用了非标准波特率（试试 at_auto_detect baudrates=[其他波特率]）\n"
                "  - 设备需要硬件流控（RTS/CTS）\n"
                "  - 设备 AT 接口在另一个 COM 口上"
            )}]

        total_ports = len(handler.list_ports())
        text = f"扫描完成: {len(discovered)}/{total_ports} 个端口有响应\n\n"
        for i, d in enumerate(discovered, 1):
            text += f"{'='*50}\n"
            text += f"  [{i}] {d['device']} - {d['description']}\n"
            text += f"  工作波特率: {d['working_baudrate']}\n"
            if d.get("manufacturer"):
                text += f"  制造商: {d['manufacturer']}\n"
            if d.get("vid"):
                text += f"  VID/PID: {d['vid']}/{d['pid']}\n"
            if d.get("serial_number"):
                text += f"  SN: {d['serial_number']}\n"
            if d.get("response"):
                text += f"  响应: {d['response']}\n"
            text += f"  尝试过的波特率: {d['tried_baudrates']}\n"

        return [{"type": "text", "text": text.strip()}]

    elif name == "at_send_command":
        command = arguments["command"]
        read_until = arguments.get("read_until")
        try:
            result = handler.send_at_command(command, read_until)
            text = f"发送: {result['command']}\n"
            text += f"耗时: {result['elapsed_ms']}ms\n"
            text += f"响应:\n"
            for line in result["response"]:
                text += f"  {line}\n"
            return [{"type": "text", "text": text.strip()}]
        except RuntimeError as e:
            return [{"type": "text", "text": str(e)}]
        except Exception as e:
            return [{"type": "text", "text": f"发送失败: {e}"}]

    elif name == "at_batch_test":
        cmds = arguments.get("commands", [])
        timeout = arguments.get("timeout", 1.0)
        if not cmds:
            return [{"type": "text", "text": "请提供要测试的命令列表。"}]
        try:
            results = handler.batch_test(cmds, timeout=timeout)
        except RuntimeError as e:
            return [{"type": "text", "text": str(e)}]

        pass_count = sum(1 for r in results if r["status"] == "PASS")
        ok_count = sum(1 for r in results if r["status"] == "OK")
        cme_count = sum(1 for r in results if r["status"] == "CME")
        err_count = sum(1 for r in results if r["status"] == "ERR")
        unk_count = sum(1 for r in results if r["status"] == "UNKNOWN")

        text = f"批量测试 {len(results)} 条命令:\n"
        text += f"  PASS(有数据): {pass_count}  OK(仅OK): {ok_count}  CME: {cme_count}  ERR: {err_count}  ???: {unk_count}\n\n"

        for r in results:
            flag = {"PASS": "✅", "OK": "✔️", "CME": "⚠️", "ERR": "❌", "UNKNOWN": "❓"}[r["status"]]
            data_str = " | ".join(r["data"][:2]) if r["data"] else "(empty)"
            text += f"  {flag} [{r['status']:4s}] {r['cmd']:35s} {data_str[:100]}\n"

        return [{"type": "text", "text": text.strip()}]

    elif name == "at_knowledge_search":
        query = arguments.get("query", "")
        standard = arguments.get("standard", "")
        tags = arguments.get("tags")
        results = kb.search(query=query, standard=standard, tags=tags)
        if not results:
            hint_parts = []
            if query:
                hint_parts.append(f"没有找到与 '{query}' 相关的命令")
            if standard:
                hint_parts.append(f"来源 '{standard}' 中无匹配")
            if tags:
                hint_parts.append(f"标签 {tags} 无匹配")
            hint = "。".join(hint_parts) if hint_parts else "知识库中没有匹配的命令。"
            return [{"type": "text", "text": f"{hint}。试试 at_knowledge_list 查看全部命令，或 at_knowledge_add 添加新命令。"}]
        text = f"找到 {len(results)} 条匹配命令:\n\n"
        for cmd in results:
            text += _format_knowledge_entry(cmd)
        return [{"type": "text", "text": text.strip()}]

    elif name == "at_knowledge_chipsets":
        chipsets = kb.list_chipsets()
        text = "可用芯片平台知识库:\n\n"
        for c in chipsets:
            rw = "✏️ 可写" if c["writable"] else "🔒 只读"
            text += f"  {c['name']:20s} {c['file']:20s} {c['count']:3d} 条  {rw}\n"
        text += "\n使用 at_knowledge_add 并指定 chipset=<平台名> 将命令写入对应平台文件。"
        text += "\n不指定 chipset 则默认写入 '_custom'（用户暂存区）。"
        return [{"type": "text", "text": text.strip()}]

    elif name == "at_knowledge_add":
        chipset = arguments.pop("chipset", "_custom")
        try:
            saved = kb.add_or_update(arguments, chipset=chipset)
            text = f"命令 `{saved['key']}` ({saved['name']}) 已保存到 {saved['source_file']}。\n\n"
            text += _format_knowledge_entry(saved)
            return [{"type": "text", "text": text.strip()}]
        except ValueError as e:
            return [{"type": "text", "text": str(e)}]

    elif name == "at_knowledge_list":
        standard = arguments.get("standard", "")
        commands = kb.list_all(standard=standard)
        if not commands:
            return [{"type": "text", "text": f"知识库中暂无命令{'（来源: ' + standard + '）' if standard else ''}。使用 at_knowledge_add 添加。"}]
        total = len(commands)
        text = f"共 {total} 条命令{(' (来源: ' + standard + ')') if standard else ''}:\n\n"
        for i, cmd in enumerate(commands, 1):
            expect_str = ", ".join(cmd.get("expect", [])) if cmd.get("expect") else "-"
            typ = cmd.get("type", "command")
            text += f"{i:3d}. [{typ:7s}] {cmd['key']:28s} {cmd['command']:40s} → {expect_str}\n"
            text += f"     {cmd['name']} — {cmd['description'][:80]}\n"
            text += "\n"
        return [{"type": "text", "text": text.strip()}]

    elif name == "at_knowledge_stats":
        stats = kb.get_stats()
        text = f"AT 命令知识库统计:\n\n"
        text += f"  命令总数: {stats['total_commands']}\n"
        text += f"  包内目录: {stats['package_dir']}\n"
        text += f"  用户目录: {stats['user_dir']}\n\n"
        text += "源文件分布:\n"
        for src in stats["source_files"]:
            text += f"  {src['file']:25s} — {src['count']} 条\n"
        text += "\n来源分布:\n"
        for k, v in stats.get("by_standard", {}).items():
            text += f"  {k:10s} — {v} 条\n"
        text += "\n分类分布:\n"
        for k, v in stats.get("by_category", {}).items():
            text += f"  {k:15s} — {v} 条\n"
        return [{"type": "text", "text": text.strip()}]

    else:
        return [{"type": "text", "text": f"未知工具: {name}"}]


def _format_config(config: dict) -> str:
    """Format config dict for display."""
    parity_names = {"N": "无", "E": "偶校验", "O": "奇校验", "M": "标记", "S": "空格"}
    return (
        f"  波特率: {config['baudrate']}\n"
        f"  数据位: {config['bytesize']}\n"
        f"  校验位: {parity_names.get(config['parity'], config['parity'])}\n"
        f"  停止位: {config['stopbits']}\n"
        f"  超时: {config['timeout']}s\n"
        f"  RTS/CTS: {'开' if config['rtscts'] else '关'}\n"
        f"  XON/XOFF: {'开' if config['xonxoff'] else '关'}"
    )


def _format_knowledge_entry(cmd: dict) -> str:
    """Format a single AT command knowledge entry for display."""
    typ = cmd.get("type", "command")
    typ_badge = {"urc": "📡URC", "data": "📤透传", "command": "📋AT"}.get(typ, f"[{typ}]")

    text = f"{'─'*60}\n"
    text += f"{typ_badge} {cmd.get('key', '?')} — {cmd.get('name', '?')}\n"
    text += f"   指令: {cmd.get('command', '?')}\n"
    text += f"   来源: {cmd.get('standard', '?')} ({cmd.get('source_file', '?')})\n"
    text += f"   分类: {cmd.get('category', '?')}\n"
    text += f"   超时: {cmd.get('timeout', 1)}s  重试: {cmd.get('retry', 1)}\n"

    expect = cmd.get("expect", [])
    if expect:
        text += f"   预期响应: {' → '.join(expect)}\n"

    text += f"   描述:\n"
    desc = cmd.get("description", "")
    for line in desc.strip().split("\n"):
        text += f"     {line.strip()}\n"

    params = cmd.get("params", [])
    if params:
        text += "   参数:\n"
        for p in params:
            t = p.get("type", "string")
            d = p.get("default", "")
            r = " (必填)" if p.get("required") else f" (默认={d})" if d != "" else ""
            text += f"     • {p.get('name', '?')}: {t}{r}\n"

    tags = cmd.get("tags", [])
    if tags:
        text += f"   标签: {', '.join(tags)}\n"

    text += "\n"
    return text


def main():
    """Sync entry point for the MCP server (stdio transport)."""
    import asyncio
    asyncio.run(_run())


async def _run():
    """Async runner for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
