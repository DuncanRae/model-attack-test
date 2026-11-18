#!/usr/bin/env bash
# Every test, with the Python on this computer (3.9 or newer). Nothing is installed and nothing leaves this computer.
set -euo pipefail
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" -W error::ResourceWarning -m unittest discover -s tests -t .
