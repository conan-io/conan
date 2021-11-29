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
            pc_files.update(get_pc_files_and_content(self._conanfile, dep))
        return pc_files

    def generate(self):
        """Save all the *.pc files"""
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)
