import json
import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.test.utils.env import environment_update


class TestCustomCommands:

    def test_import_error_custom_command(self):
        mycommand = textwrap.dedent("""
            import this_doesnt_exist
            """)

        client = TestClient()
        command_file_path = os.path.join(client.cache_folder, 'extensions',
                                         'commands', 'cmd_mycommand.py')
        client.save({f"{command_file_path}": mycommand})
        # Call to any other command, it will fail loading the custom command
        client.run("list *")
        assert "ERROR: Error loading custom command 'cmd_mycommand.py': " \
               "No module named 'this_doesnt_exist'" in client.out
        # But it won't break the whole conan and you can still use the rest of it
        client.run("config home")
        assert client.cache_folder in client.out

    def test_import_error_custom_command_subfolder(self):
        """
        used to break, this is handled differently in conan
        """
        mycommand = textwrap.dedent("""
            import this_doesnt_exist
            """)

        client = TestClient()
        command_file_path = os.path.join(client.cache_folder, 'extensions',
                                         'commands', 'mycompany', 'cmd_mycommand.py')
        client.save({f"{command_file_path}": mycommand})
        # Call to any other command, it will fail loading the custom command,
        client.run("list *")
        assert "ERROR: Error loading custom command mycompany.cmd_mycommand" in client.out
        # But it won't break the whole conan and you can still use the rest of it
        client.run("config home")
        assert client.cache_folder in client.out

    def test_simple_custom_command(self):
        mycommand = textwrap.dedent("""
            import json
            import os

            from conan.cli.command import conan_command
            from conan.api.output import cli_out_write

            def output_mycommand_cli(info):
                cli_out_write(f"Conan cache folder is: {info.get('cache_folder')}")

            def output_mycommand_json(info):
                cli_out_write(json.dumps(info))

            @conan_command(group="custom commands",
                           formatters={"cli": output_mycommand_cli,
                                       "json": output_mycommand_json})
            def mycommand(conan_api, parser, *args, **kwargs):
                \"""
                this is my custom command, it will print the location of the cache folder
                \"""
                info = {"cache_folder": os.path.basename(conan_api.cache_folder)}
                return info
            """)

        client = TestClient()
        command_file_path = os.path.join(client.cache_folder, 'extensions',
                                         'commands', 'cmd_mycommand.py')
        client.save({f"{command_file_path}": mycommand})
        client.run("mycommand -f cli")
        foldername = os.path.basename(client.cache_folder)
        assert f'Conan cache folder is: {foldername}' in client.out
        client.run("mycommand -f json")
        assert f'{{"cache_folder": "{foldername}"}}' in client.out

    def test_command_layer(self):
        myhello = textwrap.dedent("""
            from conan.api.output import cli_out_write
            from conan.cli.command import conan_command

            @conan_command(group="custom commands")
            def hello(conan_api, parser, *args, **kwargs):
                '''
                My Hello doc
                '''
                cli_out_write("Hello {}!")
            """)
        mybye = textwrap.dedent("""
            from conan.api.output import cli_out_write
            from conan.cli.command import conan_command, conan_subcommand

            @conan_command(group="custom commands")
            def bye(conan_api, parser, *args, **kwargs):
                '''
                My Bye doc
                '''

            @conan_subcommand()
            def bye_say(conan_api, parser, *args, **kwargs):
                '''
                My bye say doc
                '''
                cli_out_write("Bye!")
            """)

        client = TestClient()
        layer_path = os.path.join(client.cache_folder, 'extensions', 'commands')
        client.save({os.path.join(layer_path, 'cmd_hello.py'): myhello.format("world"),
                     os.path.join(layer_path, "greet", 'cmd_hello.py'): myhello.format("moon"),
                     os.path.join(layer_path, "greet", 'cmd_bye.py'): mybye})
        # Test that the root "hello" without subfolder still works and no conflict
        client.run("hello")
        assert "Hello world!" in client.out
        client.run("greet:hello")
        assert "Hello moon!" in client.out
        client.run("greet:bye say")
        assert "Bye!" in client.out
        client.run("-h")
        assert "greet:bye" in client.out

    def test_custom_command_with_subcommands(self):
        complex_command = textwrap.dedent("""
            import json

            from conan.cli.command import conan_command, conan_subcommand
            from conan.api.output import cli_out_write

            def output_cli(info):
                cli_out_write(f"{info.get('argument1')}")

            def output_json(info):
                 cli_out_write(json.dumps(info))

            @conan_subcommand(formatters={"cli": output_cli, "json": output_json})
            def complex_sub1(conan_api, parser, subparser, *args):
                \"""
                sub1 subcommand
                \"""
                subparser.add_argument("argument1", help="This is argument number 1")
                args = parser.parse_args(*args)
                info = {"argument1": args.argument1}
                return info

            @conan_command()
            def complex(conan_api, parser, *args, **kwargs):
                \"""
                this is a command with subcommands
                \"""
            """)

        client = TestClient()
        command_file_path = os.path.join(client.cache_folder, 'extensions',
                                         'commands', 'cmd_complex.py')
        client.save({f"{command_file_path}": complex_command})
        client.run("complex sub1 myargument -f=cli")
        assert "myargument" in client.out
        client.run("complex sub1 myargument -f json")
        assert f'{{"argument1": "myargument"}}' in client.out

    def test_custom_command_with_subcommands_with_underscore(self):
        complex_command = textwrap.dedent("""
            import json

            from conan.cli.command import conan_command, conan_subcommand
            from conan.api.output import cli_out_write

            @conan_command()
            def command_with_underscores(conan_api, parser, *args, **kwargs):
                \"""
                this is a command with subcommands
                \"""

            @conan_subcommand()
            def command_with_underscores_subcommand_with_underscores_too(conan_api, parser, subparser, *args):
                \"""
                sub1 subcommand
                \"""
                subparser.add_argument("argument1", help="This is argument number 1")
                args = parser.parse_args(*args)
                cli_out_write(args.argument1)
            """)

        client = TestClient()
        command_file_path = os.path.join(client.cache_folder, 'extensions',
                                         'commands', 'cmd_command_with_underscores.py')
        client.save({f"{command_file_path}": complex_command})
        client.run("command-with-underscores subcommand-with-underscores-too myargument")
        assert "myargument" in client.out

    def test_overwrite_builtin_command(self):
        complex_command = textwrap.dedent("""
            import json

            from conan.cli.command import conan_command
            from conan.api.output import cli_out_write

            @conan_command()
            def install(conan_api, parser, *args, **kwargs):
                \"""
                this is a command with subcommands
                \"""
                cli_out_write("Hello world")
            """)

        client = TestClient()
        command_file_path = os.path.join(client.cache_folder, 'extensions',
                                         'commands', 'myteam', 'cmd_install.py')
        client.save({f"{command_file_path}": complex_command})
        command_file_path = os.path.join(client.cache_folder, 'extensions',
                                         'commands', 'cmd_install.py')
        client.save({f"{command_file_path}": complex_command})
        client.run("myteam:install")
        assert "Hello world" in client.out
        client.run("install")
        assert "Hello world" in client.out

    def test_custom_command_local_import(self):
        mycode = textwrap.dedent("""
            from conan.api.output import cli_out_write


            def write_output(folder):
                cli_out_write(f"Conan cache folder from cmd_mycode: {folder}")
        """)
        mycommand = textwrap.dedent("""
            import os

            from conan.cli.command import conan_command
            from mycode import write_output


            @conan_command(group="custom commands")
            def mycommand(conan_api, parser, *args, **kwargs):
                \"""
                this is my custom command, it will print the location of the cache folder
                \"""
                folder = os.path.basename(conan_api.cache_folder)
                write_output(folder)
            """)

        client = TestClient()
        mycommand_file_path = os.path.join(client.cache_folder, 'extensions',
                                           'commands', 'danimtb', 'cmd_mycommand.py')
        mycode_file_path = os.path.join(client.cache_folder, 'extensions',
                                        'commands', 'danimtb', 'mycode.py')
        client.save({
            mycode_file_path: mycode,
            mycommand_file_path: mycommand
        })
        client.run("danimtb:mycommand")
        foldername = os.path.basename(client.cache_folder)
        assert f'Conan cache folder from cmd_mycode: {foldername}' in client.out

    def test_custom_command_from_other_location(self):
        """
        Tests that setting developer env variable ``_CONAN_INTERNAL_CUSTOM_COMMANDS_PATH``
        will append that folder to the Conan custom command default location.
        """
        myhello = textwrap.dedent("""
            from conan.api.output import cli_out_write
            from conan.cli.command import conan_command

            @conan_command(group="custom commands")
            def hello(conan_api, parser, *args, **kwargs):
                '''
                My Hello doc
                '''
                cli_out_write("Hello {}!")
            """)

        client = TestClient()
        my_local_layer_path = temp_folder(path_with_spaces=False)
        layer_path = os.path.join(client.cache_folder, 'extensions', 'commands')
        client.save({os.path.join(layer_path, 'cmd_hello.py'): myhello.format("world")})
        client.save({"cmd_hello.py": myhello.format("Overridden")}, path=my_local_layer_path)
        with environment_update({"_CONAN_INTERNAL_CUSTOM_COMMANDS_PATH": my_local_layer_path}):
            client.run("hello")
            # Local commands have preference over Conan custom ones if they collide
            assert "Hello Overridden!" in client.out
        # Without the variable it only loads the default custom commands location
        client.run("hello")
        assert "Hello world!" in client.out


