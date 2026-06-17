"""
内置扩展: 文件管理器 — 全平台文件浏览/选择工具

检测条件: 全平台自动启用
功能: 交互式文件浏览、多文件选择、目录遍历
      终端环境: 交互式编号选择
      非交互式环境: glob模式选择
"""
import os
import sys

EXTENSION_NAME = "minxg-files"
EXTENSION_DESCRIPTION = "全平台文件管理器扩展: 浏览目录、选择文件、多选操作"
EXTENSION_VERSION = "0"
EXTENSION_PRIORITY = 50
EXTENSION_SOURCE = "builtin"
EXTENSION_ENABLED = True  


def handle_command(args) -> int:
    """CLI命令: minxg ext files <subcommand>"""
    subcmd = getattr(args, 'files_subcommand', None)

    if subcmd == "browse":
        return _browse_cli(args)

    elif subcmd == "select":
        return _select_cli(args)

    else:
        print("文件管理器子命令:")
        print("  browse [DIR]    浏览目录 (交互式)")
        print("  select PATTERN  按模式选择文件")
        return 0


def _browse_cli(args) -> int:
    """打开交互式文件浏览器。"""
    directory = getattr(args, 'directory', os.getcwd())
    directory = os.path.expanduser(directory)

    if not os.path.isdir(directory):
        print(f"目录不存在: {directory}")
        return 1

    _display_directory(directory)
    return 0


def _display_directory(directory: str, depth: int = 0, max_items: int = 50):
    """显示目录内容。"""
    max_depth = 2
    if depth > max_depth:
        return

    items = sorted(os.listdir(directory), key=lambda x: (
        not os.path.isdir(os.path.join(directory, x)),
        x.lower()
    ))

    indent = "  " * depth
    for item in items[:max_items]:
        full = os.path.join(directory, item)
        if os.path.isdir(full):
            size = len(os.listdir(full))
            print(f"{indent}📁 {item}/ ({size} items)")
            if depth < max_depth:
                _display_directory(full, depth + 1, 15)
        else:
            size = os.path.getsize(full)
            if size < 1024:
                sz = f"{size}B"
            elif size < 1024*1024:
                sz = f"{size/1024:.1f}KB"
            else:
                sz = f"{size/(1024*1024):.1f}MB"
            print(f"{indent}📄 {item} ({sz})")

    if len(items) > max_items:
        print(f"{indent}... (+{len(items)-max_items} more)")


def _select_cli(args) -> int:
    """按模式选择文件。"""
    pattern = getattr(args, 'pattern', '*')
    directory = getattr(args, 'directory', os.getcwd())
    directory = os.path.expanduser(directory)

    import fnmatch
    found = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                found.append(os.path.join(root, f))
        if len(found) > 200:
            break

    for fp in found[:50]:
        rel = os.path.relpath(fp, directory)
        size = os.path.getsize(fp)
        print(f"  {rel:50s} {size:>8d} bytes")

    print(f"\n找到 {len(found)} 个匹配文件")
    return 0


def register_cli(subparsers) -> None:
    """注册命令行子命令。"""
    p = subparsers.add_parser("files", help="全平台文件管理器")
    sub_p = p.add_subparsers(dest="files_subcommand")

    sp_browse = sub_p.add_parser("browse", help="浏览目录")
    sp_browse.add_argument("directory", nargs="?", default=os.getcwd(), help="目录路径")

    sp_select = sub_p.add_parser("select", help="选择文件")
    sp_select.add_argument("pattern", help="文件模式 (如 *.py)")
    sp_select.add_argument("--directory", default=os.getcwd(), help="搜索目录")


def register_hooks(registry) -> None:
    """注册AI工具钩子。"""
    @registry.tool_interceptor(priority=40)
    def inject_file_tools(tools_list):
        tools_list.append({
            "name": "file_browse",
            "description": "浏览目录结构 (全平台)",
            "category": "file",
        })
        tools_list.append({
            "name": "file_select",
            "description": "按模式选择文件 (glob匹配, 全平台)",
            "category": "file",
        })
        return tools_list