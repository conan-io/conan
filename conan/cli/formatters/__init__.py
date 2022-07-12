from jinja2 import Environment, select_autoescape, FileSystemLoader, ChoiceLoader

from conans.assets.templates import dict_loader


def get_template(template_name, template_folder=None):
    # TODO: It can be initialized only once together with the Conan app
    loaders = [dict_loader]
    if template_folder:
        loaders.insert(0, FileSystemLoader(template_folder))
    env = Environment(loader=ChoiceLoader(loaders),
                      autoescape=select_autoescape(['html', 'xml']))
    return env.get_template(template_name)
