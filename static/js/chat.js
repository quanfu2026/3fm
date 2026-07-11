/* AI 客服視窗互動邏輯 */

function toggleChat() {
  const widget = document.getElementById("chatWidget");

  if (widget) {
    widget.classList.toggle("open");
  }
}


async function sendChat() {
  const input = document.getElementById("chatInput");
  const rerankerToggle = document.getElementById("rerankerToggle");
  const topKSelect = document.getElementById("topKSelect");

  if (!input) {
    console.error("找不到 chatInput");
    return;
  }

  const query = input.value.trim();

  if (!query) {
    return;
  }

  const reranker = rerankerToggle
    ? rerankerToggle.checked
    : false;

  const topK = topKSelect
    ? Number.parseInt(topKSelect.value, 10)
    : 5;

  appendMsg("user", query);
  input.value = "";

  const typing = appendMsg(
    "assistant",
    "⏳ 正在查詢知識庫...",
    true
  );

  try {
    const response = await fetch("/chat/api", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        query: query,
        reranker: reranker,
        top_k: topK
      })
    });

    const data = await response.json();

    if (typing) {
      typing.remove();
    }

    if (!response.ok || data.error) {
      appendMsg(
        "assistant",
        "❌ " + (data.error || "查詢失敗")
      );
      return;
    }

    appendMsg(
      "assistant",
      data.answer || "目前沒有可顯示的回答。"
    );

    renderSources(data.sources || []);
    updateMetrics(
      data.metrics || {},
      data.reranker_diff || []
    );

  } catch (error) {
    console.error("Chat API error:", error);

    if (typing) {
      typing.remove();
    }

    appendMsg(
      "assistant",
      "❌ 連線失敗，請確認 Flask 與 Ollama 是否正常運作。"
    );
  }
}


function appendMsg(role, text, isTyping = false) {
  const box = document.getElementById("chatMessages");

  if (!box) {
    console.error("找不到 chatMessages");
    return null;
  }

  const div = document.createElement("div");

  div.className =
    `msg ${role}${isTyping ? " typing" : ""}`;

  div.textContent = text;

  box.appendChild(div);
  box.scrollTop = box.scrollHeight;

  return div;
}


function appendRaw(html) {
  const box = document.getElementById("chatMessages");

  if (!box) {
    console.error("找不到 chatMessages");
    return null;
  }

  const div = document.createElement("div");
  div.innerHTML = html;

  box.appendChild(div);
  box.scrollTop = box.scrollHeight;

  return div;
}


function renderSources(sources) {
  if (!Array.isArray(sources) || sources.length === 0) {
    return;
  }

  const sourceCards = sources.map((source, index) => {
    const filename = escapeHtml(
      getFilename(source.source || source.id)
    );

    const content = escapeHtml(
      source.content || source.text || "無內容"
    );

    const score = formatScore(source.score);
    const type = escapeHtml(source.type || "knowledge");

    return `
      <details class="source-card">
        <summary>
          <span class="source-rank">
            ${index + 1}
          </span>

          <span class="source-name">
            ${filename}
          </span>

          ${
            score
              ? `<span class="source-score">
                   ${score}
                 </span>`
              : ""
          }
        </summary>

        <div class="source-detail">
          <div class="source-meta">
            類型：${type}
          </div>

          <div class="source-content">
            ${content.replace(/\n/g, "<br>")}
          </div>
        </div>
      </details>
    `;
  }).join("");

  appendRaw(`
    <div class="sources-panel">
      <div class="sources-title">
        📚 參考來源
      </div>

      ${sourceCards}
    </div>
  `);
}


