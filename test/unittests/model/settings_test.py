import textwrap
import pytest

from conan.internal.default_settings import default_settings_yml
from conan.errors import ConanException
from conan.internal.model.settings import Settings, bad_value_msg, undefined_field


def undefined_value(v):
    return "'%s' value not defined" % v


class TestSettingsLoads:

    def test_none_value(self):
        yml = "os: [null, Windows]"
        settings = Settings.loads(yml)
        settings.validate()
        assert settings.os == None
        assert "" == settings.dumps()
        settings.os = "Windows"
        assert settings.os == "Windows"
        assert "os=Windows" == settings.dumps()

    def test_any(self):
        yml = "os: [ANY]"
        settings = Settings.loads(yml)
        with pytest.raises(ConanException, match="'settings.os' value not defined"):
            settings.validate()  # Raise exception if unset
        settings.os = "some-os"
        settings.validate()
        assert settings.os == "some-os"
        assert "os=some-os" in settings.dumps()
        settings.os = "Windows"
        assert settings.os == "Windows"
        assert "os=Windows" == settings.dumps()

    def test_none_any(self):
        yml = "os: [null, ANY]"
        settings = Settings.loads(yml)
        settings.validate()
        settings.os = "None"
        settings.validate()
        assert settings.os == "None"
        assert "os=None" in settings.dumps()
        settings.os = "Windows"
        assert settings.os == "Windows"
        assert "os=Windows" == settings.dumps()

    def test_nested_any(self):
        yml = textwrap.dedent("""\
            os:
                ANY:
                    version: [null, ANY]
                Ubuntu:
                    version: ["18.04", "20.04"]
            """)
        settings = Settings.loads(yml)
        settings.os = "Windows"
        settings.validate()
        assert settings.os == "Windows"
        assert "os=Windows" in settings.dumps()
        settings.os.version = 2
        assert settings.os == "Windows"
        assert "os=Windows\nos.version=2" == settings.dumps()
        settings.os = "Ubuntu"
        with pytest.raises(ConanException, match="'settings.os.version' value not defined"):
            settings.validate()
        with pytest.raises(ConanException, match="Invalid setting '3' is not a valid 'settings.os.version'"):
            settings.os.version = 3
        settings.os.version = "20.04"
        assert "os=Ubuntu\nos.version=20.04" == settings.dumps()
        assert settings.os.version == "20.04"

    def test_getattr_none(self):
        yml = "os: [None, Windows]"
        settings = Settings.loads(yml)
        assert settings.os == None
        _os = getattr(settings, "os")
        assert _os == None
        assert str(_os) == "None"

    def test_get_safe(self):
        yml = "os: [None, Windows]"
        settings = Settings.loads(yml)
        settings.os = "Windows"
        assert settings.os == "Windows"
        assert settings.get_safe("compiler.version") == None
        assert settings.get_safe("build_type") == None
        assert "Release" == settings.get_safe("build_type", "Release")
        assert False == settings.get_safe("build_type", False)
        assert "Windows" == settings.get_safe("os", "Linux")

    def test_none_subsetting(self):
        yml = """os:
    null:
    Windows:
        subsystem: [null, cygwin]
"""
        settings = Settings.loads(yml)
        settings.validate()
        assert settings.os == None
        assert "" == settings.dumps()
        settings.os = "Windows"
        assert settings.os.subsystem == None
        assert "os=Windows" == settings.dumps()
        settings.os.subsystem = "cygwin"
        settings.validate()
        assert "os=Windows\nos.subsystem=cygwin" == settings.dumps()

    def test_none__sub_subsetting(self):
        yml = """os:
    null:
        subsystem: [null, cygwin]
    Windows:
"""
        with pytest.raises(ConanException, match="settings.yml: null setting can't have subsettings"):
            Settings.loads(yml)


