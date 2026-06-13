"""
testing.py - Testing Framework and Utilities

Provides:
  - TestFixture: Reusable test data management
  - MockAgent: Mock agent for testing
  - TestRunner: Custom test runner with reporting
  - Assertions: Domain-specific assertion helpers
  - TestSuite: Organized test collection
"""

import asyncio
import json
import os
import sys
import time
import traceback
import unittest
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass
class TestResult:
    """Result of a single test"""
    name: str
    passed: bool
    message: str = ""
    duration_ms: float = 0.0
    error_trace: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "passed": self.passed,
            "message": self.message, "duration_ms": round(self.duration_ms, 3),
            "has_error": bool(self.error_trace),
        }


@dataclass
class TestReport:
    """Test run report"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: float = 0.0
    results: List[TestResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total * 100 if self.total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total, "passed": self.passed,
            "failed": self.failed, "errors": self.errors,
            "skipped": self.skipped,
            "pass_rate": round(self.pass_rate, 2),
            "duration_ms": round(self.duration_ms, 2),
        }

    def to_text(self) -> str:
        lines = [
            "=" * 60,
            "TEST REPORT",
            "=" * 60,
            "Total: {}  Passed: {}  Failed: {}  Errors: {}  Skipped: {}".format(
                self.total, self.passed, self.failed, self.errors, self.skipped
            ),
            "Pass Rate: {:.1f}%".format(self.pass_rate),
            "Duration: {:.2f}ms".format(self.duration_ms),
            "-" * 60,
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append("[{}] {} ({:.1f}ms)".format(status, r.name, r.duration_ms))
            if r.message:
                lines.append("  -> {}".format(r.message))
            if r.error_trace:
                for tl in r.error_trace.split("\n")[:5]:
                    lines.append("  | {}".format(tl))
        return "\n".join(lines)


class TestFixture:
    """Test fixture manager for reusable test data"""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._setup_funcs: List[Callable] = []
        self._teardown_funcs: List[Callable] = []

    def add_data(self, key: str, value: Any):
        """Add test data"""
        self._data[key] = value

    def get(self, key: str, default=None) -> Any:
        """Get test data"""
        return self._data.get(key, default)

    def setup(self, func: Callable):
        """Register setup function"""
        self._setup_funcs.append(func)

    def teardown(self, func: Callable):
        """Register teardown function"""
        self._teardown_funcs.append(func)

    async def run_setup(self):
        """Run all setup functions"""
        for func in self._setup_funcs:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()

    async def run_teardown(self):
        """Run all teardown functions"""
        for func in self._teardown_funcs:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()

    def reset(self):
        """Reset fixture data"""
        self._data.clear()


class MockAgent:
    """Mock agent for testing without real LLM calls"""

    def __init__(self, name="mock_agent", default_response="ok"):
        self.name = name
        self.default_response = default_response
        self._responses: Dict[str, Any] = {}
        self._call_log: List[Dict] = []
        self._call_count = 0

    def set_response(self, tool_name: str, response: Any):
        """Set mock response for a specific tool"""
        self._responses[tool_name] = response

    def set_responses(self, responses: Dict[str, Any]):
        """Set multiple mock responses"""
        self._responses.update(responses)

    def get_call_log(self) -> List[Dict]:
        return self._call_log.copy()

    def get_call_count(self) -> int:
        return self._call_count

    def clear_log(self):
        self._call_log.clear()
        self._call_count = 0

    def mock_call(self, tool_name: str, args: Dict = None) -> Any:
        """Simulate a tool call"""
        self._call_count += 1
        self._call_log.append({
            "tool": tool_name, "args": args or {},
            "timestamp": time.time(),
        })
        if tool_name in self._responses:
            return self._responses[tool_name]
        return self.default_response


class AssertionHelpers:
    """Domain-specific assertion helpers"""

    @staticmethod
    def assert_tool_result(result: Any, expect_success: bool = True,
                           message: str = ""):
        """Assert that a tool result indicates success or failure"""
        if isinstance(result, dict):
            has_error = "error" in result and result["error"]
            if expect_success and has_error:
                raise AssertionError(
                    "{}: Expected success but got error: {}".format(
                        message or "Tool", result["error"]
                    )
                )
            if not expect_success and not has_error:
                raise AssertionError(
                    "{}: Expected failure but got success".format(message or "Tool")
                )
        elif not expect_success:
            pass  # Non-dict error result is expected

    @staticmethod
    def assert_has_keys(data: Dict, keys: List[str], message: str = ""):
        """Assert that dict has all required keys"""
        missing = [k for k in keys if k not in data]
        if missing:
            raise AssertionError(
                "{}: Missing keys: {}".format(message or "Dict", missing)
            )

    @staticmethod
    def assert_in_range(value: float, min_val: float, max_val: float,
                        message: str = ""):
        """Assert value is within range"""
        if not (min_val <= value <= max_val):
            raise AssertionError(
                "{}: {} not in range [{}, {}]".format(
                    message or "Value", value, min_val, max_val
                )
            )

    @staticmethod
    def assert_contains(container, item, message: str = ""):
        """Assert container contains item"""
        if item not in container:
            raise AssertionError(
                "{}: {} not found in {}".format(
                    message or "Assert", item, container
                )
            )

    @staticmethod
    def assert_not_none(value, message: str = ""):
        """Assert value is not None"""
        if value is None:
            raise AssertionError("{}: Value is None".format(message or "Assert"))

    @staticmethod
    def assert_raises(exception_type, func: Callable, *args, **kwargs):
        """Assert that function raises expected exception"""
        try:
            func(*args, **kwargs)
            raise AssertionError("Expected {} to be raised".format(exception_type.__name__))
        except exception_type:
            pass


class TestSuite:
    """Organized test suite with reporting"""

    def __init__(self, name: str = "test_suite"):
        self.name = name
        self._tests: List[Dict] = []
        self._fixture = TestFixture()
        self._assert = AssertionHelpers()
        self._report = TestReport()

    def test(self, name: str, func: Callable, tags: List[str] = None):
        """Register a test function"""
        self._tests.append({
            "name": name, "func": func,
            "tags": tags or [],
        })

    def add_fixture_data(self, key: str, value: Any):
        """Add fixture data"""
        self._fixture.add_data(key, value)

    def run(self, verbose: bool = False, filter_tags: List[str] = None) -> TestReport:
        """Run all registered tests"""
        import asyncio

        self._report = TestReport()
        filtered = self._tests

        if filter_tags:
            filtered = [t for t in self._tests
                        if any(tag in t.get("tags", []) for tag in filter_tags)]

        self._report.total = len(filtered)

        for test in filtered:
            result = TestResult(name=test["name"])
            start = time.time()
            try:
                # Run setup
                asyncio.get_event_loop().run_until_complete(
                    self._fixture.run_setup()
                )
                # Run test
                if asyncio.iscoroutinefunction(test["func"]):
                    asyncio.get_event_loop().run_until_complete(
                        test["func"](self)
                    )
                else:
                    test["func"](self)
                result.passed = True
                result.message = "OK"
            except AssertionError as e:
                result.passed = False
                result.message = str(e)
                result.error_trace = traceback.format_exc()
                self._report.failed += 1
            except Exception as e:
                result.passed = False
                result.message = str(e)
                result.error_trace = traceback.format_exc()
                self._report.errors += 1
            finally:
                # Run teardown
                try:
                    asyncio.get_event_loop().run_until_complete(
                        self._fixture.run_teardown()
                    )
                except Exception:
                    pass

            result.duration_ms = (time.time() - start) * 1000
            self._report.results.append(result)

            if result.passed:
                self._report.passed += 1
            if verbose:
                status = "PASS" if result.passed else "FAIL"
                print("[{}] {} ({:.1f}ms)".format(
                    status, test["name"], result.duration_ms
                ))

        self._report.duration_ms = sum(r.duration_ms for r in self._report.results)
        return self._report

    def run_async(self, verbose: bool = False) -> TestReport:
        """Run tests with async support"""
        return self.run(verbose=verbose)

    def get_report(self) -> TestReport:
        return self._report

    def export_json(self, filepath: str):
        """Export report to JSON"""
        report = self._report.to_dict()
        report["results"] = [r.to_dict() for r in self._report.results]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


# ── Convenience decorators ────────────────────────────────────────

def test_case(name: str, tags: List[str] = None):
    """Decorator to mark a method as a test case"""
    def decorator(func: Callable):
        func._is_test = True
        func._test_name = name
        func._test_tags = tags or []
        return func
    return decorator


def parametrize(test_name: str, params: List[Dict]):
    """Decorator to run a test with multiple parameter sets"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            for p in params:
                test_instance_name = "{}_{}".format(
                    test_name,
                    "_".join("{}={}".format(k, v) for k, v in p.items())
                )
                try:
                    func(self, **p)
                except AssertionError as e:
                    raise AssertionError(
                        "[{}] {}".format(test_instance_name, str(e))
                    )
        wrapper._is_parametrized = True
        wrapper._params = params
        return wrapper
    return decorator