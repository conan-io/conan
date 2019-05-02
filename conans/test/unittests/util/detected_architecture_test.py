#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4


import mock
import unittest

from parameterized import parameterized

from conans.client.tools.oss import detected_architecture

class DetectedArchitectureTest(unittest.TestCase):

    @parameterized.expand([
        ['i386', 'x86'],
        ['i686', 'x86'],
        ['x86_64', 'x86_64'],
        ['amd64', 'x86_64'],
        ['aarch64_be', 'armv8'],
        ['armv8b', 'armv8'],
        ['armv7l', 'armv7'],
        ['armv6l', 'armv6'],
        ['arm', 'armv6'],
        ['ppc64le', 'ppc64le'],
        ['ppc64', 'ppc64'],
        ['mips', 'mips'],
        ['mips64', 'mips64'],
        ['sparc', 'sparc'],
        ['sparc64', 'sparcv9'],
        ['s390', 's390'],
        ['s390x', 's390x']
    ])
    def test_various(self, mocked_machine, expected_arch):

        with mock.patch("platform.machine", mock.MagicMock(return_value=mocked_machine)):
            self.assertEqual(expected_arch, detected_architecture(), "given '%s' expected '%s'" % (mocked_machine, expected_arch))


    def test_aix(self):
        with mock.patch("platform.machine", mock.MagicMock(return_value='00FB91F44C00')),\
                mock.patch("platform.processor", mock.MagicMock(return_value='powerpc')),\
                mock.patch("platform.system", mock.MagicMock(return_value='AIX')),\
                mock.patch("conans.client.tools.oss.OSInfo.get_aix_conf", mock.MagicMock(return_value='32')),\
                mock.patch('subprocess.check_output', mock.MagicMock(return_value='7.1.0.0')):
            self.assertEqual('ppc32', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='00FB91F44C00')),\
                mock.patch("platform.processor", mock.MagicMock(return_value='powerpc')),\
                mock.patch("platform.system", mock.MagicMock(return_value='AIX')),\
                mock.patch("conans.client.tools.oss.OSInfo.get_aix_conf", mock.MagicMock(return_value='64')),\
                mock.patch('subprocess.check_output', mock.MagicMock(return_value='7.1.0.0')):
            self.assertEqual('ppc64', detected_architecture())
