import os

from conan.tools.build import build_jobs
from conan.tools.meson import MesonToolchain


class Meson(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def configure(self, reconfigure=False):
        source_folder = self._conanfile.source_folder
        build_folder = self._conanfile.build_folder
        cmd = "meson setup"
        generators_folder = self._conanfile.generators_folder
        cross = os.path.join(generators_folder, MesonToolchain.cross_filename)
        native = os.path.join(generators_folder, MesonToolchain.native_filename)
        if os.path.exists(cross):
            cmd += ' --cross-file "{}"'.format(cross)
        else:
            cmd += ' --native-file "{}"'.format(native)
        cmd += ' "{}" "{}"'.format(build_folder, source_folder)
        if self._conanfile.package_folder:
            cmd += ' -Dprefix="{}"'.format(self._conanfile.package_folder)
        if reconfigure:
            cmd += ' --reconfigure'
        self._conanfile.output.info("Meson configure cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def build(self, target=None):
        meson_build_folder = self._conanfile.build_folder
        cmd = 'meson compile -C "{}"'.format(meson_build_folder)
        njobs = build_jobs(self._conanfile)
        if njobs:
            cmd += " -j{}".format(njobs)
        if target:
            cmd += " {}".format(target)
        self._conanfile.output.info("Meson build cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def install(self):
        self.configure(reconfigure=True)  # To re-do the destination package-folder
        meson_build_folder = self._conanfile.build_folder
        cmd = 'meson install -C "{}"'.format(meson_build_folder)
        self._conanfile.run(cmd)

    def test(self):
        meson_build_folder = self._conanfile.build_folder
        cmd = 'meson test -v -C "{}"'.format(meson_build_folder)
        # TODO: Do we need vcvars for test?
        # TODO: This should use conanrunenv, but what if meson itself is a build-require?
        self._conanfile.run(cmd)
