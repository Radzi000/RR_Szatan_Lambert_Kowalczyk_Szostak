"""Tests for the Dockerized final-report workflow."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_report_preflight_fails_before_quarto_with_actionable_commands(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_report_inputs.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "outputs/tables/strategy_summary.csv" in result.stdout
    assert "run_fixed_15m_experiments" in result.stdout
    assert "run_all_optimizations" in result.stdout
    assert "docker compose run --rm report" in result.stdout
    assert "No preprocessing, optimization" in result.stdout


def test_docker_default_and_report_service_are_separate() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'CMD ["python", "-m", "strategy_development.local_implementation.reproduce"]' in dockerfile
    assert "python scripts/check_report_inputs.py && quarto render reports/final_report.qmd" in compose
