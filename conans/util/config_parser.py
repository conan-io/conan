import re

from conans.errors import ConanException


def get_bool_from_text_value(value):
    """ to be deprecated
    It has issues, as accepting into the registry whatever=value, as False, without
    complaining
    """
    return (value == "1" or value.lower() == "yes" or value.lower() == "y" or
            value.lower() == "true") if value else True


def get_bool_from_text(value):
    value = value.lower()
    if value in ["1", "yes", "y", "true"]:
        return True
    if value in ["0", "no", "n", "false"]:
        return False
    raise ConanException("Unrecognized boolean value '%s'" % value)


class ConfigParser(object):
    """ util class to load a file with sections as [section1]
    checking the values of those sections, and returns each section
    as parser.section
    Currently used in ConanInfo and ConanFileTextLoader
    """
    def __init__(self, text, allowed_fields=None, strip_comments=False):
        self._sections = {}
        self._allowed_fields = allowed_fields or []
        pattern = re.compile(r"^\[([a-z_]{2,50})]")
        current_lines = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] == '#':
                continue
            if line[0] == '[':
                m = pattern.match(line)
                if not m:
                    raise ConanException("ConfigParser: Bad syntax '%s'" % line)
                field = m.group(1)
                if self._allowed_fields and field not in self._allowed_fields:
                    raise ConanException("ConfigParser: Unrecognized field '%s'" % field)
                current_lines = []
                self._sections[field] = current_lines
            else:
                if current_lines is None:
                    raise ConanException("ConfigParser: Unexpected line '%s'" % line)
                if strip_comments:
                    line = line.split(' #', 1)[0]
                    line = line.split('    #', 1)[0]
                    line = line.strip()
                current_lines.append(line)

    def line_items(self):
        # Used atm by load_binary_info()
        return self._sections.items()

    def __getattr__(self, name):
        if name in self._sections:
            return "\n".join(self._sections[name])
        else:
            if self._allowed_fields and name not in self._allowed_fields:
                raise ConanException("ConfigParser: Unrecognized field '%s'" % name)
            return ""
