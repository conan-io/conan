import os

from conan.tools.build import build_jobs
from conan.tools.meson.toolchain import MesonToolchain


class Meson(object):
    """
    This class calls Meson commands when a package is being built. Notice that
    this one should be used together with the ``MesonToolchain`` generator.
    """

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile

    def configure(self, reconfigure=False):
        """
        Runs ``meson setup [FILE] "BUILD_FOLDER" "SOURCE_FOLDER" [-Dprefix=/]``
        command, where ``FILE`` could be ``--native-file conan_meson_native.ini``
        (if native builds) or ``--cross-file conan_meson_cross.ini`` (if cross builds).

        :param reconfigure: ``bool`` value that adds ``--reconfigure`` param to the final command.
        """
        if reconfigure:
            self._conanfile.output.warning("reconfigure param has been deprecated."
                                           " Removing in Conan 2.x.", warn_tag="deprecated")
        source_folder = self._conanfile.source_folder
        build_folder = self._conanfile.build_folder
        cmd = "meson setup"
        generators_folder = self._conanfile.generators_folder
        cross = os.path.join(generators_folder, MesonToolchain.cross_filename)
        native = os.path.join(generators_folder, MesonToolchain.native_filename)
        meson_filenames = []
        if os.path.exists(cross):
            cmd_param = " --cross-file"
            meson_filenames.append(cross)
        else:
            cmd_param = " --native-file"
            meson_filenames.append(native)

        machine_files = self._conanfile.conf.get("tools.meson.mesontoolchain:extra_machine_files",
                                                 default=[], check_type=list)
        if machine_files:
            meson_filenames.extend(machine_files)

        cmd += "".join([f'{cmd_param} "{meson_option}"' for meson_option in meson_filenames])
        cmd += ' "{}" "{}"'.format(build_folder, source_folder)
        self._conanfile.output.info("Meson configure cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def build(self, target=None):
        """
        Runs ``meson compile -C . -j[N_JOBS] [TARGET]`` in the build folder.
        You can specify ``N_JOBS`` through the configuration line ``tools.build:jobs=N_JOBS``
        in your profile ``[conf]`` section.

        :param target: ``str`` Specifies the target to be executed.
        """
        meson_build_folder = self._conanfile.build_folder
        cmd = 'meson compile -C "{}"'.format(meson_build_folder)
        njobs = build_jobs(self._conanfile)
        if njobs:
            cmd += " -j{}".format(njobs)
        if target:
            cmd += " {}".format(target)
        verbosity = self._build_verbosity
        if verbosity:
            cmd += " " + verbosity
        self._conanfile.output.info("Meson build cmd: {}".format(cmd))
        self._conanfile.run(cmd)

    def install(self, destdir=None):
        """
        Runs ``meson install -C "." --destdir`` in the build folder.

        :param destdir: ``str`` Specifies the destination folder. If ``None``, it will use
                        the ``conanfile.package_folder`` value.
        """
        meson_build_folder = self._conanfile.build_folder.replace("\\", "/")
        meson_package_folder = self._conanfile.package_folder.replace("\\", "/")
        destdir = meson_package_folder if destdir is None else destdir
        # Assuming meson >= 0.57.0
        cmd = f'meson install -C "{meson_build_folder}"'
        if destdir:
            cmd += f' --destdir "{destdir}"'
        verbosity = self._install_verbosity
        if verbosity:
            cmd += " " + verbosity
        self._conanfile.run(cmd)

    def test(self):
        """
        Runs ``meson test -v -C "."`` in the build folder.
        """
        if self._conanfile.conf.get("tools.build:skip_test", check_type=bool):
            return
        meson_build_folder = self._conanfile.build_folder
        cmd = 'meson test -v -C "{}"'.format(meson_build_folder)
        # TODO: Do we need vcvars for test?
        # TODO: This should use conanrunenv, but what if meson itself is a build-require?
        self._conanfile.run(cmd)

    @property
    def _build_verbosity(self):
        # verbosity of build tools. This passes -v to ninja, for example.
        # See https://github.com/mesonbuild/meson/blob/master/mesonbuild/mcompile.py#L156
        verbosity = self._conanfile.conf.get("tools.compilation:verbosity",
                                             choices=("quiet", "verbose"))
        return "--verbose" if verbosity == "verbose" else ""

    @property
    def _install_verbosity(self):
        # https://github.com/mesonbuild/meson/blob/master/mesonbuild/minstall.py#L81
        # Errors are always logged, and status about installed files is controlled by this flag,
        # so it's a bit backwards
        verbosity = self._conanfile.conf.get("tools.build:verbosity", choices=("quiet", "verbose"))
        return "--quiet" if verbosity else ""
