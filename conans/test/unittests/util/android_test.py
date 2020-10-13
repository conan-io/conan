import unittest

from conans.client import tools


class AndroidTest(unittest.TestCase):
    def test_to_android_abi(self):
        self.assertEqual(tools.to_android_abi('x86'), 'x86')
        self.assertEqual(tools.to_android_abi('x86_64'), 'x86_64')
        self.assertEqual(tools.to_android_abi('armv5'), 'armeabi')
        self.assertEqual(tools.to_android_abi('armv5el'), 'armeabi')
        self.assertEqual(tools.to_android_abi('armv5hf'), 'armeabi')
        self.assertEqual(tools.to_android_abi('armv6'), 'armeabi-v6')
        self.assertEqual(tools.to_android_abi('armv7'), 'armeabi-v7a')
        self.assertEqual(tools.to_android_abi('armv7hf'), 'armeabi-v7a')
        self.assertEqual(tools.to_android_abi('armv8'), 'arm64-v8a')
        self.assertEqual(tools.to_android_abi('mips'), 'mips')
        self.assertEqual(tools.to_android_abi('mips64'), 'mips64')
