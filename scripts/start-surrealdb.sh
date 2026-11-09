#!/usr/bin/env bash
#
# Start `surreal` in the background for the test suite and wait until it
# answers on /health, failing if it never does - so a server that cannot start
# fails the job rather than letting every integration test skip.
#
# Buckets are gated behind the `files` experimental capability on 3.x, so the
# server is first started with it: without it the file tests skip rather than
# run. 2.0 and 2.1 ignore the variable, but 2.2 and 2.3 reject it as an
# unknown target, and from 4.0 buckets are stable and the target is gone - so a
# server that exits on the flag is started again without it. The tests detect
# the capability rather than the version, so they still run or skip correctly.

set -euo pipefail

ENDPOINT="${SURREALDB_ENDPOINT:-http://localhost:8000}"
TIMEOUT="${SURREALDB_START_TIMEOUT:-30}"
LOG="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/surreal.log"

start() {
	"$@" surreal start --allow-all -u root -p root --log trace >"$LOG" 2>&1 &
	local pid=$!
	for _ in $(seq "$TIMEOUT"); do
		if curl -sf "$ENDPOINT/health" >/dev/null; then
			echo "surrealdb is up (pid $pid)"
			return 0
		fi
		if ! kill -0 "$pid" 2>/dev/null; then
			cat "$LOG"
			return 1
		fi
		sleep 1
	done
	kill "$pid" 2>/dev/null || true
	cat "$LOG"
	return 1
}

if start env SURREAL_CAPS_ALLOW_EXPERIMENTAL=files; then
	exit 0
fi

echo "Starting again without the files experimental capability"
if start env; then
	exit 0
fi

echo "::error::surrealdb did not answer on $ENDPOINT/health within ${TIMEOUT}s"
exit 1
