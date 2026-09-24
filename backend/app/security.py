import re

# Strict Regex Allowlist for Terminal Command Execution
ALLOWED_PATTERNS = [
    r"^kubectl get (pods|services|endpoints|deployments|events|nodes)( -n [a-zA-Z0-9-]+)?$",
    r"^kubectl describe (pod|service|deployment|node) [a-zA-Z0-9-]+( -n [a-zA-Z0-9-]+)?$",
    r"^kubectl logs [a-zA-Z0-9-]+( --tail=[0-9]+)?( -n [a-zA-Z0-9-]+)?$",
    r"^kubectl cluster-info$",
    r"^kubectl version --short$"
]

# Characters strictly forbidden to prevent Command Injection
FORBIDDEN_CHARS = [";", "&&", "||", "|", "`", "$", ">", "<", "\n", "\\"]


def is_command_allowed(command: str) -> tuple[bool, str]:
    """
    Validates user input command against security constraints.
    Returns (is_valid, reason).
    """
    cmd_str = command.strip()

    if not cmd_str:
        return False, "Empty command provided."

    # Check for forbidden execution operators
    for char in FORBIDDEN_CHARS:
        if char in cmd_str:
            return False, f"Security Violation: Operator '{char}' is forbidden."

    # Validate against pattern allowlist
    for pattern in ALLOWED_PATTERNS:
        if re.match(pattern, cmd_str):
            return True, "Command authorized."

    return False, "Security Violation: Command not found in Zero Trust Allowlist."