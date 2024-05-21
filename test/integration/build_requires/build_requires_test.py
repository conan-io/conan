import json
import os
import platform
import re
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conan.test.utils.tools import TestClient, GenConanfile


@pytest.fixture()
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "build_type"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYOPENSSL={}!!".format(self.settings.build_type)
                    save(self, "bin/myopenssl.bat", echo)
                    save(self, "bin/myopenssl.sh", echo)
                    os.chmod("bin/myopenssl.sh", 0o777)
            """)

    cmake = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            type = "application"
            settings = "build_type"
            def requirements(self):
                self.requires("openssl/1.0", run=True)
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYCMAKE={}!!".format(self.settings.build_type)
                    save(self, "mycmake.bat", echo + "\ncall myopenssl.bat")
                    save(self, "mycmake.sh", echo + "\n myopenssl.sh")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                # Custom buildenv not defined by cpp_info
                self.buildenv_info.prepend_path("PATH", self.package_folder)
                self.buildenv_info.define("MYCMAKEVAR", "MYCMAKEVALUE!!")
            """)

    gtest = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "build_type"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYGTEST={}!!".format(self.settings.build_type)
                    save(self, "bin/mygtest.bat", echo)
                    save(self, "bin/mygtest.sh", echo)
                    os.chmod("bin/mygtest.sh", 0o777)

            def package_info(self):
                self.runenv_info.define("MYGTESTVAR",
                                        "MyGTestValue{}".format(self.settings.build_type))
            """)
    client = TestClient()
    client.save({"cmake/conanfile.py": cmake,
                 "gtest/conanfile.py": gtest,
                 "openssl/conanfile.py": openssl})

    client.run("create openssl --name=openssl --version=1.0")
    client.run("create cmake --name=mycmake --version=1.0")
    client.run("create gtest --name=mygtest --version=1.0")

    myrunner_bat = "@echo off\necho MYGTESTVAR=%MYGTESTVAR%!!\n"
    myrunner_sh = "echo MYGTESTVAR=$MYGTESTVAR!!\n"
    client.save({"myrunner.bat": myrunner_bat,
                 "myrunner.sh": myrunner_sh}, clean_first=True)
    os.chmod(os.path.join(client.current_folder, "myrunner.sh"), 0o777)
    return client


def test_conanfile_txt(client):
    # conanfile.txt -(br)-> cmake
    client.save({"conanfile.txt": "[tool_requires]\nmycmake/1.0"}, clean_first=True)
    client.run("install . -s:h build_type=Debug")

    assert "mycmake/1.0" in client.out
    assert "openssl/1.0" in client.out
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command("conanbuild", client.current_folder, "mycmake.{}".format(ext))
    client.run_command(cmd)

    assert "MYCMAKE=Release!!" in client.out
    assert "MYOPENSSL=Release!!" in client.out


def test_complete(client):
    app = textwrap.dedent("""
        import platform
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            build_requires = "mycmake/1.0"
            settings = "os"

            def build_requirements(self):
                self.test_requires("mygtest/1.0", run=True)

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)
                mytest_cmd = "mygtest.bat" if platform.system() == "Windows" else "mygtest.sh"
                self.run(mytest_cmd, env="conanrun")
       """)

    client.save({"conanfile.py": app})
    client.run("install . -s build_type=Debug --build=missing")
    # Run the BUILD environment
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command("conanbuild", client.current_folder,
                                   cmd="mycmake.{}".format(ext))
    client.run_command(cmd)
    assert "MYCMAKE=Release!!" in client.out
    assert "MYOPENSSL=Release!!" in client.out

    # Run the RUN environment
    cmd = environment_wrap_command("conanrun", client.current_folder,
                                   cmd="mygtest.{ext} && .{sep}myrunner.{ext}".format(ext=ext,
                                                                                      sep=os.sep))
    client.run_command(cmd)
    assert "MYGTEST=Debug!!" in client.out
    assert "MYGTESTVAR=MyGTestValueDebug!!" in client.out

    client.run("build . -s:h build_type=Debug")
    assert "MYCMAKE=Release!!" in client.out
    assert "MYOPENSSL=Release!!" in client.out
    assert "MYGTEST=Debug!!" in client.out


def test_dependents_new_buildenv():
    client = TestClient()
    boost = textwrap.dedent("""
        from conan import ConanFile
        class Boost(ConanFile):
            def package_info(self):
                self.buildenv_info.define_path("PATH", "myboostpath")
        """)
    other = textwrap.dedent("""
        from conan import ConanFile
        class Other(ConanFile):
            def requirements(self):
                self.requires("boost/1.0")

            def package_info(self):
                self.buildenv_info.append_path("PATH", "myotherpath")
                self.buildenv_info.prepend_path("PATH", "myotherprepend")
        """)
    consumer = textwrap.dedent("""
       from conan import ConanFile
       from conan.tools.env import VirtualBuildEnv
       import os
       class Lib(ConanFile):
           requires = {}
           def generate(self):
               build_env = VirtualBuildEnv(self).vars()
               with build_env.apply():
                   self.output.info("LIB PATH %s" % os.getenv("PATH"))
       """)
    client.save({"boost/conanfile.py": boost,
                 "other/conanfile.py": other,
                 "consumer/conanfile.py": consumer.format('"boost/1.0", "other/1.0"'),
                 "profile_define": "[buildenv]\nPATH=(path)profilepath",
                 "profile_append": "[buildenv]\nPATH+=(path)profilepath",
                 "profile_prepend": "[buildenv]\nPATH=+(path)profilepath"})
    client.run("create boost --name=boost --version=1.0")
    client.run("create other --name=other --version=1.0")
    client.run("install consumer")
    result = os.pathsep.join(["myotherprepend", "myboostpath", "myotherpath"])
    assert "LIB PATH {}".format(result) in client.out

    # Now test if we declare in different order, still topological order should be respected
    client.save({"consumer/conanfile.py": consumer.format('"other/1.0", "boost/1.0"')})
    client.run("install consumer")
    assert "LIB PATH {}".format(result) in client.out

    client.run("install consumer -pr=profile_define")
    assert "LIB PATH profilepath" in client.out
    client.run("install consumer -pr=profile_append")
    result = os.pathsep.join(["myotherprepend", "myboostpath", "myotherpath", "profilepath"])
    assert "LIB PATH {}".format(result) in client.out
    client.run("install consumer -pr=profile_prepend")
    result = os.pathsep.join(["profilepath", "myotherprepend", "myboostpath", "myotherpath"])
    assert "LIB PATH {}".format(result) in client.out


def test_tool_requires_conanfile_txt():
    client = TestClient(light=True)
    client.save({"conanfile.py": GenConanfile()})

    build_req = textwrap.dedent("""
        from conan import ConanFile
        class BuildReqConan(ConanFile):
            pass
        """)

    client.save({"conanfile.py": build_req})
    client.run("export . --name=build_req --version=1.0 --user=test --channel=test")

    consumer = textwrap.dedent("""
                [tool_requires]
                build_req/1.0@test/test
            """)
    client.save({"conanfile.txt": consumer}, clean_first=True)
    client.run("install . --build=missing")
    assert "build_req/1.0@test/test: Created package" in client.out


def test_profile_override_conflict():
    client = TestClient(light=True)

    test = textwrap.dedent("""
        from conan import ConanFile
        class Lib(ConanFile):

            def requirements(self):
                self.tool_requires(self.tested_reference_str)

            def test(self):
                pass
        """)
    client.save({"conanfile.py": GenConanfile("protoc"),
                 "test_package/conanfile.py": test,
                 "profile": "[tool_requires]\nprotoc/0.1"})
    client.run("create . --version 0.1 -pr=profile")
    client.run("create . --version 0.2 -pr=profile")
    assert "protoc/0.1: Already installed!" in client.out
    assert "protoc/0.2 (test package)" in client.out
    assert "WARN: The package created was 'protoc/0.1' but the reference being tested " \
           "is 'protoc/0.2'" in client.out


def test_both_context_options_error():
    # https://github.com/conan-io/conan/issues/11385
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "arch"
            options = {"neon": [True, "check", False]}
            default_options = {"neon": True}

            def config_options(self):
                if "arm" not in self.settings.arch:
                    del self.options.neon
            """)
    c.save({"pkg/conanfile.py": pkg,
            "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                   .with_build_requires("pkg/0.1")})
    c.run("export pkg")
    c.run("install consumer -s:b arch=x86_64 -s:h arch=armv8 --build=missing")
    # This failed in Conan 1.X, but now it works
    c.assert_listed_binary({"pkg/0.1": ("a0a41a189feabff576a535d071858191b90beceb", "Build")})
    c.assert_listed_binary({"pkg/0.1": ("62e589af96a19807968167026d906e63ed4de1f5", "Build")},
                           build=True)
    assert "Finalizing install" in c.out


def test_conditional_require_context():
    """ test that we can condition on the context to define a dependency
    """
    c = TestClient(light=True)
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
           name = "pkg"
           version = "0.1"
           def requirements(self):
               if self.context == "host":
                   self.requires("dep/1.0")
           """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "consumer/conanfile.py": pkg})
    c.run("create dep")
    c.run("create consumer")
    c.assert_listed_require({"dep/1.0": "Cache"})
    c.run("create consumer --build-require")
    assert "dep/1.0" not in c.out


class TestBuildTrackHost:

    def test_overriden_host_but_not_build(self):
        """
        Making the ``tool_requires(..., visible=True)`` works, and allows overriding, but
        propagates the build-requirement to protobuf/protoc down the graph, and VirtualBuildEnv
        will put ``protoc`` from it in the PATH. Not a problem in majority of cases, but not the
        cleanest
        """
        c = TestClient(light=True)
        pkg = textwrap.dedent("""
            from conan import ConanFile
            class ProtoBuf(ConanFile):
                name = "pkg"
                version = "0.1"
                def requirements(self):
                    self.requires("protobuf/1.0")
                def build_requirements(self):
                    self.tool_requires("protobuf/1.0", visible=True)
            """)
        c.save({"protobuf/conanfile.py": GenConanfile("protobuf"),
                "pkg/conanfile.py": pkg,
                "app/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                  .with_requirement("protobuf/1.1", override=True)
                                                  .with_build_requirement("protobuf/1.1",
                                                                          override=True)})
        c.run("create protobuf --version=1.0")
        c.run("create protobuf --version=1.1")
        c.run("create pkg")
        c.run("install app")
        c.assert_listed_require({"protobuf/1.1": "Cache"})
        c.assert_listed_require({"protobuf/1.1": "Cache"}, build=True)

    def test_overriden_host_version(self):
        """
        Make the tool_requires follow the regular require with the expression "<host_version>"
        """
        c = TestClient(light=True)
        pkg = textwrap.dedent("""
            from conan import ConanFile
            class ProtoBuf(ConanFile):
                name = "pkg"
                version = "0.1"
                def requirements(self):
                    self.requires("protobuf/1.0")
                def build_requirements(self):
                    self.tool_requires("protobuf/<host_version>")
            """)
        c.save({"protobuf/conanfile.py": GenConanfile("protobuf"),
                "pkg/conanfile.py": pkg,
                "app/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                  .with_requirement("protobuf/1.1", override=True)})
        c.run("create protobuf --version=1.0")
        c.run("create protobuf --version=1.1")
        c.run("create pkg")
        c.run("install pkg")  # make sure it doesn't crash
        c.run("install app")
        c.assert_listed_require({"protobuf/1.1": "Cache"})
        c.assert_listed_require({"protobuf/1.1": "Cache"}, build=True)
        # verify locks work
        c.run("lock create app")
        lock = json.loads(c.load("app/conan.lock"))
        build_requires = lock["build_requires"]
        assert len(build_requires) == 1
        assert "protobuf/1.1" in build_requires[0]
        # lock can be used
        c.run("install app --lockfile=app/conan.lock")
        c.assert_listed_require({"protobuf/1.1": "Cache"}, build=True)

    def test_overriden_host_version_version_range(self):
        """
        same as above, but using version ranges instead of overrides
        """
        c = TestClient(light=True)
        pkg = textwrap.dedent("""
            from conan import ConanFile
            class ProtoBuf(ConanFile):
                name = "pkg"
                version = "0.1"
                def requirements(self):
                    self.requires("protobuf/[*]")
                def build_requirements(self):
                    self.tool_requires("protobuf/<host_version>")
            """)
        c.save({"protobuf/conanfile.py": GenConanfile("protobuf"),
                "pkg/conanfile.py": pkg,
                "app/conanfile.py": GenConanfile().with_requires("pkg/0.1")})
        c.run("create protobuf --version=1.0")
        c.run("create pkg")
        c.run("install pkg")  # make sure it doesn't crash
        c.run("install app")
        c.assert_listed_require({"protobuf/1.0": "Cache"})
        c.assert_listed_require({"protobuf/1.0": "Cache"}, build=True)

        c.run("create protobuf --version=1.1")
        c.run("install pkg")  # make sure it doesn't crash
        c.run("install app")
        c.assert_listed_require({"protobuf/1.1": "Cache"})
        c.assert_listed_require({"protobuf/1.1": "Cache"}, build=True)
        # verify locks work
        c.run("lock create app")
        lock = json.loads(c.load("app/conan.lock"))
        build_requires = lock["build_requires"]
        assert len(build_requires) == 1
        assert "protobuf/1.1" in build_requires[0]
        # lock can be used
        c.run("install app --lockfile=app/conan.lock")
        c.assert_listed_require({"protobuf/1.1": "Cache"}, build=True)

    def test_track_host_error_nothost(self):
        """
        if no host requirement is defined, it will be an error
        """
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_build_requirement("protobuf/<host_version>")})
        c.run("install .", assert_error=True)
        assert "ERROR:  require 'protobuf/<host_version>': " \
               "didn't find a matching host dependency" in c.out

    def test_track_host_errors_trait(self):
        """
        It is not possible to make host_version visible too
        """
        c = TestClient(light=True)
        pkg = textwrap.dedent("""
            from conan import ConanFile
            class ProtoBuf(ConanFile):
                name = "protobuf"
                def requirements(self):
                   self.tool_requires("other/<host_version>", visible=True)
            """)
        c.save({"pkg/conanfile.py": pkg})
        c.run("install pkg", assert_error=True)
        assert "ERROR: protobuf/None require 'other/<host_version>': 'host_version' " \
               "can only be used for non-visible tool_requires" in c.out

    def test_track_host_error_wrong_context(self):
        """
        it can only be used by tool_requires, not regular requires
        """
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg").with_requirement("protobuf/<host_version>")})
        c.run(f"install .", assert_error=True)
        assert " 'host_version' can only be used for non-visible tool_requires" in c.out

    def test_host_version_test_package(self):
        """
        https://github.com/conan-io/conan/issues/14704
        """
        c = TestClient(light=True)
        pkg = textwrap.dedent("""
                from conan import ConanFile
                class ProtoBuf(ConanFile):
                    name = "pkg"
                    version = "0.1"
                    def requirements(self):
                        self.requires("protobuf/[>=1.0]")
                    def build_requirements(self):
                        self.tool_requires("protobuf/<host_version>")
                """)
        # regular requires test_package
        c.save({"protobuf/conanfile.py": GenConanfile("protobuf"),
                "pkg/conanfile.py": pkg,
                "pkg/test_package/conanfile.py": GenConanfile().with_test("pass")})
        c.run("create protobuf --version=1.0")
        c.run(f"create pkg")
        # works without problem

        test = textwrap.dedent("""
                from conan import ConanFile
                class Test(ConanFile):
                    test_type = "explicit"

                    def build_requirements(self):
                        self.tool_requires(self.tested_reference_str)
                    def test(self):
                        pass
                """)
        c.save({"pkg/test_package/conanfile.py": test})
        c.run("create protobuf --version=1.0")
        # This used to fail
        c.run(f"create pkg")
        c.assert_listed_binary({"protobuf/1.0": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Cache")})
        c.assert_listed_binary({"protobuf/1.0": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Cache")}, build=True)

    def test_overriden_host_version_transitive_deps(self):
        """
        Make the tool_requires follow the regular require with the expression "<host_version>"
        for a transitive_deps
        """
        c = TestClient(light=True)
        c.save({"protobuf/conanfile.py": GenConanfile("protobuf"),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requirement("protobuf/[>=1.0]"),
                "app/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                  .with_tool_requirement("protobuf/<host_version>")})
        c.run("create protobuf --version=1.0")
        c.run("create protobuf --version=1.1")
        c.run("create pkg")
        c.run("install pkg")  # make sure it doesn't crash
        c.run("install app")
        c.assert_listed_require({"protobuf/1.1": "Cache"})
        c.assert_listed_require({"protobuf/1.1": "Cache"}, build=True)
        # verify locks work
        c.run("lock create app")
        lock = json.loads(c.load("app/conan.lock"))
        build_requires = lock["build_requires"]
        assert len(build_requires) == 1
        assert "protobuf/1.1" in build_requires[0]
        # lock can be used
        c.run("install app --lockfile=app/conan.lock")
        c.assert_listed_require({"protobuf/1.1": "Cache"}, build=True)

    @pytest.mark.parametrize("host_version, assert_error, assert_msg", [
        ("libgettext>", False, "gettext/0.2#d9f9eaeac9b6e403b271f04e04149df2"),
        # Error cases, just checking that we fail gracefully - no tracebacks
        ("libgettext", True, "Package 'gettext/<host_version:libgettext' not resolved"),
        (":>", True, "app/1.0 require ':/<host_version::>': didn't find a matching host dependency"),
        (">", True, "app/1.0 require '/<host_version:>': didn't find a matching host dependency"),
        (":", True, " Package 'gettext/<host_version::' not resolved"),
        ("", True, "Package 'gettext/<host_version:' not resolved: No remote defined")
    ])
    def test_host_version_different_ref(self, host_version, assert_error, assert_msg):
        tc = TestClient(light=True)
        tc.save({"gettext/conanfile.py": GenConanfile("gettext"),
                 "libgettext/conanfile.py": GenConanfile("libgettext"),
                 "app/conanfile.py": GenConanfile("app", "1.0").with_requires("libgettext/[>0.1]")
                                                   .with_tool_requirement(f"gettext/<host_version:{host_version}")})
        tc.run("create libgettext --version=0.2")
        tc.run("create gettext --version=0.1 --build-require")
        tc.run("create gettext --version=0.2 --build-require")

        tc.run("create app", assert_error=assert_error)
        assert assert_msg in tc.out

    @pytest.mark.parametrize("requires_tag,tool_requires_tag,fails", [
        ("user/channel", "user/channel", False),
        ("", "user/channel", True),
        ("auser/achannel", "anotheruser/anotherchannel", True),
    ])
    def test_overriden_host_version_user_channel(self, requires_tag, tool_requires_tag, fails):
        """
        Make the tool_requires follow the regular require with the expression "<host_version>"
        """
        c = TestClient(light=True)
        pkg = textwrap.dedent(f"""
            from conan import ConanFile
            class ProtoBuf(ConanFile):
                name = "pkg"
                version = "0.1"
                def requirements(self):
                    self.requires("protobuf/1.0@{requires_tag}")
                def build_requirements(self):
                    self.tool_requires("protobuf/<host_version>@{tool_requires_tag}")
            """)
        c.save({"protobuf/conanfile.py": GenConanfile("protobuf"),
                "pkg/conanfile.py": pkg})
        if "/" in requires_tag:
            user, channel = requires_tag.split("/", 1)
            user_channel = f"--user={user} --channel={channel}"
        else:
            user_channel = ""
        c.run(f"create protobuf --version=1.0 {user_channel}")

        c.run("create pkg", assert_error=fails)
        if fails:
            assert f"pkg/0.1 require 'protobuf/<host_version>@{tool_requires_tag}': didn't find a " \
                   "matching host dependency" in c.out
        else:
            assert "pkg/0.1: Package '39f6a091994d2d080081ea888d75ef65c1d04c8d' created" in c.out


def test_build_missing_build_requires():
    c = TestClient(light=True)
    c.save({"tooldep/conanfile.py": GenConanfile("tooldep", "0.1"),
            "tool/conanfile.py": GenConanfile("tool", "0.1").with_tool_requires("tooldep/0.1"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_tool_requires("tool/0.1"),
            "app/conanfile.py": GenConanfile().with_requires("pkg/0.1")})
    c.run("create tooldep")
    c.run("create tool")
    c.run("create pkg")
    c.run("remove tool*:* -c")
    c.run("install app")
    assert "- Build" not in c.out
    assert re.search(r"Skipped binaries(\s*)tool/0.1, tooldep/0.1", c.out)
    c.run("install app --build=missing")
    assert "- Build" not in c.out
    assert re.search(r"Skipped binaries(\s*)tool/0.1, tooldep/0.1", c.out)


def test_requirement_in_wrong_method():
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def configure(self):
                self.requires("foo/1.0")
        """)})
    tc.run('create . -cc="core:warnings_as_errors=[\'*\']"', assert_error=True)
    assert "ERROR: deprecated: Requirements should only be added in the requirements()/build_requirements() methods, not configure()/config_options(), which might raise errors in the future." in tc.out
