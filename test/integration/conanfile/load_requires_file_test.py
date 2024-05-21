from conan.test.utils.tools import TestClient


class TestLoadRequirementsTextFileTest:

    def test_load_reqs_from_text_file(self):
        client = TestClient()
        conanfile = """from conan import ConanFile
def reqs():
    try:
        content = open("reqs.txt", "r").read()
        lines = [line for line in content.splitlines() if line]
        return tuple(lines)
    except:
        return None

class Test(ConanFile):
    exports = "reqs.txt"
    requires = reqs()
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=hello0 --version=0.1 --user=user --channel=channel")

        for i in (0, 1, 2):
            reqs = "hello%s/0.1@user/channel" % i
            client.save({"conanfile.py": conanfile,
                         "reqs.txt": reqs})
            client.run("create . --name=hello%s --version=0.1 --user=user --channel=channel" % (i + 1))

        client.run("install --requires=hello3/0.1@user/channel")
        client.assert_listed_require({"hello0/0.1@user/channel": "Cache",
                                      "hello1/0.1@user/channel": "Cache",
                                      "hello2/0.1@user/channel": "Cache",
                                      "hello3/0.1@user/channel": "Cache"})
