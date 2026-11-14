#!/usr/bin/env bash
set -euo pipefail
# Run from the uploaded support/ directory as root. Does not start any service.
if [[ $EUID -ne 0 ]]; then echo 'Run with sudo from support/.' >&2; exit 1; fi
if systemctl is-active --quiet psa-support; then
  echo 'Stop the support bot before replacing its installation.' >&2; exit 1
fi
if ! id psa-support >/dev/null 2>&1; then
  useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin psa-support
fi
install -d -m 0755 /opt/psa-support /opt/psa-support/bin
install -d -o psa-support -g psa-support -m 0700 /var/lib/psa-support/codex-auth
install -d -o psa-support -g psa-support -m 0700 /var/lib/psa-support
cp -R psa_support /opt/psa-support/
install -m 0644 pyproject.toml requirements.lock /opt/psa-support/
/usr/bin/python3 -m venv /opt/psa-support/.venv
/opt/psa-support/.venv/bin/python -m pip install --require-hashes -r /opt/psa-support/requirements.lock
/opt/psa-support/.venv/bin/python -m pip install --no-deps /opt/psa-support
chown -R root:root /opt/psa-support
chmod -R go-w /opt/psa-support
install -m 0644 deploy/psa-support.service /etc/systemd/system/psa-support.service
if [[ ! -x /opt/psa-support/bin/codex ]] || [[ $(/opt/psa-support/bin/codex --version) != 'codex-cli 0.164.0' ]]; then
  /usr/bin/python3 - <<'PYCODEX'
import hashlib, io, tarfile, urllib.request
from pathlib import Path
url='https://github.com/openai/codex/releases/download/rust-v0.164.0/codex-x86_64-unknown-linux-musl.tar.gz'
raw=urllib.request.urlopen(url,timeout=120).read()
if hashlib.sha256(raw).hexdigest()!='90dd0b03b28afcb7fa733a4f73b413db2916a47347efd43fb669cc1c774ee8e4':
    raise RuntimeError('Official Codex artifact checksum mismatch')
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
    data=archive.extractfile('codex-x86_64-unknown-linux-musl').read()
target=Path('/opt/psa-support/bin/codex')
target.write_bytes(data); target.chmod(0o755)
PYCODEX
fi
systemctl daemon-reload
printf '%s\n' 'Installed, not enabled or started. Configure channel, knowledge and credentials before activation.'
