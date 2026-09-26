#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

export PYTHONPATH="$DIR"

case "$1" in
    "test")
        pytest -v
        ;;
    "cli")
        shift
        python3 run_cli.py "$@"
        ;;
    "web"|"")
        echo "Starting Gemma 4 Edge Agent Web Visualizer on http://127.0.0.1:8000 ..."
        uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload
        ;;
    *)
        echo "Usage: ./run.sh [web|cli|test]"
        exit 1
        ;;
esac
