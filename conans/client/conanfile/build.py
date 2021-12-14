from conans.errors import conanfile_exception_formatter


def run_build_method(conanfile, hook_manager, **hook_kwargs):
    hook_manager.execute("pre_build", conanfile=conanfile, **hook_kwargs)
    conanfile.output.highlight("Calling build()")
    with conanfile_exception_formatter(conanfile, "build"):
        conanfile.build()
    hook_manager.execute("post_build", conanfile=conanfile, **hook_kwargs)
