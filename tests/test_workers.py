"""
MINXG Worker Tests — Comprehensive test suite for all workers.
"""
import pytest
import tempfile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
#  File Workers Tests
# ═══════════════════════════════════════════════════════════════════

def test_file_read_worker():
    """Test file read worker."""
    from minxg.workers.file.file_workers import FileReadWorker

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello, World!\nLine 2\nLine 3")
        f.flush()

        worker = FileReadWorker()
        result = worker.execute(f.name)

        assert result["lines"] == 3
        assert "Hello, World!" in result["content"]

    Path(f.name).unlink()


def test_file_write_worker():
    """Test file write worker."""
    from minxg.workers.file.file_workers import FileWriteWorker

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        worker = FileWriteWorker()
        result = worker.execute(str(path), "Test content")

        assert result["bytes"] == len("Test content")
        assert path.exists()
        assert path.read_text() == "Test content"


def test_file_hash_worker():
    """Test file hash worker."""
    from minxg.workers.file.file_workers import FileHashWorker

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test")
        f.flush()

        worker = FileHashWorker()
        result = worker.execute(f.name, "sha256")

        assert "hash" in result
        assert len(result["hash"]) == 64  # SHA-256 hex length

    Path(f.name).unlink()


# ═══════════════════════════════════════════════════════════════════
#  Network Workers Tests
# ═══════════════════════════════════════════════════════════════════

def test_url_parse_worker():
    """Test URL parse worker."""
    from minxg.workers.network.network_workers import URLParseWorker

    worker = URLParseWorker()
    result = worker.execute("https://example.com:8080/path?key=value#fragment")

    assert result["scheme"] == "https"
    assert result["hostname"] == "example.com"
    assert result["port"] == 8080
    assert result["path"] == "/path"


def test_ping_worker():
    """Test ping worker."""
    from minxg.workers.network.network_workers import PingWorker

    worker = PingWorker()
    result = worker.execute("127.0.0.1", count=1, timeout=2)

    assert "host" in result
    assert result["host"] == "127.0.0.1"


# ═══════════════════════════════════════════════════════════════════
#  Crypto Workers Tests
# ═══════════════════════════════════════════════════════════════════

