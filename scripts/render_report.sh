#!/bin/sh
set -eu

python scripts/check_report_inputs.py
quarto render reports/final_report.qmd

test -f /app/reports/final_report.html
printf '\nReport successfully generated:\n\n/app/reports/final_report.html\n'
