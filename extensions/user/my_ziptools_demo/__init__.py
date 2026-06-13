
import os, zipfile, json

EXTENSION_NAME = "my-ziptools"
EXTENSION_DESCRIPTION = "ZIP代码扫描器 — 扫描ZIP内的代码文件，生成语言统计+代码行数报告"
EXTENSION_VERSION = "1.0.0"
EXTENSION_PRIORITY = 60
EXTENSION_SOURCE = "user"
EXTENSION_ENABLED = True

def handle_command(args):
    subcmd = getattr(args, 'ziptools_cmd', None)
    if subcmd == "scan":
        path = getattr(args, 'zip_path', None)
        if not path:
            print("用法: minxg ext ziptools scan <zip_path>")
            return 1
        result = scan_zip(path)
        print_scan_report(result)
        return 0
    print("子命令: scan <zip_path>")
    return 0

def scan_zip(path):
    if not os.path.isfile(path):
        return {"error": "文件不存在"}
    try:
        zf = zipfile.ZipFile(path, 'r')
    except:
        return {"error": "无效的ZIP文件"}

    CODE_EXT = {'.py','.js','.ts','.go','.rs','.java','.c','.cpp','.h','.html','.css','.json','.yaml','.md','.sh'}
    found = []
    total_lines = 0
    langs = {}

    with zf:
        for name in zf.namelist():
            ext = os.path.splitext(name)[1].lower()
            if ext in CODE_EXT:
                try:
                    raw = zf.read(name)
                    lc = raw.count(b'\n')
                    found.append({"path": name, "lines": lc, "ext": ext,
                                  "preview": raw[:100].decode('utf-8','replace')})
                    total_lines += lc
                    langs[ext] = langs.get(ext, 0) + 1
                except:
                    pass

    found.sort(key=lambda x: -x['lines'])
    return {"files": len(found), "loc": total_lines, "langs": langs,
            "top": found[:10], "total_in_zip": len(zipfile.ZipFile(path).namelist())}

def print_scan_report(r):
    if "error" in r:
        print(f"Error: {r['error']}")
        return
    print(f"ZIP总文件: {r['total_in_zip']}")
    print(f"代码文件:  {r['files']}")
    print(f"代码行数:  {r['loc']}")
    print(f"语言: {', '.join(f'{l}={c}' for l,c in sorted(r['langs'].items(),key=lambda x:-x[1]))}")
    print(f"\n最大文件:")
    for f in r['top'][:5]:
        print(f"  {f['lines']:4d}L  {f['path']}")

def register_cli(subparsers):
    p = subparsers.add_parser("ziptools", help="ZIP代码扫描器")
    sp = p.add_subparsers(dest="ziptools_cmd")
    sp_scan = sp.add_parser("scan", help="扫描ZIP内的代码")
    sp_scan.add_argument("zip_path", help="ZIP文件路径")

def register_hooks(registry):
    pass
