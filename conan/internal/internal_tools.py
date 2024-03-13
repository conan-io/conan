from conans.errors import ConanException

universal_arch_separator = '|'


def is_universal_arch(settings_value, valid_definitions):
    if settings_value is None or valid_definitions is None or universal_arch_separator not in settings_value:
        return False

    parts = settings_value.split(universal_arch_separator)

    if parts != sorted(parts):
        raise ConanException(f"Architectures must be in alphabetical order separated by "
                             f"{universal_arch_separator}")

    valid_macos_values = [val for val in valid_definitions if ("arm" in val or "x86" in val)]

    return all(part in valid_macos_values for part in parts)
