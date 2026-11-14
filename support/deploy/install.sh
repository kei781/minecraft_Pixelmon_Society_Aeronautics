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
install -d -m 0755 /opt/psa-support
install -d -o psa-support -g psa-support -m 0700 /var/lib/psa-support
cp -R psa_support /opt/psa-support/
install -m 0644 pyproject.toml requirements.lock /opt/psa-support/
/usr/bin/python3 -m venv /opt/psa-support/.venv
/opt/psa-support/.venv/bin/python -m pip install --require-hashes -r /opt/psa-support/requirements.lock
/opt/psa-support/.venv/bin/python -m pip install --no-deps /opt/psa-support
chown -R root:root /opt/psa-support
chmod -R go-w /opt/psa-support
install -m 0644 deploy/psa-support.service /etc/systemd/system/psa-support.service
systemctl daemon-reload
printf '%s\n' 'Installed, not enabled or started. Configure channel, knowledge and credentials before activation.'
