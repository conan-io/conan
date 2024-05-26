tools_locations = {
    'cmake': {
        "default": "3.25",
        "3.25": {},
        "3.23": {"path": {'Windows': r'C:\ws\cmake\cmake-3.23.1-windows-x86_64\bin'}}
    },
    'ninja': {
        "1.10.2": {"path": {'Windows': 'C:/ws/ninja/ninja1.10.2'}}
    },
    'msys2': {
        "platform": "Windows",
        "default": "system",
        "exe": "make",
        "system": {"path": {'Windows': "C:/ws/msys64/usr/bin"}},
    },
    'mingw64': {
        "platform": "Windows",
        "default": "system",
        "exe": "mingw32-make",
        "system": {"path": {'Windows': "C:/ws/msys64/mingw64/bin"}},
    },
    "clang": {
        "13": {"path": {'Windows': r'C:/ws/LLVM/clang13/bin'}},
        "16": {"path": {'Windows': r'C:/ws/LLVM/clang16/bin'}},
        "disabled": False
    },
    'visual_studio': {"default": "15",
                      "15": {},
                      "16": {"disabled": False},
                      "17": {}},
    'msys2_clang64': {
        "disabled": False,
        "platform": "Windows",
        "default": "system",
        "exe": "clang",
        "system": {"path": {'Windows': "C:/ws/msys64/clang64/bin"}},
    },
    'msys2_mingw64_clang64': {
        "disabled": False,
        "platform": "Windows",
        "default": "system",
        "exe": "clang",
        "system": {"path": {'Windows': "C:/ws/msys64/mingw64/bin"}},
    },
}
