import sys
import types

from conans.util.files import save, load


class Tool(object):
    pass


class Net(object):
    def __init__(self, output, config, requester):
        self._output = output
        self._config = config
        self._requester = requester

    def download(self, url, file):
        self._output.info("URL: %s, FILE: %s" % (url, file))


class MyCMake(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def build(self):
        self._conanfile.output.info("SUCCESS MYCMAKE")
        self._output.info("OTHER_SUCCESS MYCMAKE")


def create_my_tools(output, config, requester):
    mytools = types.ModuleType('MyTools', 'Some Conan Tools')
    files = types.ModuleType('MyFileTools', "Conan file related tools")
    files.save = save
    files.load = load
    mytools.files = files

    build = types.ModuleType('MyBuildools', "Conan build related tools")
    build.MyCMake = MyCMake
    mytools.build = build

    mytools.net = Net(output, config, requester)
    sys.modules["conans"].mytools = mytools
