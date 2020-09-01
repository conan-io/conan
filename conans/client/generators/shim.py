import os

from conans.client.shims.write_shims import generate_shim
from conans.client.tools import get_build_os_arch
from conans.model import Generator


class ShimGenerator(Generator):

    def __init__(self, *args, **kwargs):
        super(ShimGenerator, self).__init__(*args, **kwargs)

    @property
    def filename(self):
        return None

    @property
    def content(self):
        ret = {}
        for dep in self.conanfile.deps_cpp_info.deps:
            print("Generate 'shims' for {}".format(dep))
            for exe in self.conanfile.deps_cpp_info[dep].exes:
                print(" - {}".format(exe))
                os_build, _ = get_build_os_arch(self.conanfile)
                files = generate_shim(exe, self.conanfile.deps_cpp_info[dep], os_build, self.output_path)
                ret.update(files)

        # TODO: Make some files executable, feature requested for generators
        # st = os.stat(exec_wrapper)
        # os.chmod(exec_wrapper, st.st_mode | os.stat.S_IEXEC)

        return ret
