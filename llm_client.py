"""大模型 SDK 二次封装层。

将原本散落在路由函数里的 OpenAI 客户端初始化、消息拼装、流式调用
统一收口到一个独立的 DeepSeekClient 中，使路由层只关心 HTTP 语义，
不再直接耦合 SDK 细节。同时集中处理：api_key / base_url / model 配置、
System Prompt 加载、规范化 messages 结构、以及流式调用时的异常包装。
"""

import os
import json
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APIConnectionError

# 确保 .env 中的环境变量被加载（API Key 安全隔离的关键一步）
load_dotenv()

# ---------- 配置 ----------
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompt.txt")

# 语气 -> prompt 补充说明的映射，供动态拼接 System Prompt 使用
TONE_DIRECTIVES = {
    "default": "保持与原文一致的语气和风格。",
    "formal": "使用正式、得体、专业的语气，适合公文或商务信函。",
    "casual": "使用自然、口语化、接地气的语气，适合日常交流。",
    "business": "使用商务、严谨、礼貌的语气，适合职场邮件与合同。",
    "literary": "使用优美、富有文学性的语言，注重文采与意境。",
}


class LLMClientError(Exception):
    """封装层抛出的统一异常，携带可对前端展示的提示信息。"""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@lru_cache(maxsize=1)
def _load_prompt() -> str:
    """读取并缓存 System Prompt 模板，避免每次请求都做磁盘 IO。"""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


class DeepSeekClient:
    """对 DeepSeek（OpenAI 兼容接口）的二次封装。"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        # 优先使用显式参数，其次回退到环境变量
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)

        if not self.api_key:
            # 在此即抛出，避免路由层进入后才崩，便于上层统一捕获
            raise LLMClientError(
                "未检测到 DEEPSEEK_API_KEY，请在 .env 中配置后再启动。",
                status_code=500,
            )

        # 标准 openai 官方 SDK，一次性创建复用
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def build_messages(self, text: str, source_lang: str, target_lang: str, tone: str = "default") -> list:
        """规范化请求：组装成标准的 system + user 消息结构。"""
        system_prompt = _load_prompt()
        tone_directive = TONE_DIRECTIVES.get(tone, TONE_DIRECTIVES["default"])
        # 把语气指令追加到 System Prompt 末尾，动态约束大模型输出风格
        full_system = f"{system_prompt}\n\n语气要求：{tone_directive}"

        user_content = (
            f"请将以下「{source_lang}」文本翻译成「{target_lang}」"
            f"（语气风格：{tone}）：\n{text}"
        )
        return [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_content},
        ]

    def translate_stream(self, text: str, source_lang: str, target_lang: str, tone: str = "default"):
        """流式翻译生成器（统一结构化输出）。

        成功时 yield {"delta": <文本片段>}；
        失败时 yield {"error": <提示>, "status": <HTTP状态码>}，便于路由层按 SSE 下发。
        """
        messages = self.build_messages(text, source_lang, target_lang, tone)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )
        except AuthenticationError:
            yield {"error": "API Key 无效或已失效，请检查 .env 配置。", "status": 401}
            return
        except RateLimitError:
            yield {"error": "请求过于频繁，触发限流，请稍后再试。", "status": 429}
            return
        except APIConnectionError:
            yield {"error": "无法连接到模型服务，请检查网络。", "status": 502}
            return
        except APIError as e:
            yield {"error": f"模型服务异常：{e}", "status": 502}
            return
        except Exception as e:  # noqa: BLE001 - 兜底，保证不向进程外抛裸异常
            yield {"error": f"调用大模型时发生未知错误：{e}", "status": 500}
            return

        # 消费流式响应，逐片段 yield
        try:
            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:  # 首个 chunk 的 delta.content 常为 None，需判空
                    yield {"delta": content}
        except Exception as e:  # noqa: BLE001 - 流中途断流也要安全收尾
            yield {"error": f"响应流中断：{e}", "status": 502}


@lru_cache(maxsize=1)
def get_client() -> DeepSeekClient:
    """单例工厂：全局只创建一个 DeepSeekClient，复用底层连接池。"""
    return DeepSeekClient()