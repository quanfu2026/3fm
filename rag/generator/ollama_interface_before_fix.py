import requests


class OllamaInterface:
    def __init__(self, model="qwen2.5:3b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def generate(self, query: str, context: str) -> str:
        prompt = f"""
你是電商客服助理。
請只能根據下列知識片段回答問題。
如果資料不足，請回答「根據目前資料無法確認」，不要編造。

使用者問題：
{query}

知識片段：
{context}

請用繁體中文簡潔回答：
"""

        try:
            r = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=120,
            )
            r.raise_for_status()
            return r.json().get("response", "").strip()

        except Exception as e:
            return f"""⚠️ Ollama 生成失敗，系統已降級為檢索結果展示模式。

錯誤原因：
{e}

以下是本次檢索到的知識片段，可作為口試展示依據：

{context}
"""