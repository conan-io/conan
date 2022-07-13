import os
import textwrap

from conans.test.utils.tools import TestClient


class TestCustomCommands:
    def test_simple_custom_command(self):
        mycommand = textwrap.dedent("""
            import json
            import os

            from conan.cli.output import cli_out_write
            from conan.cli.command import conan_command

            def output_mycommand_cli(info):
                return f"Conan cache folder is: {info.get('cache_folder')}"

            def output_mycommand_json(info):
                return json.dumps(info)

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
            from conan.cli.output import ConanOutput
            from conan.cli.command import conan_command

            @conan_command(group="custom commands")
            def hello(conan_api, parser, *args, **kwargs):
                '''
                My Hello doc
                '''
                ConanOutput().info("Hello {}!")
            """)
        mybye = textwrap.dedent("""
            from conan.cli.output import ConanOutput
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
                ConanOutput().info("Bye!")
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

            from conan.cli.output import cli_out_write
            from conan.cli.command import conan_command, conan_subcommand

            def output_cli(info):
                return f"{info.get('argument1')}"

            def output_json(info):
                return json.dumps(info)

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
