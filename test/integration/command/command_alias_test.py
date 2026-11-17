import json
import os
import textwrap

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


class TestCommandAlias:
    """ Tests for the CLI command alias system: a single plain-text "command_alias.conf" file in the
    Conan home that translates a CLI input into a real Conan command (+ its arguments), inspired
    by Git aliases. There is no command to manage it, it is just a file, meant to be edited
    directly or distributed via "conan config install"/"conan config install-pkg".
    Not to be confused with the legacy recipe 'alias' feature tested in 'alias_test.py'.
    """

    def test_alias_simple_command(self):
        c = TestClient()
        c.save_home({"command_alias.conf": "home = config home\n"})
        c.run("home")
        assert c.cache_folder in c.out

    def test_alias_with_extra_args(self):
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias.conf": "rem = remote\n"})
        c.run("rem list")
        assert "myremote" in c.out

    def test_alias_without_optional_arg_uses_command_default(self):
        # The "--format" argument of "remote list" is optional, defaulting to "text"
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias.conf": "rl = remote list\n"})
        c.run("rl")
        assert "myremote: https://fake.example.com" in c.out

    def test_alias_appends_user_args_after_alias_args(self):
        # The optional "--format" argument, not present in the alias itself, can still be
        # supplied by the user when invoking the alias
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias.conf": "myremotes = remote list\n"})
        c.run("myremotes --format=json")
        info = json.loads(c.stdout)
        assert info[0]["name"] == "myremote"

    def test_alias_definition_can_bake_in_an_optional_arg(self):
        # The optional "--force" argument can be baked into the alias itself, so the user does
        # not need to type it every time
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias.conf": "radd = remote add --force\n"})
        c.run("radd myremote https://updated.example.com")
        c.run("remote list")
        assert "myremote: https://updated.example.com" in c.out

    def test_alias_definition_with_optional_arg_containing_equals_sign(self):
        # The alias line is only split on its *first* "=" (name = command), so an optional
        # argument that itself contains "=", like "-cc core:non_interactive=True", is preserved
        c = TestClient()
        c.save_home({"command_alias.conf": "home2 = config home -cc core:non_interactive=True\n"})
        c.run("home2")
        assert c.cache_folder in c.out

    def test_alias_does_not_shadow_real_command(self):
        # A real command always takes precedence over any alias with the same name
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias.conf": "remote = list *\n"})
        c.run("remote list")
        assert "myremote" in c.out

    def test_alias_not_chained(self):
        # Aliases are only expanded once: an alias expanding to another alias name (instead of
        # a real command) is not resolved further
        c = TestClient()
        c.save_home({"command_alias.conf": textwrap.dedent("""\
            a1 = rem list
            rem = remote
            """)})
        c.run("a1", assert_error=True)
        assert "'rem' is not a Conan command" in c.out

    def test_alias_ignores_comments_and_malformed_lines(self):
        c = TestClient()
        c.save_home({"command_alias.conf": textwrap.dedent("""\
            # this is a comment
            just some text with no equal sign gets skipped by nobody matching it

            home = config home
            """)})
        c.run("home")
        assert c.cache_folder in c.out

    def test_alias_empty_command_errors(self):
        c = TestClient()
        c.save_home({"command_alias.conf": "home =\n"})
        c.run("home", assert_error=True)
        assert "Alias 'home' in" in c.out
        assert "is empty" in c.out

    def test_alias_shown_in_help(self):
        c = TestClient()
        c.save_home({"command_alias.conf": textwrap.dedent("""\
            ci = create . --build=missing
            ws = workspace
            """)})
        c.run("--help")
        assert "Alias commands" in c.out
        assert "ci" in c.out
        assert "create . --build=missing" in c.out
        assert "ws" in c.out
        assert "workspace" in c.out

    def test_no_alias_section_in_help_when_no_aliases_defined(self):
        c = TestClient()
        c.run("--help")
        assert "Alias commands" not in c.out

    def test_alias_distributed_via_config_install(self):
        source = temp_folder()
        c = TestClient()
        c.save({"command_alias.conf": "home = config home\n"}, path=source)
        c.run(f'config install "{source}"')
        installed = c.load(os.path.join(c.cache_folder, "command_alias.conf"))
        assert "home = config home" in installed

        c.run("home")
        assert c.cache_folder in c.out
