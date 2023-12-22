from conans.errors import conanfile_exception_formatter
from conans.util.files import chdir, mkdir


def run_build_method(conanfile, hook_manager):
    mkdir(conanfile.build_folder)
    mkdir(conanfile.package_metadata_folder)
    with chdir(conanfile.build_folder):
        hook_manager.execute("pre_build", conanfile=conanfile)
        if hasattr(conanfile, "build"):
            conanfile.output.highlight("Calling build()")
            with conanfile_exception_formatter(conanfile, "build"):
                try:
                    conanfile.build()
                except Exception:
                    hook_manager.execute("post_build_fail", conanfile=conanfile)
                    raise
        hook_manager.execute("post_build", conanfile=conanfile)
