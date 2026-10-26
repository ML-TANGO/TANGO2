#!/usr/bin/env bash
# Prepare SPICE for a local (non-Docker) run — the Docker image does the same at
# build time. Fills spice/dist/ (the default SPICE_HOME) with:
#   spice-1.0.jar + lib/*.jar   from the pycocoevalcap wheel (no Python deps)
#   server/...SpiceServer.class compiled with a local JDK, or a JDK container
#   Stanford CoreNLP (~370 MB)  only with --with-corenlp; otherwise the service
#                               downloads it on first use
# Needs Java 8+ (java on PATH) to run SPICE afterwards.
# Usage: spice/setup.sh [--with-corenlp]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DIST="$HERE/dist"
PY="${PYTHON:-python3}"
mkdir -p "$DIST/server" "$DIST/lib"

if [ ! -f "$DIST/spice-1.0.jar" ]; then
  "$PY" "$HERE/fetch_jars.py" "$DIST"
fi

if [ ! -f "$DIST/server/edu/anu/spice/SpiceServer.class" ]; then
  if command -v javac >/dev/null 2>&1; then
    javac -classpath "$DIST/spice-1.0.jar" -d "$DIST/server" "$HERE/SpiceServer.java"
  else
    docker run --rm --user "$(id -u):$(id -g)" -v "$HERE:/src:ro" -v "$DIST:/dist" eclipse-temurin:8-jdk \
      javac -classpath /dist/spice-1.0.jar -d /dist/server /src/SpiceServer.java
  fi
fi

if [ "${1:-}" = "--with-corenlp" ]; then
  SPICE_HOME="$DIST" "$PY" -c "import sys; sys.path.insert(0, '$HERE/..'); from src.spice import ensure_corenlp; ensure_corenlp()"
fi
echo "SPICE files ready in $DIST"
