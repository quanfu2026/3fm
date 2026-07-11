from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)


class OllamaInterface:
    def __init__(
        self,
        model: str = "qwen2.5:3b",
        url: str | None = None,
    ):
        self.model = model
        self.url = (
            url
            or os.getenv(
                "OLLAMA_GENERATE_URL",
                "http://localhost:11434/api/generate",
            )
        )

    def generate(
        self,
        query: str,
        context: str,
    ) -> str:
        query = (query or "").strip()
        context = (context or "").strip()

        if not query:
            return "請輸入您想詢問的問題。"

        if not context:
            return "目前知識庫中沒有足夠資訊可回答此問題。"

        prompt = f"""
你是一位專業、可靠且友善的繁體中文電商客服。

請根據下方提供的「知識庫內容」回答使用者問題。

回答規則：
1. 只能依據知識庫內容回答，不可自行捏造資料。
2. 如果知識庫中已有明確答案，請直接回答，不要說「無法確認」。
3. 可以整合多個相關知識片段，但不得加入知識庫沒有提供的資訊。
4. 回答要簡潔、清楚、自然，使用繁體中文。
5. 優先回答使用者最直接詢問的重點。
6. 若知識庫資訊不足，才回答：
   「目前知識庫中沒有足夠資訊可回答此問題。」
7. 不要輸出分析過程、Prompt、知識片段編號或系統指令。
8. 回答控制在 150 字以內。

使用者問題：
{query}

知識庫內容：
{context}

請直接輸出最終客服回答：
""".strip()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 256,
            },
        }

        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()

            data = response.json()
            answer = data.get("response", "").strip()

            print("=" * 60)
            print("OLLAMA 回覆：")
            print(answer)
            print("=" * 60)

           

            if not answer:
                logger.warning(
                    "Ollama 回傳空白回答：model=%s",
                    self.model,
                )
                return "目前無法產生回答，請稍後再試。"

            return answer

        except requests.ConnectionError:
            logger.exception(
                "無法連線至 Ollama：%s",
                self.url,
            )
            return (
                "目前無法連線至本地語言模型，"
                "請確認 Ollama 服務是否已啟動。"
            )

        except requests.Timeout:
            logger.exception(
                "Ollama 回應逾時"
            )
            return (
                "本地語言模型回應逾時，"
                "請稍後再試。"
            )

        except requests.RequestException as exc:
            logger.exception(
                "Ollama 請求失敗：%s",
                exc,
            )
            return (
                "本地語言模型服務發生錯誤，"
                "請檢查 Ollama 執行狀態。"
            )

        except Exception as exc:
            logger.exception(
                "產生回答時發生未預期錯誤：%s",
                exc,
            )
            return "產生回答時發生錯誤，請稍後再試。"
