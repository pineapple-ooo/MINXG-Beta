"""
extensions/import_wizard.py — 全平台扩展包导入向导 v1.0.0

提供交互式/非交互式扩展包导入功能:
- 交互式: 终端文件浏览器选择 .py/.zip/.tar.gz 扩展包
- 非交互式: 直接通过路径导入
- Android: 支持文件管理器模式 (列出常用目录)
- 全平台: 自动检测交互式/非交互式环境
""""
from __future__ import annotations
import os
import sys
import shutil
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional






def _get_platform() -> str:
    import platform
    return platform.system()


def _is_android() -> bool:
    return _get_platform() == "Android"


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()






def _get_search_paths() -> List[str]:
    """返回该平台常用的文件搜索目录。""""
    home = os.path.expanduser("~")
    plat = _get_platform()

    paths = [home, os.getcwd()]

    if plat == "Android":
        
        paths.extend([
            "/storage/emulated/0",
            "/storage/emulated/0/Download",
            "/storage/emulated/0/Documents",
            "/storage/emulated/0/Android/data",
            os.path.join(home, "storage", "downloads"),
            os.path.join(home, "storage", "shared"),
        ])
    elif plat == "Linux":
        paths.extend([
            os.path.join(home, "Downloads"),
            os.path.join(home, "Documents"),
            "/tmp",
        ])
    elif plat == "Windows":
        paths.extend([
            os.path.join(home, "Downloads"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Desktop"),
        ])
    elif plat == "Darwin":
        paths.extend([
            os.path.join(home, "Downloads"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Desktop"),
        ])

    
    return [p for p in paths if os.path.isdir(p)]






VALID_EXTENSIONS = (".py", ".zip", ".tar.gz", ".tgz")


FILE_ICONS = {
    ".py": "[PY]",
    ".zip": "[ZIP]",
    ".tar.gz": "[TAR]",
    ".tgz": "[TAR]",
    ".dir": "[DIR]",
    ".other": "[   ]",
}


def _get_file_icon(path: str) -> str:
    if os.path.isdir(path):
        return FILE_ICONS[".dir"]
    name = path.lower()
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        return FILE_ICONS[".tar.gz"]
    for ext in (".py", ".zip"):
        if name.endswith(ext):
            return FILE_ICONS[ext]
    return FILE_ICONS[".other"]


def _get_size_str(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f}KB"
    return f"{size_bytes/(1024*1024):.1f}MB"






def _browse_files(search_dir: str = None, filter_ext: bool = True) -> Optional[str]:
    """
    交互式文件浏览器。

    用户从常用目录开始浏览，可以用数字选择文件。
    输入 'd' 进入子目录，输入 '..' 返回上级目录。

    返回选中的文件路径，或 None 表示取消。
    """"
    paths = _get_search_paths()

    
    if search_dir:
        search_dir = os.path.expanduser(search_dir)
        if os.path.isdir(search_dir) and search_dir not in paths:
            paths.insert(0, search_dir)

    if not _is_interactive():
        return _non_interactive_browse(paths, filter_ext)

    print()
    print("═" * 50)
    print("  MINXG 扩展包导入向导 — 文件浏览器")
    print("═" * 50)
    print()
    print("  支持的格式: .py (单文件)  .zip (压缩包)  .tar.gz / .tgz (压缩包)")
    print("  操作: 输入数字选择  d=进入子目录  ..=返回上级  q=取消")
    print()

    
    if len(paths) == 1 and os.path.isdir(paths[0]):
        current_dir = paths[0]
    else:
        
        current_dir = _choose_start_directory(paths)

    if current_dir is None:
        return None

    
    while True:
        result = _browse_directory(current_dir, filter_ext)
        if result is None:
            return None  
        if result == "..":
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                continue
            current_dir = parent
            continue
        full_path = os.path.join(current_dir, result)
        if os.path.isdir(full_path):
            current_dir = full_path
            continue
        
        if filter_ext:
            fname = full_path.lower()
            if not (fname.endswith(VALID_EXTENSIONS)):
                print(f"\n  不支持的文件格式: {result}")
                print(f"  支持的格式: {', '.join(VALID_EXTENSIONS)}")
                continue
        return full_path


def _choose_start_directory(paths: List[str]) -> Optional[str]:
    """让用户选择起始目录。""""
    print("  选择起始目录:")
    for i, p in enumerate(paths):
        print(f"    [{i+1}] {p}")
    print(f"    [0] 手动输入路径")

    try:
        choice = input("\n  选择 [1]: ").strip()
        if not choice:
            choice = "1"
        idx = int(choice)
        if 0 < idx <= len(paths):
            return paths[idx - 1]
        elif idx == 0:
            manual = input("  输入目录路径: ").strip()
            manual = os.path.expanduser(manual)
            if os.path.isdir(manual):
                return manual
            print(f"  目录不存在: {manual}")
            return None
    except (ValueError, EOFError, KeyboardInterrupt):
        pass
    return None


def _browse_directory(directory: str, filter_ext: bool) -> Optional[str]:
    """浏览目录内容，让用户选择文件或进入子目录。""""
    print()
    print(f"  📂 {directory}")
    print()

    try:
        items = sorted(os.listdir(directory), key=lambda x: (
            not os.path.isdir(os.path.join(directory, x)),
            x.lower()
        ))
    except PermissionError:
        print("  无法访问此目录 (权限不足)")
        return ".."

    
    print(f"  [..] 返回上级目录")
    print()

    
    display_items = []
    for item in items:
        full = os.path.join(directory, item)
        if os.path.isdir(full) and not item.startswith('.'):
            display_items.append(item)
        elif os.path.isfile(full):
            if not filter_ext or item.lower().endswith(VALID_EXTENSIONS):
                display_items.append(item)

    if not display_items:
        print("  (此目录下没有可导入的文件)")
        return ".."

    
    page = 0
    page_size = 20
    total = len(display_items)

    while True:
        start = page * page_size
        chunk = display_items[start:start + page_size]

        for i, item in enumerate(chunk):
            full = os.path.join(directory, item)
            icon = _get_file_icon(full)
            if os.path.isdir(full):
                print(f"  [{start + i + 1:>3}] {icon} {item}/")
            else:
                size = _get_size_str(os.path.getsize(full))
                print(f"  [{start + i + 1:>3}] {icon} {item}  ({size})")

        if total > page_size:
            print(f"\n  第{page+1}/{(total-1)//page_size+1}页 (共{total}项)")
            print(f"  输入 n=下一页  p=上一页")

        print()
        try:
            choice = input("  选择 (数字/d/../q): ").strip().lower()
            if not choice:
                continue

            if choice == "q":
                return None
            if choice == "..":
                return ".."
            if choice == "n" and total > page_size and page < (total - 1) // page_size:
                page += 1
                continue
            if choice == "p" and page > 0:
                page -= 1
                continue

            
            idx = int(choice) - 1
            if 0 <= idx < total:
                return display_items[idx]
            print(f"  无效选项，请输入1-{total}之间的数字")

        except ValueError:
            print("  输入无效")
        except (EOFError, KeyboardInterrupt):
            return None


def _non_interactive_browse(paths: List[str], filter_ext: bool) -> Optional[str]:
    """非交互式环境: 在常用目录搜索扩展包文件。""""
    for d in paths:
        try:
            for item in sorted(os.listdir(d)):
                full = os.path.join(d, item)
                if os.path.isfile(full):
                    if not filter_ext or item.lower().endswith(VALID_EXTENSIONS):
                        return full
        except PermissionError:
            continue
    return None






def import_extension(path: str, interactive: bool = True) -> Dict[str, Any]:
    """
    导入扩展包到 extensions/user/ 目录。

    流程:
      1. 如果path为空 → 打开交互式文件浏览器 (interactive=True)
      2. 验证文件格式 (.py/.zip/.tar.gz/.tgz)
      3. 复制到 extensions/user/ 目录
      4. 如果是.zip/.tar.gz自动解压
      5. 验证 __init__.py 存在
      6. 触发热加载

    Args:
        path: 扩展包路径 (为空则打开交互式浏览器)
        interactive: 是否允许交互式操作

    Returns:
        {"status": "success"/"error", "ext_name": ..., "dest": ...}
    """"
    
    if not path:
        if interactive and _is_interactive():
            path = _browse_files(filter_ext=True)
        else:
            path = _non_interactive_browse(_get_search_paths(), filter_ext=True)

        if not path:
            return {
                "status": "error",
                "error": "未选择任何文件。请通过 --path 参数指定扩展包路径，或在交互式终端中浏览选择。",
                "hint": "用法: minxg ext import --path /path/to/extension.zip"
            }

    path = os.path.expanduser(path)

    
    if not os.path.isfile(path):
        return {"status": "error", "error": f"文件不存在: {path}"}

    fname = os.path.basename(path)
    fl = fname.lower()
    if not fl.endswith(VALID_EXTENSIONS):
        return {
            "status": "error",
            "error": f"不支持的格式: {fname}",
            "supported": list(VALID_EXTENSIONS),
        }

    
    user_ext_dir = Path(__file__).parent / "user"
    user_ext_dir.mkdir(parents=True, exist_ok=True)

    ext_name = fname.rsplit(".", 1)[0]
    if ext_name.endswith(".tar"):
        ext_name = ext_name.rsplit(".", 1)[0]

    dest_dir = user_ext_dir / ext_name

    
    try:
        if fl.endswith(".py"):
            
            dest_dir.mkdir(exist_ok=True)
            dest_file = dest_dir / "__init__.py"
            shutil.copy2(path, dest_file)
            source_type = "py"

        elif fl.endswith(".zip"):
            
            import zipfile
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            dest_dir.mkdir()
            with zipfile.ZipFile(path, 'r') as zf:
                zf.extractall(dest_dir)
            source_type = "zip"

        elif fl.endswith((".tar.gz", ".tgz")):
            
            import tarfile
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            dest_dir.mkdir()
            with tarfile.open(path, 'r:*') as tf:
                tf.extractall(dest_dir)
            source_type = "tar.gz"

        
        init_file = dest_dir / "__init__.py"
        if not init_file.exists():
            
            found = None
            for candidate in dest_dir.rglob("__init__.py"):
                found = candidate
                break
            if not found:
                return {
                    "status": "error",
                    "error": f"扩展包缺少 __init__.py 入口文件",
                    "dest": str(dest_dir),
                    "contents": sorted(os.listdir(str(dest_dir)))[:10],
                }
            
            sub_dir = found.parent
            if sub_dir != dest_dir:
                for item in os.listdir(str(sub_dir)):
                    src = os.path.join(str(sub_dir), item)
                    dst = os.path.join(str(dest_dir), item)
                    if not os.path.exists(dst):
                        shutil.move(src, dst)

        return {
            "status": "success",
            "ext_name": ext_name,
            "dest": str(dest_dir),
            "source_type": source_type,
            "source_path": path,
            "hint": f"扩展 '{ext_name}' 已安装到 extensions/user/{ext_name}/。运行 'minxg ext reload {ext_name}' 立即加载。",
        }

    except Exception as e:
        return {"status": "error", "error": f"导入失败: {e}", "path": path}


def list_import_formats() -> Dict[str, str]:
    """返回支持的导入格式说明。""""
    return {
        ".py": "单文件Python扩展 — 包含 __init__.py 的单个Python文件",
        ".zip": "ZIP压缩包 — 包含扩展目录结构的ZIP文件",
        ".tar.gz": "TAR.GZ压缩包 — 包含扩展目录结构的TAR.GZ文件",
        ".tgz": "TGZ压缩包 — 同.tar.gz",
    }


def get_import_help_text() -> str:
    """返回导入帮助文本。""""
    plat = _get_platform()
    paths = _get_search_paths()

    text = f"""
MINXG 扩展包导入指南
══════════════════════════════════════════════════════

当前平台: {plat}

支持的扩展包格式:
  .py       单文件Python扩展
  .zip      ZIP压缩包 (包含扩展目录)
  .tar.gz   压缩包 (包含扩展目录)

导入方式:

  1. 交互式导入 (推荐):
     minxg ext import
     → 打开文件浏览器，浏览选择扩展包

  2. 直接路径导入:
     minxg ext import --path /path/to/my_ext.zip
     → 直接指定文件路径

  3. Python导入:
     from extensions.import_wizard import import_extension
     result = import_extension("/path/to/my_ext.zip")

自动搜索目录:""""

    for p in paths:
        text += f"\n  • {p}"

    text += f"""

安装后:
  minxg ext list           # 查看已安装扩展
  minxg ext reload NAME    # 热加载扩展

扩展包结构:
  my_extension/
  ├── __init__.py          # 入口: def register(api)
  └── manifest.yaml        # 元数据 (可选)
""""
    return text






def handle_import_command(args) -> int:
    """CLI命令处理: minxg ext import [--path PATH] [--help]""""
    path = getattr(args, 'path', None)

    if getattr(args, 'help', False):
        print(get_import_help_text())
        return 0

    result = import_extension(path or "", interactive=True)

    if result["status"] == "success":
        print(f"\n✅ 扩展导入成功!")
        print(f"   名称: {result['ext_name']}")
        print(f"   位置: {result['dest']}")
        print(f"   来源: {result['source_type']} ({os.path.basename(result['source_path'])})")
        print(f"\n   {result['hint']}")
        return 0
    else:
        print(f"\n❌ 导入失败: {result['error']}")
        if "supported" in result:
            print(f"   支持的格式: {', '.join(result['supported'])}")
        if "contents" in result:
            print(f"   包内容: {', '.join(result['contents'])}")
        print(f"\n   💡 提示: minxg ext import --help 查看使用帮助")
        return 1