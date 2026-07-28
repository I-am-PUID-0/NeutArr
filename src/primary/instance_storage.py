import hashlib


_READABLE_PREFIX_LENGTH = 80


def legacy_instance_storage_key(instance_name) -> str:
    """Return the filename key used by NeutArr before collision-resistant storage."""
    name = "Default" if instance_name is None else str(instance_name)
    return "".join(character if character.isalnum() else "_" for character in name)


def instance_storage_key(instance_name) -> str:
    """Return a readable, filesystem-safe, collision-resistant instance key."""
    name = "Default" if instance_name is None else str(instance_name)
    readable = "".join(character if character.isascii() and character.isalnum() else "_" for character in name)

    is_plain_ascii_name = all(character.isascii() and character.isalnum() for character in name)
    if is_plain_ascii_name and 0 < len(readable) <= _READABLE_PREFIX_LENGTH:
        return readable

    readable = readable.strip("_")[:_READABLE_PREFIX_LENGTH] or "instance"
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return f"{readable}--{digest}"
