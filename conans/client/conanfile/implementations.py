from conans.model.pkg_type import PackageType


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


def auto_language(conanfile):
    if not conanfile.languages:
        conanfile.settings.rm_safe("compiler.cstd")
        return
    if "C" not in conanfile.languages:
        conanfile.settings.rm_safe("compiler.cstd")
    if "C++" not in conanfile.languages:
        conanfile.settings.rm_safe("compiler.cppstd")
        conanfile.settings.rm_safe("compiler.libcxx")
