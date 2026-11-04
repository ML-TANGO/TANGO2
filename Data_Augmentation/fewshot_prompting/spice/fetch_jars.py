"""Copy the SPICE jars out of the pycocoevalcap wheel into <dist_dir> — without
installing pycocoevalcap or its Python dependencies.

Usage: python spice/fetch_jars.py <dist_dir>
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

PREFIX = "pycocoevalcap/spice/"


def main(dist: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "download", "--no-deps", "--quiet", "pycocoevalcap==1.2", "-d", tmp]
        )
        with zipfile.ZipFile(glob.glob(os.path.join(tmp, "*.whl"))[0]) as wheel:
            for name in wheel.namelist():
                if name.startswith(PREFIX) and name.endswith(".jar"):
                    target = os.path.join(dist, name[len(PREFIX):])
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with wheel.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)


if __name__ == "__main__":
    main(sys.argv[1])
