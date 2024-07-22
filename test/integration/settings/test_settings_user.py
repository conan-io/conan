import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_settings_user():
    c = TestClient()
    settings_user = textwrap.dedent("""\
        os:
            Windows:
                subsystem: [new_sub]
            Linux:
                new_versions: ["a", "b", "c"]
            new_os:
        new_global: ["42", "21"]
        """)
    save(os.path.join(c.cache_folder, "settings_user.yml"), settings_user)
    c.save({"conanfile.py": GenConanfile().with_settings("os").with_settings("new_global")})
    # New settings are there
    c.run("install . -s os=Windows -s os.subsystem=new_sub -s new_global=42")
    assert "new_global=42" in c.out
    assert "os.subsystem=new_sub" in c.out
    # Existing values of subsystem are still there
    c.run("install . -s os=Windows -s os.subsystem=msys2 -s new_global=42")
    assert "new_global=42" in c.out
    assert "os.subsystem=msys2" in c.out
    # Completely new values, not appended, but new, are there
    c.run("install . -s os=Linux -s os.new_versions=a -s new_global=42")
    assert "new_global=42" in c.out
    assert "os.new_versions=a" in c.out
    # Existing values of OSs are also there
    c.run("install . -s os=Macos -s new_global=42")
    assert "os=Macos" in c.out
    assert "new_global=42" in c.out


def test_settings_user_subdict():
    c = TestClient()
    settings_user = textwrap.dedent("""\
        other_new:
            other1:
            other2:
                version: [1, 2, 3]
        """)
    save(os.path.join(c.cache_folder, "settings_user.yml"), settings_user)
    c.save({"conanfile.py": GenConanfile().with_settings("other_new")})
    c.run("install . -s other_new=other1")
    assert "other_new=other1" in c.out
    c.run("install . -s other_new=other2 -s other_new.version=2")
    assert "other_new=other2" in c.out
    assert "other_new.version=2" in c.out


def test_settings_user_convert_list_dict():
    c = TestClient()
    settings_user = textwrap.dedent("""\
        arch:
            x86:
                subarch32:
                    a:
                        version: ["a1", "a2"]
                    b:
                        variant: ["b1", "b2"]
            x86_64:
                subarch: [1, 2, 3]
          """)
    save(os.path.join(c.cache_folder, "settings_user.yml"), settings_user)
    c.save({"conanfile.py": GenConanfile().with_settings("arch")})
    # check others are maintained
    c.run("install . -s arch=armv8")
    assert "arch=armv8" in c.out

    c.run("install . -s arch=x86 -s arch.subarch32=a -s arch.subarch32.version=a1")
    assert "arch=x86" in c.out
    assert "arch.subarch32=a" in c.out
    assert "arch.subarch32.version=a1" in c.out

    c.run("install . -s arch=x86_64 -s arch.subarch=2 ")
    assert "arch=x86_64" in c.out
    assert "arch.subarch=2" in c.out


def test_settings_user_error():
    c = TestClient()
    settings_user = textwrap.dedent("""\
        os:
            Windows:
                libc: null
        """)
    save(os.path.join(c.cache_folder, "settings_user.yml"), settings_user)
    c.run("profile show", assert_error=True)
    assert "ERROR: Definition of settings.yml 'settings.os.libc' cannot be null" in c.out


def test_settings_user_breaking_universal_binaries():
    # If you had a settings_user.yml with a custom architecture wit will error
    # in the Apple block of CMakeToolchain
    # https://github.com/conan-io/conan/issues/16086#issuecomment-2059118224
    c = TestClient()
    settings_user = textwrap.dedent("""\
        arch: [universal]
        """)
    save(os.path.join(c.cache_folder, "settings_user.yml"), settings_user)
    c.save({"conanfile.py": GenConanfile().with_settings("os").with_settings("arch").with_generator("CMakeToolchain")})
    c.run('install . -s="arch=universal"')
    assert "CMakeToolchain generated: conan_toolchain.cmake" in c.out
