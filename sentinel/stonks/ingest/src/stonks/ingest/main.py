from collections.abc import Sequence

from stonks.core.cli import configure_logging, parse_step_arguments, run_step
from stonks.ingest.config.settings import Settings
from stonks.ingest.runtime import ingest_runtime
from stonks.ingest.steps.bars import BarsStep
from stonks.ingest.steps.symbols import SymbolsStep
from stonks.ingest.steps.universe import UniverseStep

STEPS = {"universe": UniverseStep, "symbols": SymbolsStep, "bars": BarsStep}


def main(argv: Sequence[str] | None = None) -> None:
    arguments = parse_step_arguments("stonks-ingest", STEPS, argv)
    settings = Settings()
    configure_logging(settings.logging.level)
    with ingest_runtime(settings) as runtime:
        run_step(STEPS, runtime, arguments.step, arguments.trade_date)


if __name__ == "__main__":
    main()
