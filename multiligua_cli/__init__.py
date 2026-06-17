"""multiligua_cli module - Command-line interface components."""

__all__ = ["main", "cli_main"]

def main():
    """CLI main entry point."""
    from multiligua_cli.main import main as _main
    _main()

def cli_main():
    """Alias for main()."""
    from multiligua_cli.main import main as _main
    _main()
