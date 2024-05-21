from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestConditionalReqsTest:

    def test_conditional_requirements(self):
        conanfile = GenConanfile("hello", "0.1").with_settings("os", "build_type", "product")

        test_conanfile = '''
from conan import ConanFile

class TestConanLib(ConanFile):
    settings = "os", "build_type", "product"
    def requirements(self):
        self.output.info("TestSettings: %s, %s, %s"
                         % (self.settings.os, self.settings.build_type, self.settings.product))
        self.requires(self.tested_reference_str)

    def test(self):
        pass
'''
        client = TestClient()
        save(client.cache.settings_path_user, "product: [onion, potato]")
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . -s os=Windows -s product=onion -s build_type=Release")
        assert"hello/0.1 (test package): TestSettings: Windows, Release, onion", client.out