class TestSettings:

    @pytest.fixture(autouse=True)
    def setup(self):
        data = {"compiler": {
                            "Visual Studio": {
                                             "version": ["10", "11", "12"],
                                             "runtime": ["MD", "MT"]},
                            "gcc": {
                                   "version": ["4.8", "4.9"],
                                   "arch": {"x86": {"speed": ["A", "B"]},
                                            "x64": {"speed": ["C", "D"]}}}
                                   },
                "os": ["Windows", "Linux"]}
        self.sut = Settings(data)

    def test_in_contains(self):
        self.sut.compiler = "Visual Studio"
        assert "Visual" in self.sut.compiler
        assert not ("Visual" not in self.sut.compiler)

    def test_os_split(self):
        settings = Settings.loads("""os:
    Windows:
    Linux:
    Macos:
        version: [1, 2]
    Android:
""")
        other_settings = Settings.loads("os: [Windows, Linux]")
        settings.os = "Windows"
        other_settings.os = "Windows"
        assert settings.dumps() == other_settings.dumps()

    def test_any(self):
        data = {"target": ["ANY"]}
        sut = Settings(data)
        sut.target = "native"
        assert sut.target == "native"

    def test_multi_os(self):
        settings = Settings.loads("""os:
            Windows:
            Linux:
                distro: [RH6, RH7]
            Macos:
                codename: [Mavericks, Yosemite]
        """)
        settings.os = "Windows"
        assert settings.os == "Windows"
        settings.os = "Linux"
        settings.os.distro = "RH6"
        assert settings.os.distro == "RH6"
        with pytest.raises(ConanException):
            settings.os.distro = "Other"
        with pytest.raises(ConanException):
            settings.os.codename = "Yosemite"
        settings.os = "Macos"
        settings.os.codename = "Yosemite"
        assert settings.os.codename == "Yosemite"

    def test_remove(self):
        del self.sut.compiler
        self.sut.os = "Windows"
        self.sut.validate()
        assert self.sut.dumps() == "os=Windows"

    def test_loads_default(self):
        settings = Settings.loads("""os: [Windows, Linux, Macos, Android, FreeBSD, SunOS]
arch: [x86, x86_64, arm]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
    gcc:
        version: ["4.8", "4.9", "5.0"]
    msvc:
        runtime: [None, MD, MT, MTd, MDd]
        version: ["10", "11", "12"]
    clang:
        version: ["3.5", "3.6", "3.7"]

build_type: [None, Debug, Release]""")
        settings.compiler = "clang"
        settings.compiler.version = "3.5"
        assert settings.compiler == "clang"
        assert settings.compiler.version == "3.5"

    def test_loads(self):
        settings = Settings.loads("""
compiler:
    msvc:
        runtime: [MD, MT]
        version:
            '10':
                arch: ["32"]
            '11':
                &id1
                arch: ["32", "64"]
            '12':
                *id1
    gcc:
        arch:
            x64:
                speed: [C, D]
            x86:
                speed: [A, B]
        version: ['4.8', '4.9']
os: [Windows, Linux]
""")
        settings.update_values([('compiler', 'msvc'),
                                ('compiler.version', '10'),
                                ('compiler.version.arch', '32')])
        assert settings.values_list == [('compiler', 'msvc'),
                          ('compiler.version', '10'),
                          ('compiler.version.arch', '32')]

        settings.compiler.version = "10"
        settings.compiler.version.arch = "32"
        settings.compiler.version = "11"
        settings.compiler.version.arch = "64"
        settings.compiler.version = "12"
        settings.compiler.version.arch = "64"

        assert settings.values_list == [('compiler', 'msvc'),
                          ('compiler.version', '12'),
                          ('compiler.version.arch', '64')]

    def test_set_value(self):
        self.sut.update_values([("compiler", "Visual Studio")])
        assert self.sut.compiler == "Visual Studio"
        self.sut.update_values([("compiler.version", "12")])
        assert self.sut.compiler.version == "12"
        self.sut.update_values([("compiler", "gcc")])
        assert self.sut.compiler == "gcc"
        self.sut.update_values([("compiler.version", "4.8")])
        assert self.sut.compiler.version == "4.8"
        self.sut.update_values([("compiler.arch", "x86")])
        assert self.sut.compiler.arch == "x86"
        self.sut.update_values([("compiler.arch.speed", "A")])
        assert self.sut.compiler.arch.speed == "A"

    def test_constraint(self):
        s2 = ["os"]
        self.sut.constrained(s2)
        with pytest.raises(ConanException) as cm:
            self.sut.compiler
        assert str(cm.value) == str(undefined_field("settings", "compiler", ["os"], "settings"))
        self.sut.os = "Windows"
        self.sut.os = "Linux"

    def test_constraint2(self):
        s2 = ["os2"]
        with pytest.raises(ConanException) as cm:
            self.sut.constrained(s2)
        assert str(cm.value) == str(undefined_field("settings", "os2", ["compiler", "os"], "settings"))

    def test_constraint6(self):
        s2 = {"os", "compiler"}
        self.sut.constrained(s2)
        self.sut.compiler = "Visual Studio"
        with pytest.raises(ConanException) as cm:
            self.sut.compiler.arch
        assert str(cm.value) == str(undefined_field("settings.compiler", "arch",
                                                                ['runtime', 'version'], "Visual Studio"))
        self.sut.os = "Windows"
        self.sut.compiler.version = "11"
        self.sut.compiler.version = "12"

    def test_validate(self):
        with pytest.raises(ConanException, match=str(undefined_value("settings.compiler"))):
            self.sut.validate()

        self.sut.compiler = "gcc"
        with pytest.raises(ConanException, match="value not defined"):
            self.sut.validate()

        self.sut.compiler.arch = "x86"
        with pytest.raises(ConanException, match="value not defined"):
            self.sut.validate()

        self.sut.compiler.arch.speed = "A"
        with pytest.raises(ConanException, match="value not defined"):
            self.sut.validate()

        self.sut.compiler.version = "4.8"
        with pytest.raises(ConanException, match="value not defined"):
            self.sut.validate()

        self.sut.os = "Windows"
        self.sut.validate()
        assert self.sut.values_list == [("compiler", "gcc"),
                                                ("compiler.arch", "x86"),
                                                ("compiler.arch.speed", "A"),
                                                ("compiler.version", "4.8"),
                                                ("os", "Windows")]

    def test_validate2(self):
        self.sut.os = "Windows"
        self.sut.compiler = "Visual Studio"
        with pytest.raises(ConanException, match="value not defined"):
            self.sut.validate()

        self.sut.compiler.runtime = "MD"
        with pytest.raises(ConanException, match="value not defined"):
            self.sut.validate()

        self.sut.compiler.version = "10"
        self.sut.validate()

        assert self.sut.values_list == [("compiler", "Visual Studio"),
                                                ("compiler.runtime", "MD"),
                                                ("compiler.version", "10"),
                                                ("os", "Windows")]

    def test_basic(self):
        s = Settings({"os": ["Windows", "Linux"]})
        s.os = "Windows"
        with pytest.raises(ConanException) as cm:
            self.sut.compiler = "kk"
        assert str(cm.value) == bad_value_msg("settings.compiler", "kk", ['Visual Studio', 'gcc'])

    def test_my(self):
        assert self.sut.compiler == None

        with pytest.raises(ConanException) as cm:
            self.sut.compiler = "kk"
        assert str(cm.value) == bad_value_msg("settings.compiler", "kk", ['Visual Studio', 'gcc'])

        self.sut.compiler = "Visual Studio"
        assert str(self.sut.compiler) == "Visual Studio"
        assert self.sut.compiler == "Visual Studio"

        with pytest.raises(ConanException) as cm:
            self.sut.compiler.kk
        assert str(cm.value) == str(undefined_field("settings.compiler", "kk", ['runtime', 'version'],
                                             "Visual Studio"))

        assert self.sut.compiler.version == None

        with pytest.raises(ConanException) as cm:
            self.sut.compiler.version = "123"
        assert str(cm.value) == bad_value_msg("settings.compiler.version", "123", ['10', '11', '12'])

        self.sut.compiler.version = "12"
        assert self.sut.compiler.version == "12"
        assert str(self.sut.compiler.version) == "12"

        with pytest.raises(ConanException) as cm:
            assert self.sut.compiler == "kk"
        assert str(cm.value) == bad_value_msg("settings.compiler", "kk", ['Visual Studio', 'gcc'])

        assert not (self.sut.compiler == "gcc")
        assert self.sut.compiler == "Visual Studio"

        assert self.sut.compiler.version == "12"
        assert not (self.sut.compiler.version == "11")

        with pytest.raises(ConanException) as cm:
            assert self.sut.compiler.version == "13"
        assert str(cm.value) == bad_value_msg("settings.compiler.version", "13", ['10', '11', '12'])

        self.sut.compiler = "gcc"
        with pytest.raises(ConanException) as cm:
            self.sut.compiler.runtime
        assert str(cm.value) == str(undefined_field("settings.compiler", "runtime", "['arch', 'version']",
                                             "gcc"))

        self.sut.compiler.arch = "x86"
        self.sut.compiler.arch.speed = "A"
        assert self.sut.compiler.arch.speed == "A"

        with pytest.raises(ConanException) as cm:
            self.sut.compiler.arch.speed = "D"
        assert str(cm.value) == bad_value_msg("settings.compiler.arch.speed", "D", ['A', 'B'])

        self.sut.compiler.arch = "x64"
        self.sut.compiler.arch.speed = "C"
        assert self.sut.compiler.arch.speed == "C"

        with pytest.raises(ConanException) as cm:
            self.sut.compiler.arch.speed = "A"
        assert str(cm.value) == bad_value_msg("settings.compiler.arch.speed", "A", ['C', 'D'])

        self.sut.compiler.arch.speed = "D"
        assert self.sut.compiler.arch.speed == "D"


