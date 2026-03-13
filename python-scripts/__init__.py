from __future__ import annotations
import os
import sys

try:
    from .boss import BossCrawler
    from .zhilian import ZhilianCrawler
    from .liepin import LiepinCrawler
except ImportError:
    _scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from boss import BossCrawler
    from zhilian import ZhilianCrawler
    from liepin import LiepinCrawler

# 名字 -> 可调用(params, stop_event, on_step, on_data)
CRAWLER_REGISTRY = {
    "boss": lambda params, stop_event=None, on_step=None, on_data=None: BossCrawler(**params, stop_event=stop_event, on_step=on_step).start(),
    "zhilian": lambda params, stop_event=None, on_step=None, on_data=None: ZhilianCrawler(**params, stop_event=stop_event, on_step=on_step).start(),
    "liepin": lambda params, stop_event=None, on_step=None, on_data=None: LiepinCrawler(**params, stop_event=stop_event, on_step=on_step).start(),
}
