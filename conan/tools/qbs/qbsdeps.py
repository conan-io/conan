import os

from conan.tools.qbs.qbsmoduletemplate import QbsModuleTemplate
from conan.tools.qbs.qbsconanmoduleproviderinfotemplate import QbsConanModuleProviderInfoTemplate
from conans.errors import ConanException
from conans.util.files import save


class QbsDeps(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Activate the build config files for the specified libraries
        self.build_context_activated = []
        # If specified, the files/targets/variables for the build context will be renamed appending
        # a suffix. It is necessary in case of same require and build_require and will cause an error
        self.build_context_suffix = {}

    def generate(self):
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    @property
    def content(self):
        ret = {}

        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.direct_build
        test_req = self._conanfile.dependencies.test

        self._check_if_build_require_suffix_is_missing(host_req, build_req)

        requires = []
        dependencies = []
        for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            # Require is not used at the moment, but its information could be used,
            # and will be used in Conan 2.0
            # Filter the build_requires not activated with qbsdeps.build_context_activated
            if dep.is_build_context and dep.ref.name not in self.build_context_activated:
                continue

            if dep.cpp_info.get_property("skip_deps_file", "QbsDeps"):
                # Skip the generation of config files for this node, it will be located externally
                continue

            requires.append(require)
            dependencies.append(dep)

            if dep.cpp_info.has_components:
                for comp_name in dep.cpp_info.component_names:
                    ret.update(self._get_module(require, dep, comp_name))
            else:
                ret.update(self._get_module(require, dep, None))
        ret.update(self._get_conan_module_provider_info(requires, dependencies))

        return ret

    def _activated_build_requires(self, build_requires):
        return {r.ref.name for r in build_requires.values()
                if r.ref.name in self.build_context_activated}

    def _get_module(self, require, dep, comp_name):
        qbs_module_template = self._create_module_template(require, dep, comp_name)
        file_content = qbs_module_template.render()
        return {"modules/{}/module.qbs".format(qbs_module_template.filename): file_content}

    def _get_conan_module_provider_info(self, requires, dependencies):
        qbs_conan_module_provider_info_template = self._create_module_provider_info_template(
            requires, dependencies)
        return {"qbs_conan-moduleprovider_info.json":
                qbs_conan_module_provider_info_template.render()}

    def _create_module_template(self, require, dep, comp_name):
        return QbsModuleTemplate(self, require, dep, comp_name)

    def _create_module_provider_info_template(self, requires, dependencies):
        return QbsConanModuleProviderInfoTemplate(self, requires, dependencies)

    def _check_if_build_require_suffix_is_missing(self, host_requires, build_requires):
        activated_br = self._activated_build_requires(build_requires)
        common_names = {r.ref.name for r in host_requires.values()}.intersection(activated_br)
        for common_name in common_names:
            suffix = self.build_context_suffix.get(common_name)
            if not suffix:
                raise ConanException("The package '{}' exists both as 'require' and as "
                                     "'build require'. You need to specify a suffix using the "
                                     "'build_context_suffix' attribute at the QbsDeps "
                                     "generator.".format(common_name))
