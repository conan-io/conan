import os

from conan.tools.qbs.qbsmoduletemplate import QbsModuleTemplate
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

        # Check if the same package is at host and build and the same time
        activated_br = {r.ref.name for r in build_req.values()
                        if r.ref.name in self.build_context_activated}
        common_names = {r.ref.name for r in host_req.values()}.intersection(activated_br)
        for common_name in common_names:
            suffix = self.build_context_suffix.get(common_name)
            if not suffix:
                raise ConanException("The package '{}' exists both as 'require' and as "
                                     "'build require'. You need to specify a suffix using the "
                                     "'build_context_suffix' attribute at the QbsDeps "
                                     "generator.".format(common_name))

        def add_module(require, dep, comp_name):
            qbs_module_template = QbsModuleTemplate(self, require, dep, comp_name)
            file_content = qbs_module_template.render()
            ret["modules/{}/module.qbs".format(qbs_module_template.filename)] = file_content

        for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            # Require is not used at the moment, but its information could be used,
            # and will be used in Conan 2.0
            # Filter the build_requires not activated with qbsdeps.build_context_activated
            if dep.is_build_context and dep.ref.name not in self.build_context_activated:
                continue

            if dep.cpp_info.get_property("skip_deps_file", "QbsDeps"):
                # Skip the generation of config files for this node, it will be located externally
                continue

            if dep.cpp_info.has_components:
                for comp_name in dep.cpp_info.component_names:
                    add_module(require, dep, comp_name)
            else:
                add_module(require, dep, None)

        return ret
