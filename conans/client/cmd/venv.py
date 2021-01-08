def cmd_venv(conanfile, cmd):
    conanfile.run(" ".join(cmd), run_environment=True)
