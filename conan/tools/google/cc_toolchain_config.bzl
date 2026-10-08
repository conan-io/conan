load("@rules_cc//cc:action_names.bzl", "ACTION_NAMES")
load(
    "@rules_cc//cc:cc_toolchain_config_lib.bzl",
    "action_config",
    "feature",
    "flag_group",
    "flag_set",
    "tool",
    "tool_path",
    "variable_with_value",
)
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/toolchains:cc_toolchain_config_info.bzl", "CcToolchainConfigInfo")

_COMPILE = [
    ACTION_NAMES.c_compile,
    ACTION_NAMES.cpp_compile,
    ACTION_NAMES.assemble,
]
_LINK = [
    ACTION_NAMES.cpp_link_executable,
    ACTION_NAMES.cpp_link_dynamic_library,
    ACTION_NAMES.cpp_link_nodeps_dynamic_library,
]
_TOOL_PATH_NAMES = ["gcc", "ld", "ar", "cpp", "nm", "objdump", "objcopy", "strip", "gcov"]

def _action(name, path, implies = None):
    return action_config(
        action_name = name,
        enabled = True,
        tools = [tool(path = path)],
        implies = implies or [],
    )

def _flags_feature(name, actions, flags):
    return feature(
        name = name,
        enabled = True,
        flag_sets = [flag_set(
            actions = actions,
            flag_groups = [flag_group(flags = flags)],
        )],
    )

