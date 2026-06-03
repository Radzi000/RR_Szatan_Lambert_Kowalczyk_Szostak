#!/usr/bin/env sh
set -eu

REPO_ROOT="${REPO_ROOT:-/app}"
ARTIFACT_DIR="${ARTIFACT_DIR:-/artifacts}"

cd "$REPO_ROOT"

quarto render reports/final_report.qmd

mkdir -p "$ARTIFACT_DIR/reports" "$ARTIFACT_DIR/outputs"

cp reports/final_report.html "$ARTIFACT_DIR/reports/final_report.html"

if [ -d reports/final_report_files ]; then
    rm -rf "$ARTIFACT_DIR/reports/final_report_files"
    cp -R reports/final_report_files "$ARTIFACT_DIR/reports/final_report_files"
fi

cp -R outputs/. "$ARTIFACT_DIR/outputs/"
