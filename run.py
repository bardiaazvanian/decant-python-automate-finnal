"""Entry point for the Fragrantica automation pipeline."""
import argparse
import logging
import sys
from url_panel import run_panel


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    logging.basicConfig(level=level, format=fmt, handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("automation.log", encoding="utf-8"),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Fragrantica product data scraper")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    from orchestrator import run_pipeline
    run_pipeline()


if __name__ == "__main__":
    from config import config

    print("=== در حال اجرای پنل ثبت لینک فرگرنتیکا ===")
    print(f"آدرس پنل: http://localhost:{config.PANEL_PORT}")
    run_panel(port=config.PANEL_PORT, debug=True)
    main()
