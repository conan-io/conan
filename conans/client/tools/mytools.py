import sys
import types

from conans.util.files import save, load


def create_my_tools(output, requester, config):
    mytools = types.ModuleType('MyTools', 'Some Conan Tools')
    files = types.ModuleType('MyFileTools', "Conan file related tools")
    files.save = save
    files.load = load
    mytools.files = files
    sys.modules["conans"].mytools = mytools