class TestCommandAPI:
    @pytest.mark.parametrize("argument", ['["list", "pkg*", "-c"]',
                                          '"list pkg* -c"'])
    def test_command_reuse_interface(self, argument):
        mycommand = textwrap.dedent(f"""
            import json
            from conan.cli.command import conan_command
            from conan.api.output import cli_out_write

            @conan_command(group="custom commands")
            def mycommand(conan_api, parser, *args, **kwargs):
                \""" mycommand help \"""
                result = conan_api.command.run({argument})
                cli_out_write(json.dumps(result["results"], indent=2))
            """)

        c = TestClient()
        command_file_path = os.path.join(c.cache_folder, 'extensions',
                                         'commands', 'cmd_mycommand.py')
        c.save({f"{command_file_path}": mycommand})
        c.run("mycommand", redirect_stdout="file.json")
        assert json.loads(c.load("file.json")) == {"Local Cache": {}}

    def test_command_reuse_other_custom(self):
        cmd1 = textwrap.dedent(f"""
            from conan.cli.command import conan_command
            from conan.api.output import cli_out_write

            @conan_command(group="custom commands")
            def mycmd1(conan_api, parser, *args, **kwargs):
                \"""mycommand help \"""
                # result = conan_api.command.run("")
                cli_out_write("MYCMD1!!!!!")
                conan_api.command.run("mycmd2")
            """)
        cmd2 = textwrap.dedent(f"""
            from conan.cli.command import conan_command
            from conan.api.output import cli_out_write

            @conan_command(group="custom commands")
            def mycmd2(conan_api, parser, *args, **kwargs):
                \"""mycommand help\"""
                cli_out_write("MYCMD2!!!!!")
            """)

        c = TestClient()
        cmds = os.path.join(c.cache_folder, 'extensions', 'commands')
        c.save({os.path.join(cmds, "cmd_mycmd1.py"): cmd1,
                os.path.join(cmds, "cmd_mycmd2.py"): cmd2})
        c.run("mycmd1")
        assert "MYCMD1!!!!!" in c.out
        assert "MYCMD2!!!!!" in c.out

    def test_command_reuse_interface_create(self):
        mycommand = textwrap.dedent("""
            import json
            from conan.cli.command import conan_command
            from conan.cli.formatters.graph import format_graph_json

            @conan_command(group="custom commands", formatters={"json": format_graph_json})
            def mycommand(conan_api, parser, *args, **kwargs):
                \""" mycommand help \"""
                result = conan_api.command.run(["create", ".", "--version=1.0.0"])
                return result
            """)

        c = TestClient()
        command_file_path = os.path.join(c.cache_folder, 'extensions',
                                         'commands', 'cmd_mycommand.py')
        c.save({f"{command_file_path}": mycommand,
                "conanfile.py": GenConanfile("mylib")})
        c.run("mycommand --format=json", redirect_stdout="file.json")
        create_output = json.loads(c.load("file.json"))
        assert create_output['graph']['nodes']['1']['label'] == "mylib/1.0.0"

    def test_subcommand_reuse_interface(self):
        mycommand = textwrap.dedent("""
            import json
            from conan.cli.command import conan_command
            from conan.api.output import cli_out_write

            @conan_command(group="custom commands")
            def mycommand(conan_api, parser, *args, **kwargs):
                \""" mycommand help \"""
                parser.add_argument("remote", help="remote")
                parser.add_argument("url", help="url")
                args = parser.parse_args(*args)
                conan_api.command.run(["remote", "add", args.remote, args.url])
                result = conan_api.command.run(["remote", "list"])
                result = {r.name: r.url for r in result}
                cli_out_write(json.dumps(result, indent=2))
            """)

        c = TestClient()
        command_file_path = os.path.join(c.cache_folder, 'extensions',
                                         'commands', 'cmd_mycommand.py')
        c.save({f"{command_file_path}": mycommand})
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("export .")
        c.run("mycommand myremote myurl")
        assert json.loads(c.stdout) == {"myremote": "myurl"}
