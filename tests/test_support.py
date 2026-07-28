import atexit
import os
import shutil
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="neutarr-tests-"))
atexit.register(lambda: shutil.rmtree(_TEST_ROOT, ignore_errors=True))


def configure_test_environment():
    config_dir = Path(os.environ.setdefault("NEUTARR_CONFIG_DIR", str(_TEST_ROOT / "config")))
    stateful_dir = Path(os.environ.setdefault("STATEFUL_DIR", str(config_dir / "stateful")))

    os.environ.setdefault("NEUTARR_INSTANCE_ID", "test")
    os.environ.setdefault("NEUTARR_SETUP_TOKEN", "test-first-run-token")
    os.environ.setdefault("PORT", "9705")

    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "logs").mkdir(parents=True, exist_ok=True)
    stateful_dir.mkdir(parents=True, exist_ok=True)

    for app_type in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        (stateful_dir / app_type).mkdir(parents=True, exist_ok=True)

    return config_dir
