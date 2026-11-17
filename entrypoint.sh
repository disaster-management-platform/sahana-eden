#!/bin/sh
set -eu
for directory in databases sessions errors uploads cache; do
    mkdir -p "/data/$directory"
done
if [ ! -f /data/hmac.key ]; then
    python -c 'import secrets; from pathlib import Path; Path("/data/hmac.key").write_text(secrets.token_hex(32))'
    chmod 600 /data/hmac.key
fi
ln -sfn /opt/eden "applications/$EDEN_APPLICATION"
python web2py.py -S "$EDEN_APPLICATION" -M -R /opt/eden/static/scripts/tools/noop.py
exec python web2py.py --no_gui --no-banner -a '<disabled>' -i 0.0.0.0 -p 8000
