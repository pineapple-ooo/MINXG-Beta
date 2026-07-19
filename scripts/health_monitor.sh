#!/bin/sh
# scripts/health_monitor.sh — MINXG health watchdog (docker cron)
#
# Runs every 60s (managed by docker compose health-monitor service).
# Pings gateway /health endpoint; if 3 consecutive failures,
# writes to /data/health_alert.log.  Non-zero exit triggers
# docker restart policy.
#
# Hermes-agent equivalent: cron scripts/watchdog.sh
# MINXG advantage: This is a 28-line sh script, not 180-line Python.

GATEWAY="http://minxg-gateway:8080"
ALERT_LOG="/data/health_alert.log"
MAX_FAILS=3
FAIL_FILE="/tmp/minxg_health_fails"
INTERVAL=60

check() {
    curl -sf --max-time 5 "${GATEWAY}/health" >/dev/null 2>&1
}

# Read current fail count
if [ -f "$FAIL_FILE" ]; then
    fails=$(cat "$FAIL_FILE")
else
    fails=0
fi

if check; then
    # Reset on success
    echo 0 > "$FAIL_FILE"
    exit 0
fi

fails=$((fails + 1))
echo "$fails" > "$FAIL_FILE"

if [ "$fails" -ge "$MAX_FAILS" ]; then
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$ts] GATEWAY UNREACHABLE after $fails consecutive failures" >> "$ALERT_LOG"
    exit 1  # docker restarts the service
fi

exit 0