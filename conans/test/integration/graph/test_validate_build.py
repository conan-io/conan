import json
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_basic_validate_build_test():

    t = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conans.errors import ConanInvalidConfiguration

    class myConan(ConanFile):
        name = "foo"
        version = "1.0"
        settings = "os", "arch", "compiler"

        def validate_build(self):
            if self.settings.compiler == "gcc":
                raise ConanInvalidConfiguration("This doesn't build in GCC")

        def package_id(self):
            del self.info.settings.compiler
    """)

    settings_gcc = "-s compiler=gcc -s compiler.libcxx=libstdc++11 -s compiler.version=11"
    settings_clang = "-s compiler=clang -s compiler.libcxx=libc++ -s compiler.version=8"

    t.save({"conanfile.py": conanfile})
    t.run(f"create . {settings_gcc}", assert_error=True)

    assert "foo/1.0: Cannot build for this configuration: This doesn't build in GCC" in t.out

    t.run(f"create . {settings_clang}")

    # Now with GCC again, but now we have the binary, we don't need to build, so it doesn't fail
    t.run(f"create . {settings_gcc} --build missing")
    assert "foo/1.0: Already installed!" in t.out

    # But if I force the build... it will fail
    t.run(f"create . {settings_gcc} ", assert_error=True)
    assert "foo/1.0: Cannot build for this configuration: This doesn't build in GCC" in t.out

    # What happens with a conan info?
    t.run(f"info foo/1.0@ {settings_gcc} --json=myjson")
    myjson = json.loads(t.load("myjson"))
    assert myjson[0]["invalid_build"] is True
    assert myjson[0]["invalid_build_reason"] == "This doesn't build in GCC"

    t.run(f"info foo/1.0@ {settings_clang} --json=myjson")
    myjson = json.loads(t.load("myjson"))
    assert myjson[0]["invalid_build"] is False
    assert "invalid_build_reason" not in myjson[0]


def test_with_options_validate_build_test():
    t = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conans.errors import ConanInvalidConfiguration

    class myConan(ConanFile):
        name = "foo"
        version = "1.0"
        options = {"my_option": [True, False]}
        default_options = {"my_option": True}

        def validate_build(self):
            if not self.options.my_option:
                raise ConanInvalidConfiguration("This doesn't build with False option")

    """)
    t.save({"conanfile.py": conanfile})
    t.run("export .")
    consumer = GenConanfile().with_require("foo/1.0").with_name("consumer").with_version("1.0")
    t.save({"consumer.py": consumer})
    t.run("create consumer.py --build missing -o foo/*:my_option=False", assert_error=True)
    assert "foo/1.0: Cannot build for this configuration: This doesn't build " \
           "with False option" in t.out

    t.run("create consumer.py --build missing -o foo/*:my_option=True")