def test_possible_values():
    settings = Settings.loads(default_settings_yml)
    settings.compiler = "gcc"
    sot = settings.compiler.cppstd.possible_values()
    assert sot == [None, '98', 'gnu98', '11', 'gnu11', '14', 'gnu14', '17', 'gnu17', '20',
                   'gnu20', '23', 'gnu23', '26', 'gnu26']

    # We cannot access the child definition of a non declared setting
    with pytest.raises(Exception) as e:
        settings.os.version.possible_values()

    assert "'settings.os' value not defined" in str(e.value)

    # But if we have it declared, we can
    settings.os = "watchOS"
    sot = settings.os.version.possible_values()
    assert "4.0" in sot

    # We can get the whole settings definition and explore the dict
    sot = settings.possible_values()
    assert [None, "cygwin", "msys", "msys2", "wsl"] == sot["os"]["Windows"]["subsystem"]


def test_rm_safe():
    settings = Settings.loads(default_settings_yml)
    settings.rm_safe("compiler.cppstd")
    settings.rm_safe("compiler.libcxx")
    settings.compiler = "gcc"
    with pytest.raises(Exception) as e:
        settings.compiler.cppstd = "14"
    assert "'settings.compiler.cppstd' doesn't exist for 'gcc'" in str(e.value)
    with pytest.raises(Exception) as e:
        settings.compiler.libcxx = "libstdc++"
    assert "'settings.compiler.libcxx' doesn't exist for 'gcc'" in str(e.value)

    settings.compiler = "clang"
    with pytest.raises(Exception) as e:
        settings.compiler.cppstd = "14"
    assert "'settings.compiler.cppstd' doesn't exist for 'clang'" in str(e.value)
    with pytest.raises(Exception) as e:
        settings.compiler.libcxx = "libstdc++"
    assert "'settings.compiler.libcxx' doesn't exist for 'clang'" in str(e.value)


