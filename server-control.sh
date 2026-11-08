#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
[[ -f .psa-forge-candidate.json && -f .psa-owned-smoke-test ]] || { echo 'Not an owned PSA candidate profile' >&2; exit 1; }
SOCKET="psa-forge-$(printf '%s' "$ROOT" | sha256sum | cut -c1-16)"
TMUX=(tmux -L "$SOCKET" -f /dev/null)
# Never let the persistent tmux server or Java inherit the start lock.
tmux_cmd() { "${TMUX[@]}" "$@" 9>&-; }
running() { tmux_cmd has-session -t server 2>/dev/null; }
owned_session() {
  [[ "$(tmux_cmd show-options -qv -t server @psa-root)" == "$ROOT" ]] || { echo 'Refusing to control an unrecognized tmux session' >&2; exit 1; }
}
case "${1:-status}" in
  start)
    exec 9>.psa-control.lock
    flock -n 9 || { echo 'Another start operation is in progress' >&2; exit 1; }
    if running; then owned_session; echo 'Already running'; exit 0; fi
    if [[ "${2:-}" == --accept-eula ]]; then printf 'eula=true\n' > eula.txt; fi
    grep -qx 'eula=true' eula.txt || { echo 'Read the Minecraft EULA, then start --accept-eula' >&2; exit 1; }
    [[ -x runtime/java/bin/java && -f libraries/net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt ]] || { echo 'Install the pinned runtime first' >&2; exit 1; }
    sha256sum --check --status .psa-mods.sha256 || { echo 'Mod hash mismatch' >&2; exit 1; }
    [[ "$(find mods -maxdepth 1 -type f -name '*.jar' | wc -l)" -eq 313 ]] || { echo 'Unexpected mod inventory' >&2; exit 1; }
    grep -qx 'online-mode=true' server.properties || { echo 'Online authentication is required' >&2; exit 1; }
    mkdir -p logs
    if [[ -f console.log ]]; then mv console.log "$(mktemp logs/console-previous-XXXXXXXX)"; fi
    printf -v command 'exec %q @user_jvm_args.txt @libraries/net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt nogui >console.log 2>&1' "$ROOT/runtime/java/bin/java"
    tmux_cmd new-session -d -s server -c "$ROOT" "$command"
    tmux_cmd set-option -t server @psa-root "$ROOT"
    echo 'Started. Use status and console.log to confirm Done.'
    ;;
  stop)
    if ! running; then echo 'Stopped'; exit 0; fi
    owned_session
    tmux_cmd send-keys -t server -l stop
    tmux_cmd send-keys -t server Enter
    for ((n=0; n<120; n++)); do
      if ! running; then echo 'Stopped'; exit 0; fi
      sleep 1
    done
    echo 'Shutdown still pending; inspect console.log. No process was killed.' >&2
    exit 1
    ;;
  status)
    if running; then owned_session; echo 'Running'; else echo 'Stopped'; fi
    ;;
  command)
    running || { echo 'Stopped' >&2; exit 1; }
    owned_session
    [[ $# -eq 2 && "$2" != *$'\n'* && "$2" != *$'\r'* ]] || { echo 'One console command is required' >&2; exit 1; }
    tmux_cmd send-keys -t server -l "$2"
    tmux_cmd send-keys -t server Enter
    ;;
  *) echo 'Usage: server-control.sh start [--accept-eula] | stop | status | command "..."' >&2; exit 2 ;;
esac
