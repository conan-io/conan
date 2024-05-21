from conan.test.utils.tools import TestClient

base_conanfile = '''
from conan import ConanFile

class TestSystemReqs(ConanFile):
    name = "test"
    version = "0.1"

    def system_requirements(self):
        self.output.info("*+Running system requirements+*")
'''


class TestSystemReqs:

    def test_force_system_reqs_rerun(self):
        client = TestClient()
        client.save({'conanfile.py': base_conanfile})
        client.run("create . ")
        assert "*+Running system requirements+*" in client.out
        client.run("install --requires=test/0.1")
        assert "*+Running system requirements+*" in client.out

    def test_local_system_requirements(self):
        client = TestClient()
        client.save({'conanfile.py': base_conanfile})
        client.run("install .")
        assert "*+Running system requirements+*" in client.out
