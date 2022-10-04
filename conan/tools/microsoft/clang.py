
def is_clang_cl(conanfile, build_context=False):
    """ Validate if current compiler in settings is 'clang' and running on Windows
    :param conanfile: ConanFile instance
    :param build_context: If True, will use the settings from the build context, not host ones
    :return: True, if the host compiler is related to Clang on Windows, otherwise, False.
    """
    # FIXME: 2.0: remove "hasattr()" condition
    if not build_context or not hasattr(conanfile, "settings_build"):
        settings = conanfile.settings
    else:
        settings = conanfile.settings_build
    return (settings.get_safe("os") == "Windows" and settings.get_safe("compiler") == "clang") or \
        settings.get_safe("compiler.toolset") == "ClangCL"
