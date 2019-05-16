# coding=utf-8

import unittest


class ClassicProtocExample(unittest.TestCase):
    """ There is an application that requires the protobuf library, and also
        build_requires the protoc executable to generate some files, but protoc
        also requires the protobuf library to build.

        Expected packages:
            * host_machine: application, protobuf
            * build_machine: protoc, protobuf
    """
    pass


class ProtocWithGTestExample(unittest.TestCase):
    """ On top of the 'ClassicProtocExample' test, now the application also
        build_requires gtest library to link a test program that is only run during
        the build stage, but it is not included in the package (tests are supposed to run
        in the host_machine).

        Expected packages:
            * host_machine: application, protobuf, application_test, gtest
            * build_machine: protoc, protobuf

        Challenge: we have a build_require (we don't want it to affect the ID) without a
        context change to the build_machine
    """
    pass


class ProtocToBuildAndDeploy(unittest.TestCase):
    """ This extends the idea of the 'ClassicProtocExample' where we also want the
        protoc to be deployed to the host_machine.

        Expected packages:
            * host_machine: application, protobuf, protoc
            * build_machine: protoc, protobuf

        Challenge: the package 'application' makes use of protoc with and without context change,
        here we have the standard build_require but also a ¿require? to protoc (the deployed one
        should affect the package ID)
    """
    pass
