import textwrap

from jinja2 import Template

from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conan.tools.meson.helpers import to_meson_value
from conans.model.new_build_info import NewCppInfo
from conans.util.files import save


class MesonDeps(object):
    """Generator that manages all the GNU flags from all the dependencies"""

    filename = "conan_meson_deps_flags.ini"

    _meson_file_template = textwrap.dedent("""
    [constants]
    deps_c_args = {{c_args}}
    deps_c_link_args = {{c_link_args}}
    deps_cpp_args = {{cpp_args}}
    deps_cpp_link_args = {{cpp_link_args}}
    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._ordered_deps = []
        # constants
        self.c_args = []
        self.c_link_args = []
        self.cpp_args = []
        self.cpp_link_args = []

    # TODO: Add all this logic to GnuDepsFlags? Distinguish between GnuFlags and GnuDepsFlags?
    @property
    def ordered_deps(self):
        if not self._ordered_deps:
            deps = self._conanfile.dependencies.host.topological_sort
            self._ordered_deps = [dep for dep in reversed(deps.values())]
        return self._ordered_deps

    def _get_cpp_info(self):
        ret = NewCppInfo()
        for dep in self.ordered_deps:
            dep_cppinfo = dep.cpp_info.aggregated_components()
            # In case we have components, aggregate them, we do not support isolated
            # "targets" with autotools
            ret.merge(dep_cppinfo)
        return ret

    def _rpaths_flags(self):
        flags = []
        for dep in self.ordered_deps:
            flags.extend(["-Wl,-rpath -Wl,{}".format(libdir) for libdir in dep.cpp_info.libdirs
                          if dep.options.get_safe("shared", False)])
        return flags

    def get_gnu_flags(self):
        flags = GnuDepsFlags(self._conanfile, self._get_cpp_info())

        # cpp_flags
        cpp_flags = []
        cpp_flags.extend(flags.include_paths)
        cpp_flags.extend(flags.defines)

        # Ldflags
        ldflags = flags.sharedlinkflags
        ldflags.extend(flags.exelinkflags)
        ldflags.extend(flags.frameworks)
        ldflags.extend(flags.framework_paths)
        ldflags.extend(flags.lib_paths)

        # set the rpath in Macos so that the library are found in the configure step
        if self._conanfile.settings.get_safe("os") == "Macos":
            ldflags.extend(self._rpaths_flags())

        # libs
        libs = flags.libs
        libs.extend(flags.system_libs)

        # cflags
        cflags = flags.cflags
        cxxflags = flags.cxxflags
        return cflags, cxxflags, cpp_flags, ldflags, libs

    def _context(self):
        cflags, cxxflags, cpp_flags, ldflags, _ = self.get_gnu_flags()
        self.c_args.extend(cflags + cpp_flags)
        self.cpp_args.extend(cxxflags + cpp_flags)
        self.c_link_args.extend(ldflags)
        self.cpp_link_args.extend(ldflags)

        return {
            "c_args": to_meson_value(self.c_args),
            "c_link_args": to_meson_value(self.c_link_args),
            "cpp_args": to_meson_value(self.cpp_args),
            "cpp_link_args": to_meson_value(self.cpp_link_args),
        }

    def _content(self):
        context = self._context()
        content = Template(self._meson_file_template).render(context)
        return content

    def generate(self):
        save(self.filename, self._content())
