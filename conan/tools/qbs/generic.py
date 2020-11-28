import shlex
import platform
import textwrap

from io import StringIO
from jinja2 import Template
from conans import tools
from conans.errors import ConanException
from conans.util.files import save

_profile_name = "conan"
_profiles_prefix_in_config = "profiles.%s" % _profile_name


class QbsException(ConanException):
    def __str__(self):
        msg = super(QbsException, self).__str__()
        return "Qbs generic toolchain: {}".format(msg)


def _env_var_to_list(var):
    return list(shlex.shlex(var, posix=True, punctuation_chars=True))


def _check_for_compiler(conanfile):
    compiler = conanfile.settings.get_safe("compiler")
    if not compiler:
        raise QbsException("need compiler to be set in settings")

    if compiler not in ["Visual Studio", "gcc", "clang"]:
        raise QbsException("compiler not supported")


def _compiler_name(conanfile):
    # needs more work since currently only windows and linux is supported
    compiler = conanfile.settings.get_safe("compiler")
    the_os = conanfile.settings.get_safe("os")
    if the_os == "Windows":
        if compiler == "gcc":
            return "mingw"
        if compiler == "Visual Studio":
            if tools.msvs_toolset(conanfile) == "ClangCl":
                return "clang-cl"
            return "cl"
        if compiler == "clang":
            return "clang-cl"
        raise QbsException("unknown windows compiler")

    if the_os == "Linux":
        return compiler

    raise QbsException("unknown compiler")


def _settings_dir(conanfile):
    return '%s/conan_qbs_toolchain_settings_dir' % conanfile.install_folder


def _setup_toolchains(conanfile):
    if tools.get_env("CC"):
        compiler = tools.get_env("CC")
    else:
        compiler = _compiler_name(conanfile)

    env_context = tools.no_op()
    if platform.system() == "Windows":
        if compiler in ["cl", "clang-cl"]:
            env_context = tools.vcvars()

    with env_context:
        cmd = "qbs-setup-toolchains --settings-dir %s %s %s" % (
              _settings_dir(conanfile), compiler, _profile_name)
        conanfile.run(cmd)


def _read_qbs_toolchain_from_config(conanfile):
    s = StringIO()
    conanfile.run("qbs-config --settings-dir %s --list" % (
                    _settings_dir(conanfile)), output=s)
    config = {}
    s.seek(0)
    for line in s:
        colon = line.index(':')
        if 0 < colon and not line.startswith('#'):
            full_key = line[:colon]
            if full_key.startswith(_profiles_prefix_in_config):
                key = full_key[len(_profiles_prefix_in_config)+1:]
                value = line[colon+1:].strip()
                if value.startswith('"') and value.endswith('"'):
                    temp_value = value[1:-1]
                    if (temp_value.isnumeric() or
                            temp_value in ['true', 'false', 'undefined']):
                        value = temp_value
                config[key] = value
    return config


def _flags_from_env():
    flags_from_env = {}
    if tools.get_env("ASFLAGS"):
        flags_from_env["cpp.assemblerFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("ASFLAGS")))
    if tools.get_env("CFLAGS"):
        flags_from_env["cpp.cFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("CFLAGS")))
    if tools.get_env("CPPFLAGS"):
        flags_from_env["cpp.cppFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("CPPFLAGS")))
    if tools.get_env("CXXFLAGS"):
        flags_from_env["cpp.cxxFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("CXXFLAGS")))
    if tools.get_env("LDFLAGS"):
        ld_flags = []
        for item in _env_var_to_list(tools.get_env("LDFLAGS")):
            if item not in ['-Wl', ',']:
                ld_flags.append(item)
        flags_from_env["cpp.linkerFlags"] = str(ld_flags)
    return flags_from_env


class QbsGenericToolchain(object):
    filename = "conan_toolchain.qbs"

    _template_toolchain = textwrap.dedent('''\
        import qbs

        Project {
            Profile {
                name: "conan_toolchain_profile"
                {%- for key, value in profile_values.items() %}
                {{ key }}: {{ value }}
                {%- endfor %}
            }
        }
        ''')

    def __init__(self, conanfile):
        _check_for_compiler(conanfile)
        self._conanfile = conanfile
        _setup_toolchains(conanfile)
        self._profile_values = _read_qbs_toolchain_from_config(conanfile)
        self._profile_values.update(_flags_from_env())
        tools.rmdir(_settings_dir(conanfile))

    def write_toolchain_files(self):
        save(self.filename, self.content)

    @property
    def content(self):
        context = {"profile_values": self._profile_values}
        t = Template(self._template_toolchain)
        content = t.render(**context)
        return content
