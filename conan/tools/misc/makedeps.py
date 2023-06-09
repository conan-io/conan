# -*- coding: utf-8 -*-

import os
import re

from conan.internal import check_duplicated_generator
from conan.tools.files import save
from conans.model.build_info import CppInfo

class MakeDeps(object):

    _output_filename = "conandeps.mk"
    _title = "Makefile variables from Conan dependencies"

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile

    def _var_ref(self, var):
        return f"$({var})"

    def _var_assign_single(self, var, value):
        return f"{var} = {value}"

    def _var_assign_multi(self, var, value):
        return " \\\n\t".join([f"{var} ="] + value)

    def generate(self):
        check_duplicated_generator(self, self._conanfile)

        line_buffer = []
        var_aggregates = {}

        def _divert():
            buf = list(line_buffer)
            line_buffer.clear()
            return buf

        # Convert a name to Make-variable-friendly syntax
        def _makeify(name):
            return re.sub(r'[^0-9A-Z_]', '_', name.upper())

        # Replace common prefixes in a path list with a variable reference
        def _rootify(root, root_id, path_list):
            root_len = len(root)
            root_with_sep = root + os.path.sep
            root_var_ref = self._var_ref(f"CONAN_ROOT_{root_id}")
            return [root_var_ref + path[root_len:] \
                    if path.startswith(root_with_sep) else path for path in path_list]

        # Output a variable assignment, appropriately formatted
        def _output_var(name, item, root=None, root_id=None, prefix_var=None, blank_after=True):
            if item is None:
                return False
            if type(item).__name__ in ('Component', 'SettingsItem', 'Version', 'str'):
                value = str(item)
                if not value:
                    return False
                line_buffer.append(self._var_assign_single(name, value))
            else:
                assert type(item) is list
                ritem = _rootify(root, root_id, item) if root else item
                if prefix_var:
                    ritem = [self._var_ref(prefix_var) + i for i in ritem]
                if len(ritem) == 0:
                    return False
                elif len(ritem) == 1:
                    line_buffer.append(self._var_assign_single(name, ritem[0]))
                else:
                    line_buffer.append(self._var_assign_multi(name, ritem))
            if blank_after:
                line_buffer.append("")
            return True

        def _output_cpp_info_vars(var_id, cpp_info, root=None, root_id=None, add_to_aggregates=True):
            def _var(name, item, prefix_var=None):
                v = f"CONAN_{name}_{var_id}"
                if _output_var(v, item, root, root_id, prefix_var) and add_to_aggregates:
                    var_aggregates.setdefault(name, []).append(self._var_ref(v))
            _var("SYSROOT",         cpp_info.sysroot)
            _var("INCLUDE_DIRS",    cpp_info.includedirs, "CONAN_INCLUDE_DIR_FLAG")
            _var("LIB_DIRS",        cpp_info.libdirs,     "CONAN_LIB_DIR_FLAG")
            _var("BIN_DIRS",        cpp_info.bindirs)
            _var("SRC_DIRS",        cpp_info.srcdirs)
            _var("BUILD_DIRS",      cpp_info.builddirs)
            _var("OBJECTS",         cpp_info.objects)
            _var("RES_DIRS",        cpp_info.resdirs)
            _var("LIBS",            cpp_info.libs,        "CONAN_LIB_FLAG")
            _var("SYSTEM_LIBS",     cpp_info.system_libs, "CONAN_SYSTEM_LIB_FLAG")
            _var("DEFINES",         cpp_info.defines,     "CONAN_DEFINE_FLAG")
            _var("CFLAGS",          cpp_info.cflags)
            _var("CXXFLAGS",        cpp_info.cxxflags)
            _var("SHAREDLINKFLAGS", cpp_info.sharedlinkflags)
            _var("EXELINKFLAGS",    cpp_info.exelinkflags)
            _var("FRAMEWORKS",      cpp_info.frameworks)
            _var("FRAMEWORK_DIRS",  cpp_info.frameworkdirs)
            _var("REQUIRES",        cpp_info.requires)

        # Top-of-file banner
        line_buffer.extend([
            "#" * 72,
            "##" + " " * 68 + "##",
            "##" + self._title.center(68) + "##",
            "##" + " " * 68 + "##",
            "#" * 72,
            ""
        ])

        # Output settings variables
        for key, value in self._conanfile.settings.items():
            var_name = "CONAN_" + _makeify(key)
            _output_var(var_name, value, blank_after=False)
        line_buffer.append("")

        preamble = _divert()

        body = []
        dep_name_list = []

        for require, dep in self._conanfile.dependencies.items():
            dep_id = _makeify(require.ref.name)
            dep_name_list.append(require.ref.name)

            root = dep.package_folder

            line_buffer.extend([
                "",
                f"# {require.ref.name}/{require.ref.version}",
                f"# (" + ("direct" if require.direct else "indirect") + " dependency)",
                ""
            ])

            _output_var(f"CONAN_ROOT_{dep_id}",    root)
            _output_var(f"CONAN_VERSION_{dep_id}", require.ref.version)

            _output_cpp_info_vars(dep_id, dep.cpp_info, root, dep_id)

            dep_section = _divert()
            comp_name_list = []

            for comp_name, component in dep.cpp_info.components.items():
                line_buffer.append(f"# {require.ref.name}::{comp_name}")
                line_buffer.append("")
                comp_id = _makeify(comp_name)
                comp_name_list.append(comp_name)
                _output_cpp_info_vars(f"{dep_id}_{comp_id}", component, root, dep_id, False)

            comp_section = _divert()

            line_buffer.extend(dep_section)
            _output_var(f"CONAN_COMPONENTS_{dep_id}", comp_name_list)
            line_buffer.extend(comp_section)

            body.extend(_divert())

        assert not line_buffer
        line_buffer.extend([
            "",
            "# Aggregated values",
            "# (note: these do not include components)",
            ""
        ])
        for var_name, var_list in var_aggregates.items():
            _output_var(f"CONAN_{var_name}", var_list)
        body.extend(_divert())

        line_buffer.extend(preamble)
        _output_var("CONAN_DEPS", dep_name_list)
        line_buffer.extend(body)
        line_buffer.extend(["", "#" * 72])

        save(self._conanfile, self._output_filename, "\n".join(line_buffer))
        self._conanfile.output.info(f"Generated {self._output_filename}")
