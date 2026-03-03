from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings

whisparr_logger = get_logger("whisparr")


def is_configured():
    """Check if Whisparr API credentials are configured"""
    try:
        instances = load_settings("whisparr").get("instances", [])
        return any(inst.get("enabled", True) and inst.get("api_url") and inst.get("api_key") for inst in instances)
    except Exception as e:
        whisparr_logger.error(f"Error checking if Whisparr is configured: {str(e)}")
        return False


def get_configured_instances():
    """Get all configured and enabled Whisparr instances"""
    try:
        instances = load_settings("whisparr").get("instances", [])

        enabled_instances = []
        for instance in instances:
            if not instance.get("enabled", True):
                continue

            api_url = instance.get("api_url")
            api_key = instance.get("api_key")

            if not api_url or not api_key:
                continue

            enabled_instances.append(
                {
                    "api_url": api_url,
                    "api_key": api_key,
                    "instance_name": instance.get("name", "Default"),
                    "api_timeout": instance.get("api_timeout", 90),
                }
            )

        return enabled_instances
    except Exception as e:
        whisparr_logger.error(f"Error getting configured Whisparr instances: {str(e)}")
        return []
