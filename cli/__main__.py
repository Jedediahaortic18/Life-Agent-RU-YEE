"""Life-Agent-RU-YEE CLI"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx


BASE_URL = "http://localhost:8000"


async def cmd_chat(args: argparse.Namespace) -> None:
    """与 Agent 对话"""
    message = " ".join(args.message)
    print(f">>> {message}\n")

    async with httpx.AsyncClient(timeout=120.0) as client:
        if args.sync:
            resp = await client.post(
                f"{BASE_URL}/api/chat/sync",
                json={"message": message, "session_id": args.session},
            )
            data = resp.json()
            if data.get("success"):
                result = data["data"]["result"]
                print(result.get("summary", json.dumps(result, ensure_ascii=False, indent=2)))
            else:
                print(f"Error: {data.get('error', 'Unknown')}")
        else:
            # SSE 流式
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/chat",
                json={"message": message, "session_id": args.session},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if "content" in data:
                            print(data["content"], end="", flush=True)
                        elif "error" in data:
                            print(f"\nError: {data['error']}")
                        elif "tool" in data and "result" in data:
                            print(f"\n[Tool: {data['tool']}] ", end="")
                    elif line.startswith("event:"):
                        event = line[6:].strip()
                        if event == "done":
                            print()
                        elif event == "tool_call":
                            pass  # 等待 tool_output
    print()


async def cmd_plugins_list(args: argparse.Namespace) -> None:
    """列出插件"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/plugins")
        data = resp.json()
        if data.get("success"):
            for p in data["data"]:
                status = p["status"]
                caps = ", ".join(p.get("capabilities", [])) or "-"
                print(f"  [{status}] {p['name']} ({p['type']}) v{p['version']}  capabilities: {caps}")
        else:
            print(f"Error: {data}")


async def cmd_plugins_load(args: argparse.Namespace) -> None:
    """加载插件"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/plugins/{args.name}/load",
            params={"plugin_dir": args.dir} if args.dir else {},
        )
        print(resp.json())


async def cmd_devices_list(args: argparse.Namespace) -> None:
    """列出设备"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/devices")
        data = resp.json()
        if data.get("success"):
            if not data["data"]:
                print("  No connected devices")
            for d in data["data"]:
                print(f"  [{d['device_type']}] {d['device_id']} - {d['name']}")
        else:
            print(f"Error: {data}")


async def cmd_scaffold(args: argparse.Namespace) -> None:
    """生成插件脚手架"""
    output = Path(args.output or f"contrib/agents/{args.name}")
    output.mkdir(parents=True, exist_ok=True)

    # manifest.yaml
    manifest = {
        "manifest_version": 1,
        "name": args.name,
        "version": "0.1.0",
        "type": args.type,
        "description": f"{args.name} plugin",
        "entry_point": f"agent:{args.name.title().replace('_', '')}",
        "dependencies": {"plugins": [], "python": []},
    }
    if args.type == "agent":
        manifest["tools"] = []

    import yaml
    (output / "manifest.yaml").write_text(yaml.dump(manifest, allow_unicode=True, default_flow_style=False))

    # 骨架代码
    if args.type == "agent":
        (output / "agent.py").write_text(f'''"""{{args.name}} Agent"""
from core.interfaces.agent import BaseStreamAgent
from core.interfaces.tool import BaseTool


class {args.name.title().replace("_", "")}(BaseStreamAgent):

    @property
    def capabilities(self) -> list[str]:
        return []

    def get_model(self) -> str:
        return self.config.get("model", "ollama/phi3:mini")

    def get_tools(self) -> list[BaseTool]:
        return []

    def get_system_prompt(self, context: dict) -> str:
        return "You are a helpful assistant."
''')
        (output / "tools").mkdir(exist_ok=True)
        (output / "tools" / "__init__.py").touch()
        (output / "prompts").mkdir(exist_ok=True)
        (output / "prompts" / "system.j2").write_text("You are a helpful assistant.")

    (output / "__init__.py").touch()
    (output / "tests").mkdir(exist_ok=True)
    (output / "tests" / "__init__.py").touch()
    (output / "tests" / f"test_{args.name}.py").write_text(f'"""Tests for {args.name}"""\\n')

    print(f"Scaffold created at: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="life-agent", description="Life-Agent-RU-YEE CLI")
    sub = parser.add_subparsers(dest="command")

    # chat
    chat_p = sub.add_parser("chat", help="与 Agent 对话")
    chat_p.add_argument("message", nargs="+", help="消息内容")
    chat_p.add_argument("--sync", action="store_true", help="同步模式")
    chat_p.add_argument("--session", default=None, help="Session ID")

    # plugins
    plugins_p = sub.add_parser("plugins", help="插件管理")
    plugins_sub = plugins_p.add_subparsers(dest="plugins_command")

    plugins_sub.add_parser("list", help="列出插件")

    load_p = plugins_sub.add_parser("load", help="加载插件")
    load_p.add_argument("name", help="插件名称")
    load_p.add_argument("--dir", default="", help="插件目录")

    scaffold_p = plugins_sub.add_parser("scaffold", help="生成插件脚手架")
    scaffold_p.add_argument("--name", required=True, help="插件名称")
    scaffold_p.add_argument("--type", default="agent", choices=["agent", "memory", "search", "extension"])
    scaffold_p.add_argument("--output", default=None, help="输出目录")

    # devices
    devices_p = sub.add_parser("devices", help="设备管理")
    devices_sub = devices_p.add_subparsers(dest="devices_command")
    devices_sub.add_parser("list", help="列出已连接设备")

    args = parser.parse_args()

    if args.command == "chat":
        asyncio.run(cmd_chat(args))
    elif args.command == "plugins":
        if args.plugins_command == "list":
            asyncio.run(cmd_plugins_list(args))
        elif args.plugins_command == "load":
            asyncio.run(cmd_plugins_load(args))
        elif args.plugins_command == "scaffold":
            asyncio.run(cmd_scaffold(args))
        else:
            plugins_p.print_help()
    elif args.command == "devices":
        if args.devices_command == "list":
            asyncio.run(cmd_devices_list(args))
        else:
            devices_p.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