def _impl(ctx):
    features = [
        feature(name = "supports_pic", enabled = True),
        feature(name = "supports_dynamic_linker", enabled = True),
        feature(
            name = "opt",
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(flags = ["-O2", "-DNDEBUG"])],
            )],
        ),
        feature(
            name = "dbg",
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(flags = ["-g"])],
            )],
        ),
        feature(name = "fastbuild"),
        feature(
            name = "sysroot",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE + _LINK,
                flag_groups = [flag_group(
                    flags = ["--sysroot=%{sysroot}"],
                    expand_if_available = "sysroot",
                )],
            )],
        ),
        feature(
            name = "include_paths",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [
                    flag_group(
                        flags = ["-iquote", "%{quote_include_paths}"],
                        iterate_over = "quote_include_paths",
                    ),
                    flag_group(
                        flags = ["-I%{include_paths}"],
                        iterate_over = "include_paths",
                    ),
                    flag_group(
                        flags = ["-isystem", "%{system_include_paths}"],
                        iterate_over = "system_include_paths",
                    ),
                ],
            )],
        ),
        feature(
            name = "preprocessor_defines",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(
                    flags = ["-D%{preprocessor_defines}"],
                    iterate_over = "preprocessor_defines",
                )],
            )],
        ),
        feature(
            name = "pic",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(
                    flags = ["-fPIC"],
                    expand_if_available = "pic",
                )],
            )],
        ),
        feature(
            name = "dependency_file",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(
                    flags = ["-MD", "-MF", "%{dependency_file}"],
                    expand_if_available = "dependency_file",
                )],
            )],
        ),
        feature(
            name = "user_compile_flags",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(
                    flags = ["%{user_compile_flags}"],
                    iterate_over = "user_compile_flags",
                    expand_if_available = "user_compile_flags",
                )],
            )],
        ),
    ]
    if ctx.attr.compile_flags:
        features.append(_flags_feature("conan_compile_flags", _COMPILE, ctx.attr.compile_flags))
    features.extend([
        feature(
            name = "compiler_input_flags",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(
                    flags = ["-c", "%{source_file}"],
                    expand_if_available = "source_file",
                )],
            )],
        ),
        feature(
            name = "compiler_output_flags",
            enabled = True,
            flag_sets = [flag_set(
                actions = _COMPILE,
                flag_groups = [flag_group(
                    flags = ["-o", "%{output_file}"],
                    expand_if_available = "output_file",
                )],
            )],
        ),
        feature(
            name = "shared_flag",
            enabled = True,
            flag_sets = [flag_set(
                actions = [
                    ACTION_NAMES.cpp_link_dynamic_library,
                    ACTION_NAMES.cpp_link_nodeps_dynamic_library,
                ],
                flag_groups = [flag_group(flags = ["-shared"])],
            )],
        ),
        feature(
            name = "library_search_directories",
            enabled = True,
            flag_sets = [flag_set(
                actions = _LINK,
                flag_groups = [flag_group(
                    flags = ["-L%{library_search_directories}"],
                    iterate_over = "library_search_directories",
                    expand_if_available = "library_search_directories",
                )],
            )],
        ),
        feature(
            name = "libraries_to_link",
            enabled = True,
            flag_sets = [flag_set(
                actions = _LINK,
                flag_groups = [flag_group(
                    iterate_over = "libraries_to_link",
                    flag_groups = [
                        flag_group(
                            flags = ["-Wl,--start-lib"],
                            expand_if_equal = variable_with_value("libraries_to_link.type", "object_file_group"),
                        ),
                        flag_group(
                            flags = ["%{libraries_to_link.object_files}"],
                            iterate_over = "libraries_to_link.object_files",
                            expand_if_equal = variable_with_value("libraries_to_link.type", "object_file_group"),
                        ),
                        flag_group(
                            flags = ["-Wl,--end-lib"],
                            expand_if_equal = variable_with_value("libraries_to_link.type", "object_file_group"),
                        ),
                        flag_group(
                            flags = ["%{libraries_to_link.name}"],
                            expand_if_equal = variable_with_value("libraries_to_link.type", "object_file"),
                        ),
                        flag_group(
                            flags = ["%{libraries_to_link.name}"],
                            expand_if_equal = variable_with_value("libraries_to_link.type", "static_library"),
                        ),
                        flag_group(
                            flags = ["-l%{libraries_to_link.name}"],
                            expand_if_equal = variable_with_value("libraries_to_link.type", "dynamic_library"),
                        ),
                    ],
                    expand_if_available = "libraries_to_link",
                )],
            )],
        ),
        feature(
            name = "user_link_flags",
            enabled = True,
            flag_sets = [flag_set(
                actions = _LINK,
                flag_groups = [flag_group(
                    flags = ["%{user_link_flags}"],
                    iterate_over = "user_link_flags",
                    expand_if_available = "user_link_flags",
                )],
            )],
        ),
        feature(
            name = "runtime_library_search_directories",
            enabled = True,
            flag_sets = [flag_set(
                actions = _LINK,
                flag_groups = [flag_group(
                    iterate_over = "runtime_library_search_directories",
                    flag_groups = [flag_group(flags = [
                        "-Wl,-rpath,$ORIGIN/%{runtime_library_search_directories}",
                    ])],
                    expand_if_available = "runtime_library_search_directories",
                )],
            )],
        ),
    ])
    if ctx.attr.link_flags:
        features.append(_flags_feature("conan_link_flags", _LINK, ctx.attr.link_flags))
    features.extend([
        feature(
            name = "output_execpath_flags",
            enabled = True,
            flag_sets = [flag_set(
                actions = _LINK,
                flag_groups = [flag_group(
                    flags = ["-o", "%{output_execpath}"],
                    expand_if_available = "output_execpath",
                )],
            )],
        ),
        feature(
            name = "archiver_flags",
            enabled = True,
            flag_sets = [
                flag_set(
                    actions = [ACTION_NAMES.cpp_link_static_library],
                    flag_groups = [flag_group(
                        flags = ["rcs", "%{output_execpath}"],
                        expand_if_available = "output_execpath",
                    )],
                ),
                flag_set(
                    actions = [ACTION_NAMES.cpp_link_static_library],
                    flag_groups = [flag_group(
                        iterate_over = "libraries_to_link",
                        flag_groups = [
                            flag_group(
                                flags = ["%{libraries_to_link.name}"],
                                expand_if_equal = variable_with_value("libraries_to_link.type", "object_file"),
                            ),
                            flag_group(
                                flags = ["%{libraries_to_link.object_files}"],
                                iterate_over = "libraries_to_link.object_files",
                                expand_if_equal = variable_with_value("libraries_to_link.type", "object_file_group"),
                            ),
                        ],
                    )],
                ),
            ],
        ),
    ])
    return cc_common.create_cc_toolchain_config_info(
        ctx = ctx,
        features = features,
        action_configs = [
            _action(ACTION_NAMES.c_compile, ctx.attr.c_compiler),
            _action(ACTION_NAMES.cpp_compile, ctx.attr.cxx_compiler),
            _action(ACTION_NAMES.assemble, ctx.attr.c_compiler),
            _action(ACTION_NAMES.cpp_link_executable, ctx.attr.c_compiler),
            _action(ACTION_NAMES.cpp_link_dynamic_library, ctx.attr.c_compiler),
            _action(ACTION_NAMES.cpp_link_nodeps_dynamic_library, ctx.attr.c_compiler),
            _action(ACTION_NAMES.cpp_link_static_library, ctx.attr.archiver, ["archiver_flags"]),
        ],
        cxx_builtin_include_directories = ctx.attr.cxx_builtin_include_directories,
        toolchain_identifier = "conan_gcc",
        host_system_name = "local",
        target_system_name = "local",
        target_cpu = ctx.attr.target_cpu,
        target_libc = "glibc",
        compiler = "gcc",
        abi_version = "gcc",
        abi_libc_version = "glibc",
        tool_paths = [
            tool_path(name = name, path = ctx.attr.tool_paths[name])
            for name in _TOOL_PATH_NAMES
        ],
        builtin_sysroot = ctx.attr.sysroot or None,
    )

cc_toolchain_config = rule(
    implementation = _impl,
    attrs = {
        "c_compiler": attr.string(mandatory = True),
        "cxx_compiler": attr.string(mandatory = True),
        "archiver": attr.string(mandatory = True),
        "tool_paths": attr.string_dict(mandatory = True),
        "cxx_builtin_include_directories": attr.string_list(),
        "sysroot": attr.string(),
        "compile_flags": attr.string_list(),
        "link_flags": attr.string_list(),
        "target_cpu": attr.string(mandatory = True),
    },
    provides = [CcToolchainConfigInfo],
)