function updateMetrics(metrics, rerankerDiff) {
  if (!metrics) {
    return;
  }

  const panel = document.getElementById("chatMetrics");

  if (!panel) {
    return;
  }

  panel.style.display = "flex";

  setText(
    "metricLatency",
    `⏱ ${metrics.total_ms ?? 0} ms`
  );

  setText(
    "metricReranker",
    metrics.reranker_enabled
      ? `🔍 Reranker ON（${metrics.reranker_ms ?? 0} ms）`
      : "🔍 Reranker OFF"
  );

  setText(
    "metricMRR",
    `📄 最終 ${metrics.final_docs ?? 0} 份文件`
  );

  const extra = document.getElementById(
    "metricRetrieval"
  );

  if (extra) {
    extra.textContent =
      `BM25 ${metrics.bm25_hits ?? 0}｜` +
      `BGE ${metrics.bge_hits ?? 0}`;
  }

  if (
    Array.isArray(rerankerDiff) &&
    rerankerDiff.length > 0
  ) {
    console.log(
      "Reranker 排序差異：",
      rerankerDiff
    );
  }
}


function setText(id, value) {
  const element = document.getElementById(id);

  if (element) {
    element.textContent = value;
  }
}


function getFilename(path) {
  if (!path) {
    return "知識庫";
  }

  return path
    .split("/")
    .pop()
    .split("\\")
    .pop();
}


function formatScore(score) {
  if (
    score === undefined ||
    score === null ||
    Number.isNaN(Number(score))
  ) {
    return "";
  }

  return Number(score).toFixed(4);
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


async function runEvaluation() {
  const typing = appendMsg(
    "assistant",
    "📊 正在讀取正式評測結果...",
    true
  );

  try {
    const response = await fetch("/chat/evaluate");
    const data = await response.json();

    if (typing) {
      typing.remove();
    }

    if (!response.ok || data.error) {
      appendMsg(
        "assistant",
        "❌ " + (data.error || "評測資料讀取失敗")
      );
      return;
    }

    const card = `
      <div class="evaluation-card">
        <div class="evaluation-title">
          📊 評測結果總覽
        </div>

        <div class="evaluation-grid">
          <div>
            <span>題數</span>
            <strong>${data.total_questions ?? 0}</strong>
          </div>

          <div>
            <span>Hit@5</span>
            <strong>${data["Hit@5"] ?? 0}</strong>
          </div>

          <div>
            <span>MRR</span>
            <strong>${data["MRR"] ?? 0}</strong>
          </div>

          <div>
            <span>NDCG@5</span>
            <strong>${data["NDCG@5"] ?? 0}</strong>
          </div>

          <div>
            <span>BGE Cosine</span>
            <strong>${data["BGE Cosine"] ?? 0}</strong>
          </div>

          <div>
            <span>Coverage Proxy</span>
            <strong>${data["Coverage Proxy"] ?? 0}</strong>
          </div>

          <div>
            <span>平均延遲</span>
            <strong>${data["平均延遲(ms)"] ?? 0} ms</strong>
          </div>

          <div>
            <span>P95 延遲</span>
            <strong>${data["P95延遲(ms)"] ?? 0} ms</strong>
          </div>
        </div>

        <div class="evaluation-meta">
          模型：${escapeHtml(data.model || "未提供")}<br>
          Reranker：
          ${data.use_reranker ? "啟用" : "停用"}<br>
          來源：
          ${escapeHtml(data.source_file || "")}
        </div>
      </div>
    `;

    appendRaw(card);

  } catch (error) {
    console.error(
      "Evaluation API error:",
      error
    );

    if (typing) {
      typing.remove();
    }

    appendMsg(
      "assistant",
      "❌ 評測失敗，請確認正式評測 JSON 檔案是否存在。"
    );
  }
}


/* Enter 送出，Shift + Enter 換行 */
document.addEventListener(
  "DOMContentLoaded",
  () => {
    const input = document.getElementById("chatInput");

    if (!input) {
      return;
    }

    input.addEventListener(
      "keydown",
      event => {
        if (
          event.key === "Enter" &&
          !event.shiftKey
        ) {
          event.preventDefault();
          sendChat();
        }
      }
    );
  }
);
