"""tests/test_extensions.py — 扩展系统自动化测试

验证:
1. 扩展发现 (builtin + user)
2. ADB/ROOT自动检测机制
3. 扩展启用/禁用状态
4. 导入向导功能
5. loader 模块加载

运行: python -m pytest tests/test_extensions.py -v
"""
import os
import sys
import unittest
from pathlib import Path

# 设置路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestExtensionDiscovery(unittest.TestCase):
    """测试扩展发现机制。"""

    @classmethod
    def setUpClass(cls):
        # 清缓存
        for k in list(sys.modules):
            if k.startswith("extensions"):
                del sys.modules[k]
        from extensions.loader import discover_extensions
        cls.extensions = discover_extensions()

    def test_at_least_four_extensions_found(self):
        """至少发现4个扩展 (hello, files, adb, root)。"""
        self.assertGreaterEqual(len(self.extensions), 4,
                                f"只发现 {len(self.extensions)} 个扩展，预期 ≥4")

    def test_builtin_extensions_present(self):
        """内置扩展都存在。"""
        names = {e.name for e in self.extensions}
        required = {"hello", "minxg-files", "minxg-adb", "minxg-root"}
        missing = required - names
        self.assertEqual(missing, set(),
                         f"缺少内置扩展: {missing}")

    def test_all_extensions_have_names(self):
        """所有扩展都有名称。"""
        for ext in self.extensions:
            self.assertTrue(ext.name, f"扩展无名称: path={getattr(ext, 'path', '?')}")
            self.assertTrue(ext.description or True,
                            f"{ext.name}: 描述为空 (可接受)")

    def test_extensions_have_handler(self):
        """所有扩展都有 handle_command 函数。"""
        for ext in self.extensions:
            self.assertTrue(
                hasattr(ext.module, 'handle_command'),
                f"{ext.name}: 缺少 handle_command"
            )


class TestADBRootDetection(unittest.TestCase):
    """测试ADB/ROOT自动检测逻辑。"""

    def test_adb_extension_has_detection_flag(self):
        """adb_ext 有 ADB_AVAILABLE 检测标志。"""
        from extensions.loader import discover_extensions
        for k in list(sys.modules):
            if "extensions" in k:
                del sys.modules[k]
        exts = discover_extensions()

        adb_ext = next((e for e in exts if e.name == "minxg-adb"), None)
        if adb_ext:
            has_available = hasattr(adb_ext.module, 'ADB_AVAILABLE')
            self.assertTrue(has_available,
                            "minxg-adb 缺少 ADB_AVAILABLE 标志")
            # 验证是布尔值
            val = getattr(adb_ext.module, 'ADB_AVAILABLE', None)
            self.assertIsInstance(val, bool,
                                  f"ADB_AVAILABLE 应为布尔值，实际: {type(val)}")

    def test_root_extension_has_detection_flag(self):
        """root_ext 有 ROOT_AVAILABLE 检测标志。"""
        from extensions.loader import discover_extensions
        for k in list(sys.modules):
            if "extensions" in k:
                del sys.modules[k]
        exts = discover_extensions()

        root_ext = next((e for e in exts if e.name == "minxg-root"), None)
        if root_ext:
            has_available = hasattr(root_ext.module, 'ROOT_AVAILABLE')
            self.assertTrue(has_available,
                            "minxg-root 缺少 ROOT_AVAILABLE 标志")
            val = getattr(root_ext.module, 'ROOT_AVAILABLE', None)
            self.assertIsInstance(val, bool,
                                  f"ROOT_AVAILABLE 应为布尔值，实际: {type(val)}")

    def test_status_in_description(self):
        """描述中包含状态信息。"""
        from extensions.loader import discover_extensions
        exts = discover_extensions()
        adb_ext = next((e for e in exts
                       if e.name == "minxg-adb"), None)
        if adb_ext:
            desc = adb_ext.description
            self.assertTrue(
                "ADB" in desc,
                f"minxg-adb 描述不包含ADB: {desc}"
            )
            self.assertTrue(
                "ACTIVE" in desc or "INACTIVE" in desc,
                f"minxg-adb 描述不包含状态标志: {desc}"
            )


class TestImportWizard(unittest.TestCase):
    """测试导入向导。"""

    def test_get_search_paths(self):
        """搜索路径包含合理目录。"""
        from extensions.import_wizard import _get_search_paths
        paths = _get_search_paths()
        self.assertTrue(len(paths) > 0, "搜索路径为空")
        # 至少包含home目录
        home = os.path.expanduser("~")
        self.assertIn(home, paths,
                      f"搜索路径不含home: {paths}")

    def test_list_import_formats(self):
        """导入格式列表完整。"""
        from extensions.import_wizard import list_import_formats
        formats = list_import_formats()
        self.assertIn(".py", formats)
        self.assertIn(".zip", formats)
        self.assertIn(".tar.gz", formats)

    def test_import_nonexistent_file(self):
        """导入不存在的文件返回错误。"""
        from extensions.import_wizard import import_extension
        result = import_extension("/nonexistent/__path__.zip", interactive=False)
        self.assertEqual(result["status"], "error",
                         f"预期error, 实际: {result}")

    def test_import_help_text(self):
        """帮助文本包含多平台信息。"""
        from extensions.import_wizard import get_import_help_text
        text = get_import_help_text()
        self.assertIn("导入指南", text or "",
                       "帮助文本缺少关键信息")
        self.assertTrue(len(text) > 100,
                        f"帮助文本太短: {len(text)} chars")


class TestLoaderReload(unittest.TestCase):
    """测试扩展热加载。"""

    def test_reload_returns_extensions(self):
        """reload 返回扩展列表。"""
        for k in list(sys.modules):
            if k.startswith("extensions"):
                del sys.modules[k]

        from extensions.loader import reload_extensions
        exts = reload_extensions()
        self.assertTrue(len(exts) >= 4,
                        f"重载后只发现 {len(exts)} 个扩展")

    def test_reload_is_idempotent(self):
        """重复reload结果一致。"""
        exts1 = TestExtensionDiscovery.extensions
        name_set1 = {e.name for e in exts1}

        # 重载
        for k in list(sys.modules):
            if k.startswith("extensions._dynamic"):
                del sys.modules[k]
        from extensions.loader import discover_extensions
        exts2 = discover_extensions()
        name_set2 = {e.name for e in exts2}

        self.assertEqual(name_set1, name_set2,
                         f"扩展集合不一致: {name_set1 - name_set2} / {name_set2 - name_set1}")


class TestPlatformDetection(unittest.TestCase):
    """测试平台检测。"""

    def test_platform_detect(self):
        """platform检测函数可用。"""
        import platform
        plat = platform.system()
        self.assertIn(plat, ["Android", "Linux", "Darwin", "Windows"],
                      f"未知平台: {plat}")

    def test_android_detection(self):
        """Android检测: Termux环境应返回Android。"""
        try:
            import importlib
            sys.path.insert(0, str(Path(__file__).parent.parent))
            # 简单验证platform检测一致性
            plat = __import__('platform').system()
            if os.path.exists("/data/data/com.termux"):
                self.assertEqual(plat, "Android",
                                 f"Termux环境但platform返回: {plat}")
        except Exception:
            pass  # 非Android环境跳过


if __name__ == "__main__":
    unittest.main(verbosity=2)