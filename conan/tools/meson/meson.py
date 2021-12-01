import os

from conan.tools.build import build_jobs
from conan.tools.cross_building import cross_building
from conan.tools.meson import MesonToolchain


class Meson(object):
    def __init__(self, conanfile, build_folder='build'):
        self._conanfile = conanfile
        self._build_folder = build_folder

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
        self._conanfile.output.info("Meson configure cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def build(self, target=None):
        cmd = 'meson compile -C "{}"'.format(self._build_dir)
        njobs = build_jobs(self._conanfile)
        if njobs:
            cmd += " -j{}".format(njobs)
        if target:
            cmd += " {}".format(target)
        self._conanfile.output.info("Meson build cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def install(self):
        cmd = 'meson install -C "{}"'.format(self._build_dir)
        # TODO: Do we need vcvars for install?
        vcvars = os.path.join(self._conanfile.install_folder, "conanvcvars")
        self._conanfile.run(cmd)

    def test(self):
        cmd = 'meson test -v -C "{}"'.format(self._build_dir)
        # TODO: Do we need vcvars for test?
        # TODO: This should use conanrunenv, but what if meson itself is a build-require?
        self._conanfile.run(cmd)
