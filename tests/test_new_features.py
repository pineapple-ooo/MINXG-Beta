"""
Tests for new MINXG features:
- features.py (feature showcase)
- cost_tracker.py (cost tracking)
- themes.py (theme system)
- model_compare.py (model comparison)
"""
import pytest


# ═══════════════════════════════════════════════════════════════════
#  Features Tests
# ═══════════════════════════════════════════════════════════════════

def test_features_import():
    """Test that features module imports correctly."""
    from multiligua_cli import features
    assert hasattr(features, 'FEATURES')
    assert hasattr(features, 'SELLING_POINTS')
    assert hasattr(features, 'get_features_by_category')
    assert hasattr(features, 'get_feature_count')


def test_features_count():
    """Test that we have a good number of features."""
    from multiligua_cli.features import get_feature_count, get_category_count
    count = get_feature_count()
    categories = get_category_count()

    # Should have many features
    assert count >= 30, f"Expected 30+ features, got {count}"
    assert categories >= 5, f"Expected 5+ categories, got {categories}"


def test_features_by_category():
    """Test feature grouping by category."""
    from multiligua_cli.features import get_features_by_category
    by_cat = get_features_by_category()

    # Should have multiple categories
    assert len(by_cat) >= 5

    # Each category should have features
    for cat, feats in by_cat.items():
        assert len(feats) > 0, f"Category {cat} has no features"


def test_selling_points():
    """Test selling points structure."""
    from multiligua_cli.features import SELLING_POINTS

    assert len(SELLING_POINTS) >= 8

    for sp in SELLING_POINTS:
        assert "icon" in sp
        assert "title" in sp
        assert "desc" in sp
        assert len(sp["icon"]) <= 4  # Emoji
        assert len(sp["title"]) > 5


# ═══════════════════════════════════════════════════════════════════
#  Cost Tracker Tests
# ═══════════════════════════════════════════════════════════════════

def test_cost_tracker_import():
    """Test that cost_tracker module imports correctly."""
    from multiligua_cli import cost_tracker
    assert hasattr(cost_tracker, 'CostTracker')
    assert hasattr(cost_tracker, 'get_tracker')
    assert hasattr(cost_tracker, 'format_tokens')
    assert hasattr(cost_tracker, 'format_cost')


def test_cost_tracker_basic():
    """Test basic cost tracking."""
    from multiligua_cli.cost_tracker import CostTracker

    tracker = CostTracker()

    # Initially empty
    assert tracker.total_requests == 0
    assert tracker.total_input_tokens == 0
    assert tracker.total_output_tokens == 0
    assert tracker.total_cost == 0.0


def test_cost_tracker_record():
    """Test recording usage."""
    from multiligua_cli.cost_tracker import CostTracker

    tracker = CostTracker()
    tracker.record("openai", "gpt-4o", 1000, 500, latency_ms=200)

    assert tracker.total_requests == 1
    assert tracker.total_input_tokens == 1000
    assert tracker.total_output_tokens == 500
    assert tracker.total_cost > 0


def test_cost_tracker_estimate():
    """Test cost estimation."""
    from multiligua_cli.cost_tracker import CostTracker

    tracker = CostTracker()

    # OpenAI gpt-4o pricing: $2.50/1M input, $10/1M output
    cost = tracker.estimate_cost("openai", "gpt-4o", 1_000_000, 0)
    assert cost == 2.50

    cost = tracker.estimate_cost("openai", "gpt-4o", 0, 1_000_000)
    assert cost == 10.00


def test_cost_tracker_budget():
    """Test budget tracking."""
    from multiligua_cli.cost_tracker import CostTracker

    tracker = CostTracker(budget_usd=1.00)

    # Record some usage
    tracker.record("openai", "gpt-4o", 100_000, 50_000)

    assert tracker.budget_remaining < tracker.budget_usd
    assert tracker.budget_used_percent > 0


def test_format_helpers():
    """Test formatting helpers."""
    from multiligua_cli.cost_tracker import format_tokens, format_cost

    assert "K" in format_tokens(1000)
    assert "M" in format_tokens(1_000_000)
    assert format_tokens(500) == "500"

    assert "$" in format_cost(1.00)
    assert "¢" in format_cost(0.001)


