from conans.errors import conanfile_exception_formatter
from conans.util.files import chdir, mkdir


def run_build_method(conanfile, hook_manager, **hook_kwargs):
    mkdir(conanfile.build_folder)
    with chdir(conanfile.build_folder):
        hook_manager.execute("pre_build", conanfile=conanfile, **hook_kwargs)
        conanfile.output.highlight("Calling build()")
        with conanfile_exception_formatter(conanfile, "build"):
            conanfile.build()
        hook_manager.execute("post_build", conanfile=conanfile, **hook_kwargs)
