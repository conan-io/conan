from conan.tools.gnu.pkgconfigdeps.pc_files_creator import get_pc_files_and_content
from conans.util.files import save


class PkgConfigDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def content(self):
        """Get all the *.pc files content"""
        pc_files = {}
        host_req = self._conanfile.dependencies.host
        for _, dep in host_req.items():
            dep_name = str(dep)
            for pc_name, pc_content in get_pc_files_and_content(self._conanfile, dep).items():
                if pc_name in pc_files:
                    _, analyzed_dep_name = pc_files[pc_name]
                    self._conanfile.output.warn(
                        "[%s] The PC file name %s already exists and it matches with another "
                        "name/alias declared in %s package. Please, review all the "
                        "pkg_config_name/pkg_config_aliases defined. Skipping it!"
                        % (dep_name, pc_name, analyzed_dep_name))
                else:
                    pc_files[pc_name] = (pc_content, dep_name)
        return pc_files

    def generate(self):
        """Save all the *.pc files"""
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, (content, _) in generator_files.items():
            save(generator_file, content)
