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
        ['s390x', 's390x'],
        ['arm64', "armv8"]
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

    def test_solaris(self):
        with mock.patch("platform.machine", mock.MagicMock(return_value='sun4v')),\
                mock.patch("platform.processor", mock.MagicMock(return_value='sparc')),\
                mock.patch("platform.system", mock.MagicMock(return_value='SunOS')),\
                mock.patch("platform.architecture", mock.MagicMock(return_value=('64bit', 'ELF'))),\
                mock.patch("platform.release", mock.MagicMock(return_value='5.11')):
            self.assertEqual('sparcv9', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='i86pc')),\
                mock.patch("platform.processor", mock.MagicMock(return_value='i386')),\
                mock.patch("platform.system", mock.MagicMock(return_value='SunOS')),\
                mock.patch("platform.architecture", mock.MagicMock(return_value=('64bit', 'ELF'))),\
                mock.patch("platform.release", mock.MagicMock(return_value='5.11')):
            self.assertEqual('x86_64', detected_architecture())

    @parameterized.expand([
        ["E1C+", "e2k-v4"],
        ["E2C+", "e2k-v2"],
        ["E2C+DSP", "e2k-v2"],
        ["E2C3", "e2k-v6"],
        ["E2S", "e2k-v3"],
        ["E8C", "e2k-v4"],
        ["E8C2", "e2k-v5"],
        ["E12C", "e2k-v6"],
        ["E16C", "e2k-v6"],
        ["E32C", "e2k-v7"]
    ])
    def test_e2k(self, processor, expected_arch):
        with mock.patch("platform.machine", mock.MagicMock(return_value='e2k')), \
                mock.patch("platform.processor", mock.MagicMock(return_value=processor)):
            self.assertEqual(expected_arch, detected_architecture())
