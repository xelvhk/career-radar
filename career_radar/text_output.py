"""Shared sanitization for untrusted human-readable output."""

MARKDOWN_METACHARACTERS = ("`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "!", "|", "<", ">")


def escape_markdown(value: str) -> str:
    """Remove control characters and escape Markdown metacharacters."""
    safe_value = "".join(
        character for character in value if ord(character) >= 32 and ord(character) != 127
    )
    escaped = safe_value.replace("\\", "\\\\")
    for character in MARKDOWN_METACHARACTERS:
        escaped = escaped.replace(character, f"\\{character}")
    return escaped
