import os
import shutil


def copy_assets(src_folder, dst_folder, assets=None):
    assets_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "files")
    if src_folder:
        src_folder = os.path.join(assets_path, src_folder)
    assets = assets or os.listdir(src_folder)
    for asset in assets:
        s = os.path.join(src_folder, asset)
        d = os.path.join(dst_folder, asset)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
