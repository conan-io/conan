import jinja2
from jinja2 import Template


class CMakeDepsFileTemplate(object):

    def __init__(self, req, configuration):
        if req is not None:
            self.conanfile = req
            self.pkg_name = req.ref.name
            self.package_folder = req.package_folder.\
                replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
        self.configuration = configuration

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
    def config_suffix(self):
        return "_{}".format(self.configuration.upper()) if self.configuration else ""

    def get_dependency_names(self):
        """Get a list of the targets file names (not alias) required by req"""
        ret = []
        if self.conanfile.new_cpp_info.required_components:
            for dep_name, _ in self.conanfile.new_cpp_info.required_components:
                if dep_name and dep_name not in ret:  # External dep
                    ret.append(dep_name)
        elif self.conanfile.dependencies.host_requires:
            ret = [r.ref.name for r in self.conanfile.dependencies.host_requires]
        return ret
