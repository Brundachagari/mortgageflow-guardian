#!/usr/bin/env bash
# Package the Lambda functions for deployment.
#
# It copies src/ into build/<function>/ and adds the pydantic dependency (as
# Linux wheels, since Lambda runs on Linux) to the processor package. Run this
# BEFORE `terraform apply` so the zip files Terraform uploads are up to date.
#
#   ./scripts/build_lambdas.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/build"

echo "Cleaning $BUILD ..."
rm -rf "$BUILD"
mkdir -p "$BUILD/ingestion" "$BUILD/processor"

echo "Copying source into each package ..."
# The zip root must equal the package root so handlers resolve as
# "ingestion.handler.handler" and "processing.handler.handler".
cp -r "$ROOT/src/." "$BUILD/ingestion/"
cp -r "$ROOT/src/." "$BUILD/processor/"

echo "Installing pydantic (Linux wheels) into the processor package ..."
# boto3 is already provided by the Lambda runtime, so we do NOT bundle it.
python3 -m pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --target "$BUILD/processor" \
  "pydantic>=2.5" >/dev/null

# Trim caches to keep the zip small.
find "$BUILD" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "Build complete:"
echo "  $BUILD/ingestion"
echo "  $BUILD/processor"
