from parameterized import parameterized

from conan.internal.api.detect_api import _parse_gnu_libc, _parse_musl_libc


class TestDetectLibc:
    @parameterized.expand(
        [
            [
                """ldd (Debian GLIBC 2.36-9+rpt2+deb12u4) 2.36
Copyright (C) 2022 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Written by Roland McGrath and Ulrich Drepper.""",
                "2.36",
            ],
            [
                """ldd (Ubuntu GLIBC 2.35-0ubuntu3.6) 2.35
Copyright (C) 2022 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Written by Roland McGrath and Ulrich Drepper.""",
                "2.35",
            ],
            [
                """ldd (GNU libc) 2.38
Copyright (C) 2023 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Written by Roland McGrath and Ulrich Drepper.""",
                "2.38",
            ],
            [
                """musl libc (x86_64)
Version 1.2.4_git20230717
Dynamic Program Loader
Usage: /lib/ld-musl-x86_64.so.1 [options] [--] pathname""",
                None,
            ],
        ]
    )
    def test_parse_gnu_libc(self, ldd_output, expected_glibc_version):
        parsed_glibc_version = _parse_gnu_libc(ldd_output)
        assert expected_glibc_version == parsed_glibc_version

    @parameterized.expand(
        [
            [
                """musl libc (x86_64)
Version 1.2.4
Dynamic Program Loader
Usage: /lib/ld-musl-x86_64.so.1 [options] [--] pathname""",
                "1.2.4",
            ],
            [
                """musl libc (x86_64)
Version 1.2.4_git20230717
Dynamic Program Loader
Usage: /lib/ld-musl-x86_64.so.1 [options] [--] pathname""",
                "1.2.4_git20230717",
            ],
            [
                """ldd (Debian GLIBC 2.36-9+rpt2+deb12u4) 2.36
Copyright (C) 2022 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Written by Roland McGrath and Ulrich Drepper.""",
                None,
            ],
            [
                """ldd (GNU libc) 2.38
Copyright (C) 2023 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Written by Roland McGrath and Ulrich Drepper.""",
                None,
            ],
        ]
    )
    def test_parse_musl_libc(self, ldd_output, expected_musl_libc_version):
        parsed_musl_libc_version = _parse_musl_libc(ldd_output)
        assert expected_musl_libc_version == parsed_musl_libc_version
