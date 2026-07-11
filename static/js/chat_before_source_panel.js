/* ── AI 客服視窗互動邏輯 ── */

function toggleChat() {
  const widget = document.getElementById('chatWidget');
  widget.classList.toggle('open');
}

async function sendChat() {
  const input   = document.getElementById('chatInput');
  const query   = input.value.trim();
  if (!query) return;

  const reranker = document.getElementById('rerankerToggle').checked;
  const topK     = parseInt(document.getElementById('topKSelect').value);

  appendMsg('user', query);
  input.value = '';

  const typing = appendMsg('assistant', '⏳ 正在查詢知識庫...', true);

  try {
    const res = await fetch('/chat/api', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({ query, reranker, top_k: topK }),
    });
    const data = await res.json();
    typing.remove();

    if (data.error) {
      appendMsg('assistant', '❌ ' + data.error);
      return;
    }

    // 主要回答
    appendMsg('assistant', data.answer);

    // 來源標籤
    if (data.sources && data.sources.length) {
      const tags = data.sources.map(s =>
        `<span class="source-tag">${getFilename(s.source || s.id)}</span>`
      ).join('');
      appendRaw(`<div class="source-tags">${tags}</div>`);
    }

    // 效率指標
    updateMetrics(data.metrics, data.reranker_diff);

  } catch (e) {
    typing.remove();
    appendMsg('assistant', '❌ 連線失敗，請稍後再試。');
  }
}

function appendMsg(role, text, isTyping = false) {
  const box = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = `msg ${role}${isTyping ? ' typing' : ''}`;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

function appendRaw(html) {
  const box = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.innerHTML = html;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function updateMetrics(m, diff) {
  if (!m) return;
  const panel = document.getElementById('chatMetrics');
  panel.style.display = 'flex';

  document.getElementById('metricLatency').textContent =
    `⏱ ${m.total_ms}ms`;
  document.getElementById('metricReranker').textContent =
    m.reranker_enabled
      ? `🔍 Reranker +${m.reranker_ms}ms`
      : `🔍 Reranker OFF`;
  document.getElementById('metricMRR').textContent =
    `📄 ${m.final_docs} 文件`;
}

function getFilename(path) {
  if (!path) return '知識庫';
  return path.split('/').pop().split('\\').pop();
}
async function runEvaluation() {
  const typing = appendMsg('assistant', '📊 正在執行 115 題評測，請稍候...', true);

  try {
    const res = await fetch('/chat/evaluate');
    const data = await res.json();
    typing.remove();

    const card = `
      <div style="
        border:1px solid #ddd;
        border-radius:10px;
        padding:14px;
        margin:10px 0;
        background:#fff;
        font-family:Consolas, monospace;
        line-height:1.8;
      ">
        <b>📊 評測結果總覽（115 題）</b><br>
        ────────────────────<br>
        Hit@5&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= ${data["Hit@5"]}<br>
        MRR&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= ${data["MRR"]}<br>
        NDCG@5&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= ${data["NDCG@5"]}<br>
        平均延遲&nbsp;&nbsp;&nbsp;&nbsp;= ${data["avg_latency_ms"]} ms<br>
        <br>
        JSON：${data["json_path"]}<br>
        CSV ：${data["csv_path"]}
      </div>
    `;

    appendRaw(card);

  } catch (e) {
    typing.remove();
    appendMsg('assistant', '❌ 評測失敗，請檢查 data/eval_questions.json 是否存在。');
  }
}