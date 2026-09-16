import argparse
import logging
from importlib import metadata as importlib_metadata
from pathlib import Path

from emberpost.post import dispatch_schedule_files
from emberpost.schedule_config import Frequency


def _package_version(distribution_name: str) -> str:
    """Return the installed distribution version."""
    try:
        return importlib_metadata.version(distribution_name)
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


def parse_args() -> argparse.Namespace:
    """Parse Emberpost command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Dispatch PagerDuty on-call schedules to Slack."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"emberpost {_package_version('emberpost')}",
    )
    parser.add_argument(
        "--schedule-file",
        nargs="+",
        type=Path,
        required=True,
        help="One or more schedule YAML files to process.",
    )
    parser.add_argument(
        "--frequency",
        choices=list(Frequency),
        required=True,
        help="Only process schedules matching this frequency.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve on-call users and print intended Slack changes without writing to Slack.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the Emberpost command-line application."""
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format=("%(levelname)-8s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"),
    )
    if args.log_level != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)

    dispatch_schedule_files(
        args.schedule_file, Frequency(args.frequency), dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
