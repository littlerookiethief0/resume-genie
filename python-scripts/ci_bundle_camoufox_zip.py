"""CI 专用：将 camoufox 用户缓存打成 camoufox_cache.zip（cwd 应为 python-scripts）。"""
import os
import shutil
import sys

import platformdirs


def main() -> int:
    p = platformdirs.user_cache_dir("camoufox").strip()
    if not os.path.isdir(p):
        print(f"::warning::camoufox cache not found at {p!r}", file=sys.stderr)
        return 0
    out_base = os.path.join(os.getcwd(), "camoufox_cache")
    shutil.make_archive(out_base, "zip", root_dir=p)
    zip_path = out_base + ".zip"
    print(f"Bundled {zip_path} from {p} ({os.path.getsize(zip_path)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
