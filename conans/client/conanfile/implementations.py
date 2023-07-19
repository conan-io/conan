import inspect

from conans.model.pkg_type import PackageType


def call(module, implementation_name, conanfile_method, *args, **kwargs):
    # first check that we have at least one function in the module that starts
    # with the implementation name, then, when calling to the function name composed
    # with the conanfile_method name we pass on the exception
    def _has_function_starting_with(module, prefix):
        function_names = [name for name, _ in inspect.getmembers(module, inspect.isfunction)]
        for name in function_names:
            if name.startswith(prefix):
                return True
        return False

    if not _has_function_starting_with(module, implementation_name):
        raise Exception(f"'{implementation_name}' is not a valid 'implements' value.")

    implementation_function_name = f"{implementation_name}_{conanfile_method}"
    try:
        implementation_function = getattr(module, implementation_function_name)
        return implementation_function(*args, **kwargs)
    except AttributeError:
        pass


def auto_shared_fpic_config_options(conanfile):
    if conanfile.settings.get_safe("os") == "Windows":
        conanfile.options.rm_safe("fPIC")


def auto_shared_fpic_configure(conanfile):
    if conanfile.options.get_safe("header_only"):
        conanfile.options.rm_safe("fPIC")
        conanfile.options.rm_safe("shared")
    elif conanfile.options.get_safe("shared"):
        conanfile.options.rm_safe("fPIC")


def auto_header_only_package_id(conanfile):
    if conanfile.options.get_safe("header_only") or conanfile.package_type is PackageType.HEADER:
        conanfile.info.clear()
