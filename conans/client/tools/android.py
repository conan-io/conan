

def to_android_abi(arch):
    """converts conan-style architecture into Android-NDK ABI"""
    # https://cmake.org/cmake/help/latest/variable/CMAKE_ANDROID_ARCH_ABI.html
    return {'armv5el': 'armeabi',
            'armv5hf': 'armeabi',
            'armv5': 'armeabi',
            'armv6': 'armeabi-v6',
            'armv7': 'armeabi-v7a',
            'armv7hf': 'armeabi-v7a',
            'armv8': 'arm64-v8a'}.get(str(arch), str(arch))
