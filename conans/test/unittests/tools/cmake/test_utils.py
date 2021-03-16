from conan.tools.cmake.utils import get_generator
from conans.test.utils.mocks import ConanFileMock, MockSettings


class TestGetGenerator(object):

    def test_vs_generator(self):
        settings = MockSettings({"os": "Windows", "arch": "x86_64", "compiler": "Visual Studio"})
        conanfile = ConanFileMock()
        conanfile.settings = settings

        settings.values['compiler.version'] = '15'
        assert get_generator(conanfile) == 'Visual Studio 15 2017'

        settings.values['compiler.version'] = '15.9'
        assert get_generator(conanfile) == 'Visual Studio 15 2017'
