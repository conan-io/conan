from enum import Enum

from conans.errors import ConanException


class PackageType(Enum):
    LIBRARY = "library"  # abstract type, should contain shared option to define
    STATIC = "static library"
    SHARED = "shared library"
    HEADER = "header library"
    RUN = "run library"  # plugin-like, shared lib without headers
    APP = "application"
    UNKNOWN = "unknown"

    @staticmethod
    def from_conanfile(conanfile):
        # This doesnt implement the header_only option without shared one. Users should define
        # their package_type as they wish in the configure() method
        conanfile_type = conanfile.package_type
        if conanfile_type is not None:
            conanfile_type = PackageType(conanfile_type)

        if conanfile_type is None:  # automatic default detection with option shared/header-only
            try:
                shared = conanfile.options.shared
            except ConanException:
                pass
            else:
                if shared is not None:
                    if shared:
                        return PackageType.SHARED
                    else:
                        try:
                            header = conanfile.options.header_only
                        except ConanException:
                            pass
                        else:
                            if header:
                                return PackageType.HEADER
                        return PackageType.STATIC
            return PackageType.UNKNOWN

        if conanfile_type is PackageType.LIBRARY:
            try:
                shared = conanfile.options.shared  # MUST exist
            except ConanException:
                raise ConanException("Package type is 'library', but no 'shared' option declared")
            if shared:
                return PackageType.SHARED
            else:
                try:
                    header = conanfile.options.header_only
                except ConanException:
                    pass
                else:
                    if header:
                        return PackageType.HEADER
                return PackageType.STATIC

        return conanfile_type
