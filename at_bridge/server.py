"""MCP server exposing AT command tools for COM port device communication."""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from .serial_handler import SerialHandler
from .knowledge_store import KnowledgeStore

# --- Global state ---
handler = SerialHandler()
kb = KnowledgeStore()

# --- MCP Server ---
server = Server("at-bridge")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="at_list_ports",
            description="List all available COM/serial ports. Returns device name, description, hardware ID, VID/PID.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="at_configure",
            description="Configure serial port parameters (baud rate, data bits, parity, stop bits, flow control). Can be called before or after opening the port.",
            inputSchema={
                "type": "object",
                "properties": {
                    "baudrate": {
                        "type": "integer",
                        "description": "Baud rate. Common values: 9600, 115200, 921600, 1000000. Default 115200.",
                        "default": 115200,
                    },
                    "bytesize": {
                        "type": "integer",
                        "description": "Data bits: 5, 6, 7, 8. Default 8.",
                        "default": 8,
                    },
                    "parity": {
                        "type": "string",
                        "description": "Parity: N(None), E(Even), O(Odd), M(Mark), S(Space). Default N.",
                        "default": "N",
                    },
                    "stopbits": {
                        "type": "number",
                        "description": "Stop bits: 1, 1.5, 2. Default 1.",
                        "default": 1,
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Read timeout in seconds. Default 1.0.",
                        "default": 1.0,
                    },
                    "rtscts": {
                        "type": "boolean",
                        "description": "Hardware flow control RTS/CTS. Default false.",
                        "default": False,
                    },
                    "xonxoff": {
                        "type": "boolean",
                        "description": "Software flow control XON/XOFF. Default false.",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="at_open_port",
            description="Open the specified COM port and establish a serial connection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "port": {
                        "type": "string",
                        "description": "Serial port device name. Windows: COM3, COM4, etc.; Linux: /dev/ttyUSB0, /dev/ttyACM0, etc.",
                    },
                },
                "required": ["port"],
            },
        ),
        Tool(
            name="at_close_port",
            description="Close the currently opened COM port connection.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="at_auto_detect",
            description="Auto-detect all available COM ports. Tries common baud rates and sends an AT probe command to find responsive devices. Useful when unsure which port the device is connected to.",
            inputSchema={
                "type": "object",
                "properties": {
                    "baudrates": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Baud rate list to try. Default: 115200, 9600, 921600, 460800, 230400, 57600, 38400, 19200.",
                    },
                    "probe_timeout": {
                        "type": "number",
                        "description": "Timeout per probe in seconds. Smaller is faster but may miss slow devices. Default 0.5.",
                        "default": 0.5,
                    },
                    "test_command": {
                        "type": "string",
                        "description": "AT command used for probing. Default 'AT'.",
                        "default": "AT",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="at_send_command",
            description="Send an AT command to the connected device and read the response. Auto-prepends AT prefix (e.g. 'CSQ' becomes 'AT+CSQ'). Supports standard AT and extended AT+ commands.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "AT command to send. Examples: 'AT', 'AT+CGMI', 'AT+CSQ', 'AT+CREG?', or omit AT prefix like 'CGMI', '+CSQ'.",
                    },
                    "read_until": {
                        "type": "string",
                        "description": "Optional. Stop reading after encountering this string.",
                    },
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="at_batch_test",
            description="Batch-test AT commands. Sends a list of AT commands to the connected device and returns all results with automatic classification (PASS/OK/ERR/CME). Much more efficient than calling at_send_command repeatedly; good for validating a command list from the knowledge base.",
            inputSchema={
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of AT commands to test. Example: ['AT', 'AT+CSQ', 'AT+CGMI']. About 4ms each; for large batches, group by category in chunks of 20-30.",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout per command in seconds. Default 1.0.",
                        "default": 1.0,
                    },
                },
                "required": ["commands"],
            },
        ),
        Tool(
            name="at_knowledge_search",
            description="Search the AT command knowledge base. Supports filtering by keyword (key/name/description/AT string) and source (3gpp/vendor/custom).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword. Searches key, name, description, AT string. Examples: 'signal', 'tcp', 'CGMI'. Empty returns all commands.",
                    },
                    "standard": {
                        "type": "string",
                        "description": "Filter by source: 3gpp (standard), vendor (vendor-specific), custom (user-defined).",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tag filter (matches any tag). Example: ['urc', 'quectel'].",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="at_knowledge_chipsets",
            description="List available chipset knowledge base files. AI should call this first to know which platforms exist, then use at_knowledge_add to write to the appropriate platform file.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="at_knowledge_add",
            description="Add or update an AT command in the knowledge base. Stores in the specified chipset file (e.g. asr, quectel) or _custom. Use at_knowledge_chipsets to see available platforms.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "YAML slug/key, e.g. 'at+csq', 'at+qcell'. Must be unique.",
                    },
                    "command": {
                        "type": "string",
                        "description": "Actual AT command string. Example: 'AT+CSQ', 'AT+QCELL?'. Supports {param} placeholders.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Short name, e.g. 'Signal Quality'.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Function description including return value meanings. Multi-line supported.",
                    },
                    "chipset": {
                        "type": "string",
                        "description": "Target chipset platform. See at_knowledge_chipsets for options. Default '_custom' (user scratchpad). Common: asr, quectel.",
                    },
                    "standard": {
                        "type": "string",
                        "description": "Source: 3gpp / vendor / custom. Default vendor.",
                    },
                    "expect": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Expected response patterns. Example: ['+CSQ:', 'OK'].",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in seconds. Default 1.0.",
                    },
                    "retry": {
                        "type": "integer",
                        "description": "Retry count. Default 1.",
                    },
                    "params": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Parameter list. Each param has name/type/default/required.",
                    },
                    "type": {
                        "type": "string",
                        "description": "Command type: empty=AT command, urc=passive URC wait, data=transparent data send.",
                    },
                },
                "required": ["key", "command"],
            },
        ),
        Tool(
            name="at_knowledge_list",
            description="List all commands in the knowledge base, optionally filtered by source. Shows key, name, and expected response summary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "standard": {
                        "type": "string",
                        "description": "Filter by source: 3gpp / vendor / custom. Empty returns all.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="at_knowledge_stats",
            description="Show knowledge base statistics: total commands, per-source YAML file breakdown, source distribution.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
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
