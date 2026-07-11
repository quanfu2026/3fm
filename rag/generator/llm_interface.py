"""
統一 LLM 介面層 — 支援 Qwen2.5 / GPT / Claude /gemini 無縫切換
論文設計：模組化生成端，企業可依算力與預算自由替換
"""
import os
import logging
from dotenv import load_dotenv

# 強制讀取並覆蓋環境變數
load_dotenv(override=True)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位專業的電商客服助理。
請根據以下提供的知識片段回答客戶問題。
規則：
1. 只能根據知識片段中的資訊回答，不可自行編造
2. 若知識片段中找不到答案，請誠實告知「很抱歉，我目前沒有這個問題的相關資料，建議您聯繫客服人員」
3. 回答需簡潔、友善、專業
4. 若涉及價格、政策，請務必引用來源片段中的確切資訊"""
class LLMInterface:

    def __init__(self):
        print(f"DEBUG: 實際讀取到的 PROVIDER 是 '{os.getenv('LLM_PROVIDER')}'")
        self.provider = os.getenv("LLM_PROVIDER", "gemini-3.5-flash").lower()
        logger.info(f"LLM Provider: {self.provider}")

    # ── 主生成入口（具備自動跳選容錯機制） ────────────────────────────────────
    def generate(self, query: str, context: str) -> str:
        prompt = self._build_prompt(query, context)
        
        # 定義當主要 LLM 掛掉時的「跳選順序清單」
        # 如果 `.env` 設定 gemini，順序就是：gemini -> gpt -> qwen
        # 如果 `.env` 設定 gpt，順序就是：gpt -> gemini -> qwen
        primary = self.provider
        fallback_chain = [primary, "gemini", "gpt", "qwen"]
        
        # 去除重複項，保持順序
        clean_chain = []
        for provider in fallback_chain:
            if provider not in clean_chain:
                clean_chain.append(provider)
        
        # 開始依序嘗試連線
        for current_provider in clean_chain:
            try:
                logger.info(f"正在嘗試使用 LLM 供應商: {current_provider}")
                
                if current_provider == "gemini":
                    return self._call_gemini(prompt)
                elif current_provider == "gpt":
                    return self._call_gpt(prompt)
                elif current_provider == "qwen":
                    return self._call_qwen(prompt)
                elif current_provider == "claude":
                    return self._call_claude(prompt)
                    
            except Exception as e:
                # 當前 LLM 掛掉了，抓取錯誤並記錄，但不中斷程式，直接讓 loop 進入下一輪跳選
                logger.warning(f"供應商 {current_provider} 連線掛掉！錯誤訊息: {e}. 系統正在自動跳選至下一個備用 LLM...")
                continue
                
        # 如果清單內所有的 LLM 統統都連不上，才執行最終的文字備援
        logger.critical("所有配置的 LLM 供應商皆連線失敗！")
        return self._fallback(query)

    # ── Prompt 組合 ───────────────────────────────────
    def _build_prompt(self, query: str, context: str) -> str:
        return f"""【知識庫內容】
{context}

【客戶問題】
{query}

請根據以上知識庫內容，給出專業、友善的回答："""

    # ── Qwen2.5（阿里達摩院，中文電商場景最佳）────────
    def _call_qwen(self, prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("QWEN_API_KEY", ""),
            base_url=os.getenv(
                "QWEN_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
        )
        resp = client.chat.completions.create(
            model=os.getenv("QWEN_MODEL", "qwen2.5-72b-instruct"),
            messages=[
                {"role": "system",  "content": SYSTEM_PROMPT},
                {"role": "user",    "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        return resp.choices[0].message.content.strip()

    # ── GPT（OpenAI）─────────────────────────────────
    def _call_gpt(self, prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system",  "content": SYSTEM_PROMPT},
                {"role": "user",    "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        return resp.choices[0].message.content.strip()

    # ── Claude（Anthropic）───────────────────────────
    def _call_claude(self, prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", "")
        )
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()

    
    
# ── Gemini (Google 2026 新版 SDK 規範) ──────────────
    def _call_gemini(self, prompt: str) -> str:
        # 💡 使用符合新版规范的初始化方式
        from google import genai
        from google.genai import types
        
        # 1. 建立 Client 實例（會自動抓取環境變數中的 GEMINI_API_KEY）
        # 如果你希望顯式傳入，可以使用 client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        client = genai.Client()
        
        # 2. 將系統提示詞封裝進新版的 GenerateContentConfig 中
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1
        )
        
        # 3. 呼叫新版模型生成介面
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        
        return resp.text.strip()

    # ── Fallback（無 API Key 時）─────────────────────
    def _fallback(self, query: str) -> str:
        return (
            "很抱歉，AI 客服目前暫時無法連線。"
            "請透過電話或 Email 聯繫我們的客服人員，謝謝！"
        )
# ── 貼在 llm_interface.py 的最底部 ──────────────────────────────

if __name__ == "__main__":
    import os
    # 確保日誌能印在終端機畫面上
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("\n" + "="*20 + " 單獨測試開始 " + "="*20)
    
    # 1. 初始化介面
    llm = LLMInterface()
    
    # 2. 模擬 RAG 給予的上下文與問題
    test_context = "2026智慧機器工程系有機電商平台提供全台最優質的自動化農業機具與溫室感測器，客服專線為 0800-000-000。"
    test_query = "請問你們客服電話是多少？"
    
    print(f"【設定測試】目前主供應商預設為: {llm.provider}")
    print(f"【測試問題】{test_query}")
    print("正在呼叫生成 pipeline，請稍候...\n")
    
    # 3. 執行生成（這會觸發你的跳選機制）
    reply = llm.generate(query=test_query, context=test_context)
    
    print("\n" + "="*20 + " AI 回應結果 " + "="*20)
    print(reply)
    print("="*50 + "\n")