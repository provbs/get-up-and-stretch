"""exe 빌드: .venv\\Scripts\\python.exe build.py  → dist\\GetUpAndStretch.exe"""
import os

import PyInstaller.__main__

from main import make_icon

HERE = os.path.dirname(os.path.abspath(__file__))
ICO = os.path.join(HERE, "icon.ico")

make_icon(256).save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

PyInstaller.__main__.run([
    os.path.join(HERE, "main.py"),
    "--name=GetUpAndStretch",
    "--onefile",
    "--windowed",
    "--noconfirm",
    f"--icon={ICO}",
    "--hidden-import=pystray._win32",
    f"--distpath={os.path.join(HERE, 'dist')}",
    f"--workpath={os.path.join(HERE, 'build')}",
    f"--specpath={HERE}",
])