def test_rm_safe_wildcard():
    settings = Settings.loads(default_settings_yml)
    settings.compiler = "gcc"
    settings.compiler.version = "4.8"
    settings.compiler.libcxx = "libstdc++"
    settings.rm_safe("compiler.*")
    assert settings.compiler == "gcc"
    assert settings.get_safe("compiler.version") is None
    assert settings.get_safe("compiler.libcxx") is None


def test_settings_intel_cppstd_03():
    settings = Settings.loads(default_settings_yml)
    settings.compiler = "intel-cc"
    # This doesn't crash, it used to crash due to "03" not quoted in setting.yml
    settings.compiler.cppstd = "03"


def test_set_value_non_existing_values():
    data = {
        "compiler": {
            "gcc": {
                "version": ["4.8", "4.9"],
                "arch": {"x86": {"speed": ["A", "B"]},
                         "x64": {"speed": ["C", "D"]}}}
        },
        "os": ["Windows", "Linux"]
    }
    settings = Settings(data)
    with pytest.raises(ConanException) as cm:
        settings.update_values([("foo", "A")])
    assert "'settings.foo' doesn't exist for 'settings'" in str(cm.value)
    with pytest.raises(ConanException) as cm:
        settings.update_values([("foo.bar", "A")])
    assert "'settings.foo' doesn't exist for 'settings'" in str(cm.value)
    # it does not raise any error
    settings.update_values([("foo", "A")], raise_undefined=False)
    settings.update_values([("foo.bar", "A")], raise_undefined=False)
