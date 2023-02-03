from conans.errors import ConanException
from conans.util.config_parser import ConfigParser


class ConanFileTextLoader(object):
    """Parse a conanfile.txt file"""

    def __init__(self, input_text):
        # Prefer composition over inheritance, the __getattr__ was breaking things
        self._config_parser = ConfigParser(input_text,  ["requires", "generators", "options",
                                                         "imports", "tool_requires", "test_requires",
                                                         "layout"],
                                           strip_comments=True)

    @property
    def layout(self):
        """returns the declared layout"""
        tmp = [r.strip() for r in self._config_parser.layout.splitlines()]
        if len(tmp) > 1:
            raise ConanException("Only one layout can be declared in the [layout] section of "
                                 "the conanfile.txt")
        return tmp[0] if tmp else None

    @property
    def requirements(self):
        """returns a list of requires
        EX:  "OpenCV/2.4.10@phil/stable"
        """
        return [r.strip() for r in self._config_parser.requires.splitlines()]

    @property
    def tool_requirements(self):
        """returns a list of tool_requires
        EX:  "OpenCV/2.4.10@phil/stable"
        """

        return [r.strip() for r in self._config_parser.tool_requires.splitlines()]

    @property
    def test_requirements(self):
        """returns a list of test_requires
        EX:  "gtest/2.4.10@phil/stable"
        """

        return [r.strip() for r in self._config_parser.test_requires.splitlines()]

    @property
    def options(self):
        return self._config_parser.options

    @property
    def generators(self):
        return self._config_parser.generators.splitlines()
