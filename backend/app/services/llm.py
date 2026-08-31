"""LLM 适配层（M2）：统一封装学校大模型 API（OpenAI 兼容网关）。

所有模型调用必须经过本模块，禁止在业务代码里直接 requests 网关。
生效配置 = 环境变量(.env) 默认值 + data/settings.json 运行时覆盖（设置页写入），
详见 app.core.settings_store.effective_settings。
"""
import asyncio
import time
from collections.abc import AsyncIterator

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError

from app.core import settings_store


class LLMError(Exception):
    """模型调用失败（映射契约错误码 E_LLM）。"""


# [2026-08-31] Harness·Loop：连接错误/超时/5xx 自动重试，最多 2 次（指数退避 1s/2s）
_MAX_RETRIES = 2
_RETRYABLE = (APIConnectionError, APITimeoutError)


def _is_retryable(e: Exception) -> bool:
    if isinstance(e, _RETRYABLE):
        return True
    return isinstance(e, APIStatusError) and getattr(e, "status_code", 0) >= 500


async def _create_with_retry(client: AsyncOpenAI, **kwargs):
    """非流式调用 + 有界重试：同一错误换措辞重试 20 次不叫坚持，叫烧钱。"""
    last: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return await client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            if not _is_retryable(e) or attempt >= _MAX_RETRIES:
                raise LLMError(f"E_LLM: {e}") from e
            last = e
            await asyncio.sleep(2 ** attempt)
    raise LLMError(f"E_LLM: {last}")  # pragma: no cover


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：中文约 1.5 字符/token，英文约 4 字符/token，取折中值。"""
    return max(1, len(text) // 2)


def _client() -> AsyncOpenAI:
    """按生效配置构造客户端。"""
    eff = settings_store.effective_settings()
    return AsyncOpenAI(
        base_url=eff["api_base_url"],
        api_key=eff["api_key"] or "sk-unset",
        timeout=eff["llm_timeout"],
    )


def _models() -> dict:
    """生效配置中的模型名。"""
    eff = settings_store.effective_settings()
    return {
        "chat": eff["chat_model"],
        "vision": eff.get("vision_model") or eff["chat_model"],
    }


async def chat_stream(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.3,
    usage_out: dict | None = None,
) -> AsyncIterator[str]:
    """流式对话。逐段 yield 文本 token。

    usage_out：可选输出参数，结束后填入 {prompt_tokens, completion_tokens}。
    网关返回 usage 时用真实值，否则按字符数估算（Harness·Observability）。
    重试策略：若尚未产出任何 token 时遇到可重试错误则重试；
    已产出内容则不再重试，直接正常收尾（避免重复输出）。
    """
    client = _client()
    kwargs: dict = {"model": _models()["chat"], "messages": messages, "temperature": temperature}
    if tools:
        kwargs["tools"] = tools

    # TODO(@M2): 网关若支持 tools 直接传参；不支持则退回"文本协议解析"兑底
    emitted = 0
    for attempt in range(_MAX_RETRIES + 1):
        try:
            stream = await client.chat.completions.create(**kwargs, stream=True)
            async for chunk in stream:
                if getattr(chunk, "usage", None) and usage_out is not None:
                    usage_out["prompt_tokens"] = chunk.usage.prompt_tokens
                    usage_out["completion_tokens"] = chunk.usage.completion_tokens
                if chunk.choices and chunk.choices[0].delta.content:
                    emitted += len(chunk.choices[0].delta.content)
                    yield chunk.choices[0].delta.content
            break
        except Exception as e:  # noqa: BLE001
            if emitted > 0:
                # 已产出内容：不重试，直接收尾（中断处已完成部分保留）
                break
            if not _is_retryable(e) or attempt >= _MAX_RETRIES:
                raise LLMError(f"E_LLM: {e}") from e
            await asyncio.sleep(2 ** attempt)
    if usage_out is not None:
        usage_out.setdefault("prompt_tokens", estimate_tokens(str(messages)))
        usage_out.setdefault("completion_tokens", max(1, emitted // 2))


async def chat_once(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """单次对话（非流式），返回完整 message 对象（含 tool_calls 时）。

    返回值额外携带 "usage": {prompt_tokens, completion_tokens}（真实值或估算值）。
    """
    client = _client()
    kwargs: dict = {"model": _models()["chat"], "messages": messages, "temperature": 0.3}
    if tools:
        kwargs["tools"] = tools

    start = time.monotonic()
    resp = await _create_with_retry(client, **kwargs)
    msg = resp.choices[0].message
    out = msg.model_dump(exclude_none=True)
    usage = getattr(resp, "usage", None)
    out["usage"] = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or estimate_tokens(str(messages)),
        "completion_tokens": getattr(usage, "completion_tokens", 0)
        or estimate_tokens(msg.content or ""),
        "latency_ms": int((time.monotonic() - start) * 1000),
    }
    return out


async def vision_analyze(image_url: str, prompt: str = "识别这张截图中的代码与报错信息") -> str:
    """调用视觉模型识别图片，返回文本。"""
    client = _client()
    resp = await client.chat.completions.create(
        model=_models()["vision"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """文本向量化：本地 bge-m3（设置页可切换为网关 embedding）。

    TODO(@M2): embedding_use_local=true 时用 sentence-transformers 加载
    settings.embedding_model 并缓存；false 时调用网关 {base_url}/embeddings。
    """
    eff = settings_store.effective_settings()
    if not eff.get("embedding_use_local", True):
        client = _client()
        resp = await client.embeddings.create(model=eff["embedding_model"], input=texts)
        return [d.embedding for d in resp.data]

    # 本地模型加载与推理均为同步 CPU 密集操作，放到线程池避免阻塞事件循环
    return await asyncio.to_thread(_encode_local, eff["embedding_model"], texts)


_embedder_cache: dict = {}


def _encode_local(model_name: str, texts: list[str]) -> list[list[float]]:
    """本地 SentenceTransformer 编码（同步，在线程池中执行）。"""
    if model_name not in _embedder_cache:
        from sentence_transformers import SentenceTransformer  # 延迟导入，加速启动

        _embedder_cache[model_name] = SentenceTransformer(model_name)
    model = _embedder_cache[model_name]
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]
