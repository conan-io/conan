import platform


def check_binary(t):
    # FIXME: Some values are hardcoded to match the CI setup
    host_arch = t.get_default_host_profile().settings['arch']
    arch_macro = {
        "gcc": {"armv8": "__aarch64__", "x86_64": "__x86_64__"},
        "msvc": {"armv8": "_M_ARM64", "x86_64": "_M_X64"}
    }
    if platform.system() == "Darwin":
        assert f"main {arch_macro['gcc'][host_arch]} defined" in t.out
        assert "main __apple_build_version__" in t.out
        assert "main __clang_major__17" in t.out
        # TODO: check why __clang_minor__ seems to be not defined in XCode 12
        # commented while migrating to XCode12 CI
        # assert ("main __clang_minor__0" in t.out
    elif platform.system() == "Windows":
        assert f"main {arch_macro['msvc'][host_arch]} defined" in t.out
        assert "main _MSC_VER19" in t.out
        assert "main _MSVC_LANG2014" in t.out
    elif platform.system() == "Linux":
        assert f"main {arch_macro['gcc'][host_arch]} defined" in t.out
        assert "main __GNUC__9" in t.out
