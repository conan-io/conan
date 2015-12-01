import re
from conans.errors import ConanException


class ConfigParser(object):
    """ util class to load a file with sections as [section1]
    checking the values of those sections, and returns each section
    as parser.section
    Currently used in ConanInfo and ConanFileTextLoader
    """
    def __init__(self, text, allowed_fields=None):
        self._sections = {}
        self._allowed_fields = allowed_fields or []
        pattern = re.compile("^\[([a-z_]{2,50})\]")
        current_lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] == '#':
                continue
            m = pattern.match(line)
            if m:
                group = m.group(1)
                if self._allowed_fields and group not in self._allowed_fields:
                    raise ConanException("ConfigParser: Unrecognized field '%s'" % group)
                current_lines = []
                self._sections[group] = current_lines
            else:
                current_lines.append(line)

    def __getattr__(self, name):
        if name in self._sections:
            return "\n".join(self._sections[name])
        else:
            if self._allowed_fields and name in self._allowed_fields:
                return ""
            else:
                raise ConanException("ConfigParser: Unrecognized field '%s'" % name)
