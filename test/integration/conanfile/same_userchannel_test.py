import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestUserChannelTestPackage:

    def test(self):
        # https://github.com/conan-io/conan/issues/2501
        client = TestClient(light=True)
        conanfile = """from conan import ConanFile
class SayConan(ConanFile):
    pass
"""
        test = """from conan import ConanFile
class SayConan(ConanFile):
    def requirements(self):
        self.output.info("USER: %s!!" % self.user)
        self.output.info("CHANNEL: %s!!" % self.channel)
        self.requires(self.tested_reference_str)

    def test(self):
        pass
"""

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        client.run("create . --name=pkg --version=0.1 --user=conan --channel=testing")
        assert "pkg/0.1@conan/testing (test package): USER: conan!!" in client.out
        assert "pkg/0.1@conan/testing (test package): CHANNEL: testing!!" in client.out


class TestSameUserChannel:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient(light=True)
        conanfile = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    build_policy = "missing"

    def build(self):
        self.output.info("Building %s/%s")
"""
        for user, channel in ("lasote", "stable"), ("other", "testing"):
            self.client.save({"conanfile.py": conanfile % (user, channel)})
            self.client.run(f"export . --user={user} --channel={channel}")

        self.conanfile = """
from conan import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    build_policy = "missing"

    def requirements(self):
        user_channel = "{}/{}".format(self.user, self.channel) if self.user else ""
        self.requires("say/0.1@{}".format(user_channel))

    def build(self):
        self.output.info("Building %s/%s" % (self.user, self.channel) )
"""

        self.test_conanfile = str(GenConanfile().with_test("pass"))
        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile})

    def test_create(self):
        self.client.run("create . --user=lasote --channel=stable")
        assert "say/0.1@lasote/stable: Building lasote/stable" in self.client.out
        assert "hello/0.1@lasote/stable: Building lasote/stable" in self.client.out
        assert "other/testing" not in self.client.out

        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile.replace("lasote/stable",
                                                                           "other/testing")})
        self.client.run("create . --user=other --channel=testing")
        assert "say/0.1@other/testing: Building other/testing" in self.client.out
        assert "hello/0.1@other/testing: Building other/testing" in self.client.out
        assert "lasote/stable" not in self.client.out

    def test_local_commands(self):
        self.client.run("install .", assert_error=True)
        assert "ERROR: Package 'say/0.1' not resolved: No remote defined" in self.client.out

        self.client.run("install . --user=lasote --channel=stable")
        assert "say/0.1@lasote/stable: Building lasote/stable" in self.client.out
        assert "other/testing" not in self.client.out

        self.client.run("install . --user=other --channel=testing")
        assert "say/0.1@other/testing: Building other/testing" in self.client.out
        assert "lasote/stable" not in self.client.out

        # Now use the default_ methods to declare user and channel
        self.client = TestClient(light=True)
        conanfile = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    build_policy = "missing"
    user = "userfoo"

    def build(self):
        self.output.info("Building %s/%s" % (self.user, self.channel) )

    @property
    def channel(self):
        return "channelbar"
"""
        self.client.save({"conanfile.py": conanfile})
        self.client.run("install .")
        self.client.run("build .")
        assert "Building userfoo/channelbar" in self.client.out


class TestBuildRequireUserChannel:
    def test(self):
        # https://github.com/conan-io/conan/issues/2254
        client = TestClient(light=True)
        conanfile = """
from conan import ConanFile

class SayConan(ConanFile):
    def build_requirements(self):
        self.output.info("MYUSER: %s" % self.user)
        self.output.info("MYCHANNEL: %s" % self.channel)
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . --user=myuser --channel=mychannel")
        assert "MYUSER: myuser" in client.out
        assert "MYCHANNEL: mychannel" in client.out
