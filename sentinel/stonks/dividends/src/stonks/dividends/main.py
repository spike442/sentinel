from collections.abc import Sequence

from stonks.core.cli import configure_logging, parse_step_arguments, run_step
from stonks.dividends.config.settings import Settings
from stonks.dividends.runtime import dividend_runtime
from stonks.dividends.steps.research import ResearchStep
from stonks.dividends.steps.validate import ValidateStep

STEPS = {"research": ResearchStep, "validate": ValidateStep}


def main(argv: Sequence[str] | None = None) -> None:
    arguments = parse_step_arguments("stonks-dividends", STEPS, argv)
    settings = Settings()
    configure_logging(settings.logging.level)
    with dividend_runtime(settings) as runtime:
        run_step(STEPS, runtime, arguments.step, arguments.trade_date)


if __name__ == "__main__":
    main()
