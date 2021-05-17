import os


class DepsCppCmake(object):

    def __init__(self, cpp_info, pfolder_var_name):

        def join_paths(paths):
            """
            Paths are doubled quoted, and escaped (but spaces)
            e.g: set(LIBFOO_INCLUDE_DIRS "/path/to/included/dir" "/path/to/included/dir2")
            """
            ret = []
            for p in paths:
                norm_path = p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
                if os.path.isabs(p):
                    ret.append('"{}"'.format(norm_path))
                else:
                    # Prepend the {{ pkg_name }}_PACKAGE_FOLDER{{ config_suffix }}
                    ret.append('"${%s}/%s"' % (pfolder_var_name, norm_path))
            return "\n\t\t\t".join(ret)

        def join_flags(separator, values):
            # Flags have to be escaped
            return separator.join(v.replace('\\', '\\\\').replace('$', '\\$').replace('"', '\\"')
                                  for v in values)

        def join_defines(values, prefix=""):
            # Defines have to be escaped, included spaces
            return "\n\t\t\t".join('"%s%s"' % (prefix, v.replace('\\', '\\\\').replace('$', '\\$').
                                   replace('"', '\\"'))
                                   for v in values)

        def join_paths_single_var(values):
            """
            semicolon-separated list of dirs:
            e.g: set(LIBFOO_INCLUDE_DIR "/path/to/included/dir;/path/to/included/dir2")
            """
            return '"%s"' % ";".join(p.replace('\\', '/').replace('$', '\\$') for p in values)

        self.include_paths = join_paths(cpp_info.includedirs)
        self.include_path = join_paths_single_var(cpp_info.includedirs)
        self.lib_paths = join_paths(cpp_info.libdirs)
        self.res_paths = join_paths(cpp_info.resdirs)
        self.bin_paths = join_paths(cpp_info.bindirs)
        self.build_paths = join_paths(cpp_info.builddirs)
        self.src_paths = join_paths(cpp_info.srcdirs)
        self.framework_paths = join_paths(cpp_info.frameworkdirs)
        self.libs = join_flags(" ", cpp_info.libs)
        self.system_libs = join_flags(" ", cpp_info.system_libs)
        self.frameworks = join_flags(" ", cpp_info.frameworks)
        self.defines = join_defines(cpp_info.defines, "-D")
        self.compile_definitions = join_defines(cpp_info.defines)

        # For modern CMake targets we need to prepare a list to not
        # loose the elements in the list by replacing " " with ";". Example "-framework Foundation"
        # Issue: #1251
        self.cxxflags_list = join_flags(";", cpp_info.cxxflags)
        self.cflags_list = join_flags(";", cpp_info.cflags)

        # linker flags without magic: trying to mess with - and / =>
        # https://github.com/conan-io/conan/issues/8811
        # frameworks should be declared with cppinfo.frameworks not "-framework Foundation"
        self.sharedlinkflags_list = join_flags(";", cpp_info.sharedlinkflags)
        self.exelinkflags_list = join_flags(";", cpp_info.exelinkflags)

        build_modules = cpp_info.get_property("cmake_build_modules", "CMakeDeps") or []
        self.build_modules_paths = join_paths(build_modules)

