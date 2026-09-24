import re


# Only read-only Kubernetes inspection commands are allowed.
# These commands are intentionally limited to the operations
# required by the dashboard terminal.
ALLOWED_PATTERNS = [
    r"^kubectl get (pods|services|endpoints|deployments|events|nodes)( -n [a-zA-Z0-9-]+)?$",
    r"^kubectl describe (pod|service|deployment|node) [a-zA-Z0-9-]+( -n [a-zA-Z0-9-]+)?$",
    r"^kubectl logs [a-zA-Z0-9-]+( --tail=[0-9]+)?( -n [a-zA-Z0-9-]+)?$",
    r"^kubectl cluster-info$",
    r"^kubectl version --short$",
]


# Shell operators and characters that must never be accepted.
FORBIDDEN_CHARS = [
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$",
    ">",
    "<",
    "\n",
    "\r",
    "\\",
]


def is_command_allowed(command: str) -> tuple[bool, str]:
    """
    Validate a terminal command against the server-side allowlist.

    Returns:
        tuple[bool, str]:
            Whether the command is allowed and an explanatory message.
    """
    if not isinstance(command, str):
        return False, "Command must be a string."

    command_text = command.strip()

    if not command_text:
        return False, "Empty command provided."

    if len(command_text) > 200:
        return False, "Command is too long."

    for forbidden_character in FORBIDDEN_CHARS:
        if forbidden_character in command_text:
            return (
                False,
                (
                    "Security violation: forbidden shell operator "
                    f"'{forbidden_character}' detected."
                ),
            )

    for pattern in ALLOWED_PATTERNS:
        if re.fullmatch(pattern, command_text):
            return True, "Command authorized."

    return (
        False,
        (
            "Security violation: command is not included "
            "in the Zero-Trust allowlist."
        ),
    )