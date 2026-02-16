import json
import textwrap
import os
from jinja2 import Template, StrictUndefined

from conan.errors import ConanException
from conan.internal.model.pkg_type import PackageType


class DepsTemplate:
    def __init__(self, zigdeps, conanfile):
        self._zigdeps = zigdeps
        self._conanfile = conanfile  # The dependency conanfile, not the consumer one

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=StrictUndefined)
        return t.render(self._context)

    @property
    def filename(self):
        return f"conan_deps.zig"

    def _get_libs(self, cpp_info, pkg_name, pkg_folder=None):
        libs = {}
        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                target = self._get_lib(component, cpp_info.components, pkg_folder, comp_name=name)
                if target is not None:
                    libs[name] = target
        else:
            target = self._get_lib(cpp_info, None, pkg_folder)
            if target is not None:
                libs[pkg_name] = target
        return libs

    def _get_lib(self, info, components, pkg_folder, comp_name=None):
        if info.exe or not (info.package_framework or info.frameworks or info.includedirs or info.libs
                            or info.system_libs or info.defines):
            return {}
        target = {}
        if info.libs:
            if len(info.libs) != 1:
                raise ConanException(f"ZigDeps only allows 1 lib per component:\n"
                                     f"{self._conanfile}: {info.libs}")
            assert info.location, "info.location missing for .libs, it should have been deduced"
            location = info.location
            link_location = info.link_location or None
            lib_type = "SHARED" if info.type is PackageType.SHARED else \
                "STATIC" if info.type is PackageType.STATIC else None
            assert lib_type, f"Unknown package type {info.type}"
            target["type"] = lib_type
            target["location"] = location
            target["link_location"] = link_location
        return target

    def _collect(self, cpp_info, attr):
        result = []
        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                result.extend(getattr(component, attr))
        else:
            result.extend(getattr(cpp_info, attr))
        return result

    def _defines(self, cpp_info):
        result = {}
        for define in self._collect(cpp_info, "defines"):
            if "=" in define:
                name, value = define.split("=", 1)
            else:
                name, value = define, "1"
            result[name] = value
        return result

    def _frameworks(self, cpp_info):
        return self._collect(cpp_info, "frameworks")

    def _system_libs(self, cpp_info):
        return self._collect(cpp_info, "system_libs")

    @property
    def _context(self):
        result = {"deps": {}}
        for require, dep in self._conanfile.dependencies.host.items():
            full_cpp_info = dep.cpp_info.deduce_full_cpp_info(dep)

            result["deps"][dep.ref.name] = {
                "include_paths": full_cpp_info.includedirs,
                "lib_paths": full_cpp_info.libdirs,
                "libs": self._get_libs(full_cpp_info, dep.ref.name),
                "defines": self._defines(full_cpp_info),
                "dependencies": [],#[d.ref.name for d in dep.dependencies.host],
                "frameworks": self._frameworks(full_cpp_info),
                "system_libs": self._system_libs(full_cpp_info),
            }
            if dep.ref.name == "libx264":
                print(f"Libx264 libs: {result['deps'][dep.ref.name]['libs']}")
        return result

    @property
    def _template(self):
        return textwrap.dedent("""\
            const std = @import("std");

            const Dep = struct {
                include_paths: []const []const u8,
                lib_paths: []const []const u8,
                libs: []const []const u8,
                defines: []const struct { name: []const u8, value: []const u8 },
                dependencies: []const []const u8,
                frameworks: []const []const u8,
                system_libs: []const []const u8,
                // c_sources: []const u8,
                // link_libc: bool,
                // link_libcpp: bool,
            };

            // Now, fill the conan_deps struct with the information from Conan

            // initialize directly at compile time
            pub const conan_deps = std.StaticStringMap(Dep).initComptime(.{
                {% for dep_name, dep_info in deps.items() %}
                .{
                    "{{ dep_name }}",
                    Dep{
                        .include_paths = &.{ {% for path in dep_info.include_paths %}"{{ path }}",{% endfor %} },
                        .lib_paths = &.{ {% for path in dep_info.lib_paths %}"{{ path }}",{% endfor %} },
                        .libs = &.{ {% for lib in dep_info.libs.values() %}{% if "location" in lib %}"{{ lib["location"] }}",{% endif %}{% endfor %} },
                        .defines = &.{ {% for define, value in dep_info.defines.items() %}.{ .name="{{ define }}", .value="{{ value }}"},{% endfor %} },
                        .dependencies = &.{ {% for d in dep_info.dependencies %}"{{ d }}",{% endfor %} },
                        .frameworks = &.{ {% for fw in dep_info.frameworks %}"{{ fw }}",{% endfor %} },
                        .system_libs = &.{ {% for lib in dep_info.system_libs %}"{{ lib }}",{% endfor %} },
                    }
                },
                {% endfor %}
            });
            """)
