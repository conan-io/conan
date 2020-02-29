

def to_android_abi(arch):
    """converts conan-style architecture into Android-NDK ABI"""
    return {'armv5': 'armeabi',
            'armv6': 'armeabi-v6',
            'armv7': 'armeabi-v7a',
            'armv7hf': 'armeabi-v7a',
            'armv8': 'arm64-v8a'}.get(str(arch), str(arch))
