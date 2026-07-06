"""Fail before Quarto starts a kernel when final-report inputs are absent."""

from pathlib import Path


REQUIRED_INPUTS = {
    "python -m strategy_development.local_implementation.reproduce": [
        "outputs/tables/strategy_summary.csv",
        "outputs/tables/reproducibility_manifest.json",
    ],
    "python -m strategy_development.local_implementation.run_fixed_15m_experiments": [
        "outputs/tables/fixed_15m_strategy_summary.csv",
        "outputs/tables/fixed_15m_train_validation_test_summary.csv",
        "outputs/tables/verification_metrics_taken_strats.csv",
    ],
    "python -m strategy_development.local_implementation.optimization.run_all_optimizations": [
        "outputs/tables/optimization_search_results.csv",
        "outputs/tables/selected_params.csv",
        "outputs/tables/train_validation_comparison.csv",
        "outputs/tables/optimization_verification_metrics.csv",
        "outputs/tables/verification_metrics_our_strats.csv",
    ],
}


def main() -> int:
    """Print actionable prerequisites and return nonzero if inputs are missing."""
    missing_by_command = {
        command: [path for path in paths if not Path(path).is_file()]
        for command, paths in REQUIRED_INPUTS.items()
    }
    missing_by_command = {command: paths for command, paths in missing_by_command.items() if paths}
    if not missing_by_command:
        print("Report preflight passed: all required generated outputs exist.")
        return 0

    print("ERROR: final report rendering cannot start because required outputs are missing:")
    for command, paths in missing_by_command.items():
        for path in paths:
            print(f"  - {path}")
        print(f"    Generate these outputs with: {command}")
    print("Then rerun: docker compose run --rm report")
    print("No preprocessing, optimization, or other pipeline stage was started automatically.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
