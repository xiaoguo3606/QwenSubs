"""Unified LLM client supporting Ollama and OpenAI-compatible APIs."""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)


LLMType = Literal["ollama", "openai"]


class LLMClient:
    """Unified client for Ollama and OpenAI-compatible APIs."""

    def __init__(
        self,
        llm_type: LLMType = "ollama",
        ollama_endpoint: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:7b",
        openai_base_url: str = "",
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
    ):
        self.llm_type = llm_type
        self.ollama_endpoint = ollama_endpoint.rstrip("/")
        self.ollama_model = ollama_model
        self.openai_base_url = openai_base_url.rstrip("/")
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model

    def correct_transcription(
        self,
        text: str,
        hint_text: str,
    ) -> str:
        """Use LLM to correct ASR transcription with hint text."""
        system_prompt = (
            "You are an ASR (Automatic Speech Recognition) correction assistant. "
            "You will receive two pieces of input:\n"
            "1. The raw transcribed text from an ASR system (may contain errors).\n"
            "2. Hint text — proper nouns (names, places, domain terms) "
            "that the user expects to appear in the transcript.\n\n"
            "Your task is to correct the transcribed text by ensuring the hint-text "
            "terms are accurately reflected, fixing misrecognized proper nouns, "
            "and correcting any obvious ASR errors related to these terms.\n"
            "Do NOT modify parts of the text that are already correct.\n"
            "Return ONLY the corrected text, nothing else.\n\n"
            "你是一个语音识别校正助手。\n"
            "你将收到两段输入：\n"
            "1. ASR 系统输出的原始识别文本（可能包含错误）。\n"
            "2. 提示性文字——用户提供的专有名词（人名、地名、领域术语等）。\n\n"
            "请根据提示性文字修正识别结果，确保专有名词被正确识别，"
            "同时保持其他已正确的部分不变。\n只返回修正后的文本，不要添加任何解释。"
        )
        user_prompt = (
            f"原始识别文本：{text}\n"
            f"提示性文字：{hint_text}\n"
            "请根据提示性文字修正识别结果中的错误："
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if self.llm_type == "ollama":
            return self._call_ollama(messages)
        return self._call_openai(messages)

    def _call_ollama(self, messages: list[dict]) -> str:
        import httpx
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
        }
        url = f"{self.ollama_endpoint}/api/chat"
        resp = httpx.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"].strip()

    def _call_openai(self, messages: list[dict]) -> str:
        from openai import OpenAI
        client = OpenAI(
            base_url=self.openai_base_url,
            api_key=self.openai_api_key,
        )
        resp = client.chat.completions.create(
            model=self.openai_model,
            messages=messages,
            timeout=300,
        )
        return resp.choices[0].message.content.strip()
