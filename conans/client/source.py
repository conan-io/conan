from conans.paths import DIRTY_FILE, source_exists
import os
from conans.util.files import rmdir, save
import six
from conans.errors import ConanException, format_conanfile_exception
import shutil


def config_source(export_folder, src_folder, conan_file, output, force=False):
    """ creates src folder and retrieve, calling source() from conanfile
    the necessary source code
    """
    dirty = os.path.join(src_folder, DIRTY_FILE)

    def remove_source(raise_error=False):
        output.warn("This can take a while for big packages")
        try:
            rmdir(src_folder, conan_file.short_paths)
        except BaseException as e_rm:
            save(dirty, "")  # Creation of DIRTY flag
            msg = str(e_rm)
            if six.PY2:
                msg = str(e_rm).decode("latin1")  # Windows prints some chars in latin1
            output.error("Unable to remove source folder %s\n%s" % (src_folder, msg))
            output.warn("**** Please delete it manually ****")
            if raise_error or isinstance(e_rm, KeyboardInterrupt):
                raise ConanException("Unable to remove source folder")

    if force:
        output.warn("Forced removal of source folder")
        remove_source(raise_error=True)
    elif os.path.exists(dirty):
        output.warn("Trying to remove dirty source folder")
        remove_source(raise_error=True)
    elif conan_file.build_policy_always:
        output.warn("Detected build_policy 'always', trying to remove source folder")
        remove_source(raise_error=True)

    if not source_exists(src_folder):
        output.info('Configuring sources in %s' % src_folder)
        shutil.copytree(export_folder, src_folder)
        save(dirty, "")  # Creation of DIRTY flag
        os.chdir(src_folder)
        try:
            conan_file.source()
            os.remove(dirty)  # Everything went well, remove DIRTY flag
        except Exception as e:
            os.chdir(export_folder)
            # in case source() fails (user error, typically), remove the src_folder
            # and raise to interrupt any other processes (build, package)
            output.warn("Trying to remove dirty source folder")
            remove_source()
            msg = format_conanfile_exception(output.scope, "source", e)
            raise ConanException(msg)