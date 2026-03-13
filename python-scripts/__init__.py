from __future__ import annotations
import os
import sys

try:
    from .boss import BossCrawler
    from .boss_resume import BossCrawler as BossResumeCrawler
    from .zhilian import ZhilianCrawler
    from .zhilian_resume import ZhilianResumeCrawler
    from .liepin import LiepinCrawler
    from .liepin_resume import LiepinResumeCrawler
except ImportError:
    _scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from boss import BossCrawler
    from boss_resume import BossCrawler as BossResumeCrawler
    from zhilian import ZhilianCrawler
    from zhilian_resume import ZhilianResumeCrawler
    from liepin import LiepinCrawler
    from liepin_resume import LiepinResumeCrawler

# 名字 -> 可调用(params, stop_event)：在这里写「传参并调用类」
CRAWLER_REGISTRY = {
    "boss": lambda params, stop_event=None, on_step=None, on_data=None: BossCrawler(**params, stop_event=stop_event, on_step=on_step).start(),
    "boss_parse": lambda params, stop_event=None, on_step=None, on_data=None: BossResumeCrawler(**params, stop_event=stop_event, on_data=on_data).start(),
    "zhilian": lambda params, stop_event=None, on_step=None, on_data=None: ZhilianCrawler(**params, stop_event=stop_event, on_step=on_step).start(),
    "zhilian_parse": lambda params, stop_event=None, on_step=None, on_data=None: ZhilianResumeCrawler(**params, stop_event=stop_event, on_data=on_data).start(),
    "liepin": lambda params, stop_event=None, on_step=None, on_data=None: LiepinCrawler(**params, stop_event=stop_event, on_step=on_step).start(),
    "liepin_parse": lambda params, stop_event=None, on_step=None, on_data=None: LiepinResumeCrawler(**params, stop_event=stop_event, on_data=on_data).start(),
}
