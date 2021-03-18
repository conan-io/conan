import os

from conan.tools.meson import MesonToolchain
from conan.tools.microsoft.visual import vcvars_command, vcvars_arch
from conans.client.tools.oss import cross_building, cpu_count


def ninja_jobs_cmd_line_arg(conanfile, parallel):
    if parallel:
        njobs = conanfile.conf["tools.ninja"].jobs or \
                conanfile.conf["core.build"].processes or \
                cpu_count(output=conanfile.output)
    else:
        njobs = 1
    return "-j{}".format(njobs)


class Meson(object):
    def __init__(self, conanfile, build_folder='build', parallel=True):
        self._conanfile = conanfile
        self._parallel = parallel
        self._build_folder = build_folder

    def _run(self, cmd):
        if self._conanfile.settings.get_safe("compiler") == "Visual Studio":
            vcvars = vcvars_command(self._conanfile.settings.get_safe("compiler.version"),
                                    vcvars_arch(self._conanfile))
            cmd = '%s && %s' % (vcvars, cmd)
        self._conanfile.run(cmd)

    @property
    def _build_dir(self):
        build = self._conanfile.build_folder
        if self._build_folder:
            build = os.path.join(self._conanfile.build_folder, self._build_folder)
        return build

    def configure(self, source_folder=None):
        source = self._conanfile.source_folder
        if source_folder:
            source = os.path.join(self._conanfile.source_folder, source_folder)

        cmd = "meson setup"
        if cross_building(self._conanfile):
            cmd += ' --cross-file "{}"'.format(MesonToolchain.cross_filename)
        else:
            cmd += ' --native-file "{}"'.format(MesonToolchain.native_filename)
        cmd += ' "{}" "{}"'.format(self._build_dir, source)
        if self._conanfile.package_folder:
            cmd += ' -Dprefix="{}"'.format(self._conanfile.package_folder)
        self._run(cmd)

    def build(self, target=None):
        njobs = ninja_jobs_cmd_line_arg(self._conanfile, parallel=self._parallel)
        cmd = 'meson compile -C "{}" {}'.format(self._build_dir, njobs)
        if target:
            cmd += " {}".format(target)
        self._run(cmd)

    def install(self):
        cmd = 'meson install -C "{}"'.format(self._build_dir)
        self._run(cmd)

    def test(self):
        cmd = 'meson test -v -C "{}"'.format(self._build_dir)
        self._run(cmd)
