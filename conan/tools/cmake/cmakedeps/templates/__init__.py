import jinja2
from jinja2 import Template

from conan.tools.cmake.utils import get_file_name
from conans.errors import ConanException


class CMakeDepsFileTemplate(object):

    def __init__(self, cmakedeps, require, conanfile, find_module_mode=False):
        self.cmakedeps = cmakedeps
        self.require = require
        self.conanfile = conanfile
        self.find_module_mode = find_module_mode

    @property
    def pkg_name(self):
        return self.conanfile.ref.name + self.suffix

    @property
    def target_namespace(self):
        return self.get_target_namespace(self.conanfile) + self.suffix

    @property
    def global_target_name(self):
        return self.get_global_target_name(self.conanfile) + self.suffix

    @property
    def file_name(self):
        return get_file_name(self.conanfile, self.find_module_mode) + self.suffix

    @property
    def suffix(self):
        if not self.conanfile.is_build_context:
            return ""
        return self.cmakedeps.build_context_suffix.get(self.conanfile.ref.name, "")

    @property
    def build_modules_activated(self):
        if self.conanfile.is_build_context:
            return self.conanfile.ref.name in self.cmakedeps.build_context_build_modules
        else:
            return self.conanfile.ref.name not in self.cmakedeps.build_context_build_modules

    def render(self):
        context = self.context
        if context is None:
            return
        return Template(self.template, trim_blocks=True, lstrip_blocks=True,
                        undefined=jinja2.StrictUndefined).render(context)

    def context(self):
        raise NotImplementedError()

    @property
    def template(self):
        raise NotImplementedError()

    @property
    def filename(self):
        raise NotImplementedError()

    @property
    def configuration(self):
        if not self.conanfile.is_build_context:
            return self.cmakedeps.configuration \
                if self.cmakedeps.configuration else None
        else:
            return self.conanfile.settings_build.get_safe("build_type")

    @property
    def arch(self):
        if not self.conanfile.is_build_context:
            return self.cmakedeps.arch if self.cmakedeps.arch else None
        else:
            return self.conanfile.settings_build.get_safe("arch")

    @property
    def config_suffix(self):
        return "_{}".format(self.configuration.upper()) if self.configuration else ""

    def get_file_name(self):
        return get_file_name(self.conanfile, find_module_mode=self.find_module_mode)

    def get_target_namespace(self, req):
        if self.find_module_mode:
            ret = req.cpp_info.get_property("cmake_module_target_namespace", "CMakeDeps")
            if ret:
                return ret

        ret = req.cpp_info.get_property("cmake_target_namespace", "CMakeDeps")
        return ret or self.get_global_target_name(req)

    def get_global_target_name(self, req):
        if self.find_module_mode:
            ret = req.cpp_info.get_property("cmake_module_target_name", "CMakeDeps")
            if ret:
                return ret

        ret = req.cpp_info.get_property("cmake_target_name", "CMakeDeps")
        return ret or req.ref.name

    def get_component_alias(self, req, comp_name):
        if comp_name not in req.cpp_info.components:
            # foo::foo might be referencing the root cppinfo
            if req.ref.name == comp_name:
                return self.get_target_namespace(req)
            raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                                 "package requirement".format(name=req.ref.name, cname=comp_name))
        if self.find_module_mode:
            ret = req.cpp_info.components[comp_name].get_property("cmake_module_target_name",
                                                                  "CMakeDeps")
            if ret:
                return ret
        ret = req.cpp_info.components[comp_name].get_property("cmake_target_name", "CMakeDeps")
        return ret or comp_name
