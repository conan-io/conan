import os
import fnmatch


class ConanIgnoreMatcher:
    def __init__(self, conanignore_path):
        self.conanignore_path = os.path.abspath(conanignore_path)
        self._ignored_entries = {".conanignore"}
        self._parse_conanignore()

    def _parse_conanignore(self):
        with open(self.conanignore_path, 'r') as conanignore:
            for line in conanignore:
                line_content = line.strip()
                if line_content != "":
                    self._ignored_entries.add(line_content)

    def matches(self, path):
        for ignore_entry in self._ignored_entries:
            if fnmatch.fnmatch(path, ignore_entry):
                return True
        return False
