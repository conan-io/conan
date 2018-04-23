#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from conans import tools


class WindowsSubsystemTest(unittest.TestCase):

    def detect_windows_subsystem_not_raise_test(self):
        if not tools.which("bash"):
            result = tools.os_info.detect_windows_subsystem()
            self.assertEqual(None, result)