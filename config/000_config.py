import os
from pathlib import Path

FINISHED_EDITING_CONFIG_FILE = True
settings.base.template = os.environ["EDEN_TEMPLATE"]
settings.base.public_url = os.environ["EDEN_PUBLIC_URL"]
settings.database.db_type = "sqlite"
settings.base.migrate = True
settings.auth.hmac_key = Path("/data/hmac.key").read_text().strip()
settings.import_template()
VERSION = 1
