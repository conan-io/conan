#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4


import unittest
from mock import mock
from conans.tools import detected_architecture


class DetectedArchitectureTest(unittest.TestCase):

    def test_various(self):

        # x86
        with mock.patch("platform.machine", mock.MagicMock(return_value='i386')):
            self.assertEqual('x86', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='i686')):
            self.assertEqual('x86', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='x86_64')):
            self.assertEqual('x86_64', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='amd64')):
            self.assertEqual('x86_64', detected_architecture())

        # ARM
        with mock.patch("platform.machine", mock.MagicMock(return_value='aarch64_be')):
            self.assertEqual('armv8', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='armv8b')):
            self.assertEqual('armv8', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='armv7l')):
            self.assertEqual('armv7', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='armv6l')):
            self.assertEqual('armv6', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='arm')):
            self.assertEqual('armv6', detected_architecture())

        # PowerPC
        with mock.patch("platform.machine", mock.MagicMock(return_value='ppc64le')):
            self.assertEqual('ppc64le', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='ppc64')):
            self.assertEqual('ppc64', detected_architecture())

        # MIPS
        with mock.patch("platform.machine", mock.MagicMock(return_value='mips')):
            self.assertEqual('mips', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='mips64')):
            self.assertEqual('mips64', detected_architecture())

        # SPARC
        with mock.patch("platform.machine", mock.MagicMock(return_value='sparc')):
            self.assertEqual('sparc', detected_architecture())

        with mock.patch("platform.machine", mock.MagicMock(return_value='sparc64')):
            self.assertEqual('sparcv9', detected_architecture())
