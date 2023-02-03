import os

from conan.tools.files.copy_pattern import report_files_copied
from conan.api.output import ConanOutput
from conans.errors import ConanException, conanfile_exception_formatter, conanfile_remove_attr
from conans.model.manifest import FileTreeManifest
from conans.model.package_ref import PkgReference
from conans.paths import CONANINFO
from conans.util.files import save, mkdir, chdir


def run_package_method(conanfile, package_id, hook_manager, ref):
    """ calls the recipe "package()" method
    - Assigns folders to conanfile.package_folder, source_folder, install_folder, build_folder
    - Calls pre-post package hook
    """

    if conanfile.package_folder == conanfile.build_folder:
        raise ConanException("Cannot 'conan package' to the build folder. "
                             "--build-folder and package folder can't be the same")

    mkdir(conanfile.package_folder)
    scoped_output = conanfile.output
    # Make the copy of all the patterns
    scoped_output.info("Generating the package")
    scoped_output.info("Temporary package folder %s" % conanfile.package_folder)

    hook_manager.execute("pre_package", conanfile=conanfile)
    if hasattr(conanfile, "package"):
        scoped_output.highlight("Calling package()")
        with conanfile_exception_formatter(conanfile, "package"):
            with chdir(conanfile.build_folder):
                with conanfile_remove_attr(conanfile, ['info'], "package"):
                    conanfile.package()
    hook_manager.execute("post_package", conanfile=conanfile)

    save(os.path.join(conanfile.package_folder, CONANINFO), conanfile.info.dumps())
    manifest = FileTreeManifest.create(conanfile.package_folder)
    manifest.save(conanfile.package_folder)

    package_output = ConanOutput(scope="%s package()" % scoped_output.scope)
    _report_files_from_manifest(package_output, manifest)
    scoped_output.success("Package '%s' created" % package_id)

    prev = manifest.summary_hash
    scoped_output.info("Created package revision %s" % prev)
    pref = PkgReference(ref, package_id)
    pref.revision = prev
    scoped_output.success("Full package reference: {}".format(pref.repr_notime()))
    return prev


def _report_files_from_manifest(scoped_output, manifest):
    copied_files = list(manifest.files())
    copied_files.remove(CONANINFO)

    if not copied_files:
        scoped_output.warning("No files in this package!")
        return

    report_files_copied(copied_files, scoped_output, message_suffix="Packaged")
