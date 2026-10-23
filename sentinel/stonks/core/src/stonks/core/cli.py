import argparse
import logging
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def parse_step_arguments(prog: str, steps: Mapping[str, Any], argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("step", choices=sorted(steps))
    parser.add_argument("--trade-date", required=True, type=date.fromisoformat)
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    upper = level.upper()
    logging.basicConfig(level=upper, format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)


def run_step(steps: Mapping[str, Any], runtime: Any, step: str, trade_date: date) -> None:
    logger.info("step_started step=%s trade_date=%s", step, trade_date)
    step_class = steps[step]
    instance = step_class(runtime)
    instance.execute(trade_date)
    logger.info("step_finished step=%s trade_date=%s", step, trade_date)