def test_hash_worker():
    """Test hash worker."""
    from minxg.workers.crypto.crypto_workers import HashWorker

    worker = HashWorker()
    result = worker.execute("hello", "sha256")

    assert result["algorithm"] == "sha256"
    assert result["hash"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_hmac_worker():
    """Test HMAC worker."""
    from minxg.workers.crypto.crypto_workers import HMACWorker

    worker = HMACWorker()
    result = worker.execute("message", "secret", "sha256")

    assert "hmac" in result
    assert result["algorithm"] == "sha256"


def test_random_bytes_worker():
    """Test random bytes worker."""
    from minxg.workers.crypto.crypto_workers import RandomBytesWorker

    worker = RandomBytesWorker()
    result = worker.execute(32, "hex")

    assert len(result["bytes"]) == 64  # 32 bytes = 64 hex chars


# ═══════════════════════════════════════════════════════════════════
#  Math Workers Tests
# ═══════════════════════════════════════════════════════════════════

def test_calculator_worker():
    """Test calculator worker."""
    from minxg.workers.math.math_workers import CalculatorWorker

    worker = CalculatorWorker()
    result = worker.execute("2 + 3 * 4")

    assert result["result"] == 14


def test_statistics_worker():
    """Test statistics worker."""
    from minxg.workers.math.math_workers import StatisticsWorker

    worker = StatisticsWorker()
    result = worker.execute([1, 2, 3, 4, 5])

    assert result["mean"] == 3.0
    assert result["median"] == 3
    assert result["min"] == 1
    assert result["max"] == 5


def test_prime_worker():
    """Test prime worker."""
    from minxg.workers.math.math_workers import PrimeWorker

    worker = PrimeWorker()
    assert worker.execute(7, "is_prime")["is_prime"] is True
    assert worker.execute(10, "is_prime")["is_prime"] is False

    result = worker.execute(11, "primes_up_to")
    assert result["count"] == 5  # 2, 3, 5, 7, 11


def test_geometry_worker():
    """Test geometry worker."""
    from minxg.workers.math.math_workers import GeometryWorker
    import math

    worker = GeometryWorker()
    result = worker.execute("circle", radius=1)

    assert abs(result["area"] - math.pi) < 0.001
    assert abs(result["circumference"] - 2 * math.pi) < 0.001


# ═══════════════════════════════════════════════════════════════════
#  Text Workers Tests
# ═══════════════════════════════════════════════════════════════════

def test_text_process_worker():
    """Test text process worker."""
    from minxg.workers.text.text_workers import TextProcessWorker

    worker = TextProcessWorker()
    result = worker.execute("Hello World", "word_count")

    assert result["word_count"] == 2
    assert result["line_count"] == 1


def test_regex_worker():
    """Test regex worker."""
    from minxg.workers.text.text_workers import RegexWorker

    worker = RegexWorker()
    result = worker.execute("abc123def", r"\d+", "findall")

    assert result["matches"] == ["123"]
    assert result["count"] == 1


def test_text_diff_worker():
    """Test text diff worker."""
    from minxg.workers.text.text_workers import TextDiffWorker

    worker = TextDiffWorker()
    result = worker.execute("hello world", "hello there", "similarity")

    assert "similarity" in result
    assert 0 < result["similarity"] < 1


# ═══════════════════════════════════════════════════════════════════
#  System Workers Tests
# ═══════════════════════════════════════════════════════════════════

def test_system_info_worker():
    """Test system info worker."""
    from minxg.workers.system.system_workers import SystemInfoWorker

    worker = SystemInfoWorker()
    result = worker.execute()

    assert "platform" in result
    assert "python_version" in result
    assert "hostname" in result


def test_disk_worker():
    """Test disk worker."""
    from minxg.workers.system.system_workers import DiskWorker

    worker = DiskWorker()
    result = worker.execute("/")

    assert "total_bytes" in result
    assert "used_bytes" in result
    assert "free_bytes" in result


def test_uptime_worker():
    """Test uptime worker."""
    from minxg.workers.system.system_workers import UptimeWorker

    worker = UptimeWorker()
    result = worker.execute()

    assert "uptime_seconds" in result
    assert "uptime_human" in result
    assert "boot_time" in result


# ═══════════════════════════════════════════════════════════════════
#  AI Workers Tests
# ═══════════════════════════════════════════════════════════════════

def test_classify_worker():
    """Test classify worker."""
    from minxg.workers.ai.ai_workers import ClassifyWorker

    worker = ClassifyWorker()
    result = worker.execute("I love programming in Python", ["python", "java", "rust"])

    assert "predicted" in result
    assert "categories" in result


def test_extract_worker():
    """Test extract worker."""
    from minxg.workers.ai.ai_workers import ExtractWorker

    worker = ExtractWorker()
    result = worker.execute("Contact us at test@example.com or visit https://example.com", ["email", "url"])

    assert "emails" in result["entities"]
    assert "urls" in result["entities"]
    assert "test@example.com" in result["entities"]["emails"]


# ═══════════════════════════════════════════════════════════════════
#  Registry Tests
# ═══════════════════════════════════════════════════════════════════

def test_registry_list():
    """Test worker registry listing."""
    from minxg.workers.registry import WorkerRegistry

    workers = WorkerRegistry.list_all()
    # Registry may be empty if auto-discovery didn't find workers
    assert isinstance(workers, list)


def test_registry_execute():
    """Test worker registry execution."""
    from minxg.workers.registry import WorkerRegistry

    result = WorkerRegistry.execute("nonexistent_worker")
    assert "error" in result  # Should return error for unknown worker
