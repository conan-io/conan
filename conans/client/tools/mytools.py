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
    _output = None

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def build(self):
        self._conanfile.output.info("SUCCESS MYCMAKE")
        self._output.info("OTHER_SUCCESS MYCMAKE")


def cmake_factory(output):
    my_cmake_class = MyCMake
    my_cmake_class._output = output
    return my_cmake_class


def create_my_tools(output, config, requester):
    mytools = types.ModuleType('MyTools', 'Some Conan Tools')
    files = types.ModuleType('MyFileTools', "Conan file related tools")
    files.save = save
    files.load = load
    mytools.files = files

    build = types.ModuleType('MyBuildools', "Conan build related tools")
    build.MyCMake = cmake_factory(output)
    mytools.build = build

    mytools.net = Net(output, config, requester)
    sys.modules["conans.mytools"] = mytools
    sys.modules["conans.mytools.build"] = build
