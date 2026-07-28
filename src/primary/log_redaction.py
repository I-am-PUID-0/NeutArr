"""Central sensitive-data redaction for NeutArr log records and log responses."""

import logging
import re
import traceback

REDACTED = "[REDACTED]"

_SENSITIVE_KEY = (
    r"(?:"
    r"x-api-key|api[_-]?key|apikey|"
    r"(?:current[_-]?|new[_-]?|confirm[_-]?)?(?:password|passwd|passphrase)|"
    r"access[_-]?token|refresh[_-]?token|setup[_-]?token|"
    r"jwt[_-]?secret|client[_-]?secret|"
    r"authorization|proxy[_-]?authorization"
    r")"
)

_QUOTED_ASSIGNMENT_RE = re.compile(
    rf"""(?ix)
    (?P<prefix>
        (?P<key_quote>["'])
        (?:{_SENSITIVE_KEY}|token|cookie|set-cookie)
        (?P=key_quote)
        \s*:\s*
    )
    (?P<value_quote>["'])
    .*?
    (?P=value_quote)
    """
)
_PLAIN_ASSIGNMENT_RE = re.compile(
    rf"""(?ix)
    (?P<prefix>\b{_SENSITIVE_KEY}\b\s*[:=]\s*)
    (?:
        \[REDACTED\]
        |
        "(?:[^"\\]|\\.)*"
        |
        '(?:[^'\\]|\\.)*'
        |
        [^\s,;&}}\]]+
    )
    """
)
_COOKIE_HEADER_RE = re.compile(
    r"""(?imx)
    ^(?P<prefix>\s*(?:cookie|set-cookie)\s*:\s*)
    .+$
    """
)
_BEARER_RE = re.compile(
    r"""(?ix)
    (?P<prefix>\bauthorization\b\s*[:=]\s*)
    ["']?bearer\s+[A-Za-z0-9._~+/=-]+["']?
    """
)
_QUERY_SECRET_RE = re.compile(
    rf"""(?ix)
    (?P<prefix>[?&](?:{_SENSITIVE_KEY}|token)=)
    [^&#\s"']*
    """
)
_URL_USERINFO_RE = re.compile(
    r"""(?ix)
    (?P<prefix>https?://[^:/@\s]+:)
    [^/@\s]+
    (?P<suffix>@)
    """
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def redact_sensitive_data(value: object) -> str:
    """Return log text with common credential shapes replaced."""
    text = str(value)
    text = _BEARER_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", text)
    text = _JWT_RE.sub(REDACTED, text)
    text = _URL_USERINFO_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED}{match.group('suffix')}",
        text,
    )
    text = _QUERY_SECRET_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", text)
    text = _QUOTED_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('prefix')}{match.group('value_quote')}{REDACTED}{match.group('value_quote')}",
        text,
    )
    text = _COOKIE_HEADER_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", text)
    return _PLAIN_ASSIGNMENT_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", text)


class SensitiveDataFilter(logging.Filter):
    """Sanitize messages and exception text before a handler emits them."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)

        record.msg = redact_sensitive_data(message)
        record.args = ()

        if record.exc_info:
            exception_text = "".join(traceback.format_exception(*record.exc_info))
            record.exc_text = redact_sensitive_data(exception_text.rstrip())
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact_sensitive_data(record.exc_text)

        if record.stack_info:
            record.stack_info = redact_sensitive_data(record.stack_info)
        return True


def add_sensitive_data_filter(handler: logging.Handler) -> None:
    """Attach one redaction filter to a logging handler."""
    if not any(isinstance(existing, SensitiveDataFilter) for existing in handler.filters):
        handler.addFilter(SensitiveDataFilter())


def install_sensitive_data_filter() -> None:
    """Protect handlers that were configured before NeutArr's loggers loaded."""
    for handler in logging.getLogger().handlers:
        add_sensitive_data_filter(handler)
