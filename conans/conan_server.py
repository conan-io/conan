import argparse

from conans.server.launcher import ServerLauncher


def run():
    parser = argparse.ArgumentParser(description='Launch the server')
    parser.add_argument('--migrate', default=False, action='store_true',
                        help='Run the pending migrations')
    args = parser.parse_args()
    launcher = ServerLauncher(force_migration=args.migrate)
    launcher.launch()


if __name__ == '__main__':
    run()
