"""中文错误，以及连接信息里的密码打码。"""

from __future__ import annotations

import re

_MYSQL_URL = re.compile(r"(mysql://[^:\s/@]+:)([^@/\s]*)(@)")
_QUOTED_PASSWORD = re.compile(r"(password\s*=\s*')((?:''|[^'])*)(')", re.IGNORECASE)
_BARE_PASSWORD = re.compile(r"(password\s*=\s*)(\S+)", re.IGNORECASE)


class TableProbeError(Exception):
    """tableprobe 抛出的错误，说明文字是中文。"""


def redact(text: str) -> str:
    """去掉连接串和报错文本里的密码。"""

    text = _MYSQL_URL.sub(r"\1***\3", text)
    text = _QUOTED_PASSWORD.sub(r"\1***\3", text)
    text = _BARE_PASSWORD.sub(r"\1***", text)
    return text
