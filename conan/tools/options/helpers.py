from conans.model.pkg_type import PackageType


def handle_common_config_options(conanfile):
    if conanfile.settings.get_safe("os") == "Windows":
        conanfile.options.rm_safe("fPIC")


def handle_common_configure_options(conanfile):
    if conanfile.options.get_safe("header_only"):
        conanfile.options.rm_safe("fPIC")
        conanfile.options.rm_safe("shared")
    elif conanfile.options.get_safe("shared"):
        conanfile.options.rm_safe("fPIC")


def handle_common_package_id_options(conanfile):
    if conanfile.options.get_safe("header_only") or conanfile.package_type == PackageType.HEADER:
        conanfile.info.clear()