# ═══════════════════════════════════════════════════════════════════
#  Themes Tests
# ═══════════════════════════════════════════════════════════════════

def test_themes_import():
    """Test that themes module imports correctly."""
    from multiligua_cli import themes
    assert hasattr(themes, 'Theme')
    assert hasattr(themes, 'THEMES')
    assert hasattr(themes, 'get_theme')
    assert hasattr(themes, 'set_theme')


def test_themes_available():
    """Test that we have multiple themes."""
    from multiligua_cli.themes import THEMES, THEME_ORDER

    assert len(THEMES) >= 6

    # Check some expected themes exist
    assert "blue-premium" in THEMES
    assert "dark-modern" in THEMES
    assert "matrix" in THEMES


def test_theme_structure():
    """Test theme data structure."""
    from multiligua_cli.themes import Theme

    theme = Theme(name="test", display_name="Test", description="A test theme")

    assert theme.name == "test"
    assert theme.display_name == "Test"
    assert hasattr(theme, 'bg_deep')
    assert hasattr(theme, 'accent')
    assert hasattr(theme, 'gold')


def test_theme_switching():
    """Test theme switching."""
    from multiligua_cli.themes import set_theme, get_theme, get_current_theme_name

    # Set a theme
    result = set_theme("matrix")
    assert result is True

    # Get current
    current = get_current_theme_name()
    assert current == "matrix"

    theme = get_theme()
    assert theme.name == "matrix"

    # Invalid theme
    result = set_theme("nonexistent")
    assert result is False


def test_list_themes():
    """Test listing themes."""
    from multiligua_cli.themes import list_themes

    themes = list_themes()
    assert len(themes) > 0

    for t in themes:
        assert "name" in t
        assert "display_name" in t
        assert "description" in t
        assert "is_current" in t


# ═══════════════════════════════════════════════════════════════════
#  Model Compare Tests
# ═══════════════════════════════════════════════════════════════════

def test_model_compare_import():
    """Test that model_compare module imports correctly."""
    from multiligua_cli import model_compare
    assert hasattr(model_compare, 'ModelResponse')
    assert hasattr(model_compare, 'ComparisonResult')
    assert hasattr(model_compare, 'ModelComparator')
    assert hasattr(model_compare, 'get_comparator')


def test_model_response():
    """Test ModelResponse dataclass."""
    from multiligua_cli.model_compare import ModelResponse

    resp = ModelResponse(
        provider="openai",
        model="gpt-4o",
        content="Hello!",
        input_tokens=10,
        output_tokens=5,
        latency_ms=100,
        cost_usd=0.001,
    )

    assert resp.provider == "openai"
    assert resp.model == "gpt-4o"
    assert resp.error is None


def test_comparison_result():
    """Test ComparisonResult."""
    from multiligua_cli.model_compare import ModelResponse, ComparisonResult
    import time

    now = time.time()
    responses = [
        ModelResponse("openai", "gpt-4o", "Response A", 10, 5, 100, 0.001),
        ModelResponse("anthropic", "claude-sonnet", "Response B", 10, 5, 200, 0.002),
    ]

    result = ComparisonResult(
        prompt="Test",
        responses=responses,
        started_at=now,
        finished_at=now + 0.5,
    )

    assert result.total_time_ms == 500
    assert result.fastest.model == "gpt-4o"
    assert result.cheapest.model == "gpt-4o"


def test_comparator_singleton():
    """Test global comparator instance."""
    from multiligua_cli.model_compare import get_comparator

    comp1 = get_comparator()
    comp2 = get_comparator()

    # Should be the same instance
    assert comp1 is comp2


# ═══════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════

def test_all_modules_importable():
    """Test that all new modules can be imported."""
    modules = [
        'multiligua_cli.features',
        'multiligua_cli.cost_tracker',
        'multiligua_cli.themes',
        'multiligua_cli.model_compare',
    ]

    for module_path in modules:
        __import__(module_path)
