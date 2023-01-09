from conan.errors import ConanException


def android_abi(conanfile, context="host"):
    """
    Returns Android-NDK ABI
    :param conanfile: ConanFile instance
    :param context: either "host", "build" or "target"
    :return: Android-NDK ABI
    """
    if context not in ["host", "build", "target"]:
        raise ConanException("context argument must be either 'host', 'build' or 'target'")

    settings = getattr(conanfile, f"settings_{context}", conanfile.settings)
    arch = settings.get_safe("arch")
    # https://cmake.org/cmake/help/latest/variable/CMAKE_ANDROID_ARCH_ABI.html
    return {
        "armv5el": "armeabi",
        "armv5hf": "armeabi",
        "armv5": "armeabi",
        "armv6": "armeabi-v6",
        "armv7": "armeabi-v7a",
        "armv7hf": "armeabi-v7a",
        "armv8": "arm64-v8a",
    }.get(arch, arch)
