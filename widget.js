(function () {
  const scriptSrc    = document.currentScript?.src || "";
  const scriptUrl    = scriptSrc ? new URL(scriptSrc) : new URL(window.location.href);
  const BASE         = scriptUrl.origin;
  const TENANT       = scriptUrl.searchParams.get("tenant") || "default";
  const API_URL      = BASE + "/chat";
  const SETTINGS_URL = `${BASE}/settings?tenant=${TENANT}`;
  const FEEDBACK_URL = `${BASE}/customer-feedback`;

  async function init() {
    let s = { bot_name: "Destek Asistanı", welcome_message: "Merhaba! Size nasıl yardımcı olabilirim?", color: "#1a1a2e", icon: "💬" };
    try { s = await (await fetch(SETTINGS_URL)).json(); } catch {}

    const c = s.color;

    const style = document.createElement("style");
    style.textContent = `
      #tn-btn {
        position:fixed; bottom:24px; right:24px; z-index:99999;
        width:56px; height:56px; border-radius:50%;
        background:${c}; color:#fff; border:none; cursor:pointer;
        box-shadow:0 4px 16px rgba(0,0,0,0.25);
        font-size:24px; display:flex; align-items:center; justify-content:center;
        transition:transform 0.2s;
      }
      #tn-btn:hover { transform:scale(1.08); }
      #tn-box {
        position:fixed; bottom:92px; right:24px; z-index:99998;
        width:340px; border-radius:16px;
        background:#fff; box-shadow:0 8px 32px rgba(0,0,0,0.18);
        display:none; flex-direction:column; overflow:hidden;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }
      #tn-box.open { display:flex; }
      #tn-header {
        background:${c}; color:#fff;
        padding:14px 16px; font-size:14px; font-weight:600;
        display:flex; align-items:center; justify-content:space-between;
      }
      #tn-header-info span { font-size:11px; font-weight:400; opacity:0.6; display:block; margin-top:2px; }
      #tn-msgs { height:360px; overflow-y:auto; padding:12px; display:flex; flex-direction:column; gap:8px; }
      .tn-msg { max-width:85%; padding:9px 12px; border-radius:10px; font-size:13px; line-height:1.5; white-space:pre-wrap; word-break:break-word; }
      .tn-msg.user { background:${c}; color:#fff; align-self:flex-end; border-bottom-right-radius:3px; }
      .tn-msg.bot  { background:#f0f2f5; color:#1a1a2e; align-self:flex-start; border-bottom-left-radius:3px; }
      .tn-dots span { display:inline-block; width:6px; height:6px; margin:0 2px; background:#999; border-radius:50%; animation:tn-bounce 1.2s infinite ease-in-out; }
      .tn-dots span:nth-child(2) { animation-delay:.2s; }
      .tn-dots span:nth-child(3) { animation-delay:.4s; }
      @keyframes tn-bounce { 0%,80%,100%{transform:scale(0.6);opacity:.4;} 40%{transform:scale(1);opacity:1;} }
      #tn-footer { display:flex; gap:8px; padding:10px 12px; border-top:1px solid #eee; }
      #tn-input { flex:1; padding:9px 12px; border:1.5px solid #ddd; border-radius:8px; font-size:13px; outline:none; font-family:inherit; resize:none; height:38px; }
      #tn-input:focus { border-color:${c}; }
      #tn-send { padding:0 14px; background:${c}; color:#fff; border:none; border-radius:8px; font-size:13px; font-weight:600; cursor:pointer; height:38px; }
      #tn-send:disabled { background:#bbb; cursor:not-allowed; }
      #tn-fb-btn {
        padding:0 10px; background:none; color:${c}; border:1.5px solid ${c};
        border-radius:8px; font-size:14px; cursor:pointer; height:38px;
        flex-shrink:0; transition:background 0.15s;
      }
      #tn-fb-btn:hover { background:#f0f2f5; }
      #tn-fb-btn.active { background:${c}; color:#fff; }
      #tn-fb-panel {
        display:none; flex-direction:column; gap:8px;
        padding:10px 12px; border-top:1px solid #eee; background:#fafafa;
      }
      #tn-fb-panel.open { display:flex; }
      #tn-fb-label { font-size:12px; color:#666; font-weight:600; }
      #tn-fb-input {
        width:100%; padding:8px 12px; border:1.5px solid #ddd; border-radius:8px;
        font-size:13px; outline:none; resize:none; font-family:inherit; min-height:64px;
      }
      #tn-fb-input:focus { border-color:${c}; }
      .tn-fb-btns { display:flex; gap:8px; }
      #tn-fb-send { flex:1; padding:8px; background:${c}; color:#fff; border:none; border-radius:8px; font-size:13px; font-weight:600; cursor:pointer; }
      #tn-fb-send:disabled { background:#bbb; cursor:not-allowed; }
      #tn-fb-cancel { padding:8px 12px; background:none; border:1.5px solid #ddd; color:#666; border-radius:8px; font-size:13px; cursor:pointer; }
    `;
    document.head.appendChild(style);

    document.body.insertAdjacentHTML("beforeend", `
      <button id="tn-btn" title="Soru sor">${s.icon}</button>
      <div id="tn-box">
        <div id="tn-header">
          <div id="tn-header-info">${s.bot_name} <span>Size nasıl yardımcı olabiliriz?</span></div>
        </div>
        <div id="tn-msgs">
          <div class="tn-msg bot">${s.welcome_message}</div>
        </div>
        <div id="tn-footer">
          <textarea id="tn-input" placeholder="Mesajınızı yazın..." rows="1"></textarea>
          <button id="tn-fb-btn" title="Geri Bildirim Gönder">📝</button>
          <button id="tn-send">Gönder</button>
        </div>
        <div id="tn-fb-panel">
          <div id="tn-fb-label">Öneri, görüş veya şikayetinizi yazın:</div>
          <textarea id="tn-fb-input" placeholder="Görüşünüzü buraya yazın..."></textarea>
          <div class="tn-fb-btns">
            <button id="tn-fb-cancel">İptal</button>
            <button id="tn-fb-send">Gönder</button>
          </div>
        </div>
      </div>
    `);

    const btn     = document.getElementById("tn-btn");
    const box     = document.getElementById("tn-box");
    const msgs    = document.getElementById("tn-msgs");
    const inp     = document.getElementById("tn-input");
    const snd     = document.getElementById("tn-send");
    const fbBtn   = document.getElementById("tn-fb-btn");
    const fbPanel = document.getElementById("tn-fb-panel");
    const fbInput = document.getElementById("tn-fb-input");
    const fbSend  = document.getElementById("tn-fb-send");
    const fbCancel= document.getElementById("tn-fb-cancel");

    btn.addEventListener("click", () => {
      box.classList.toggle("open");
      if (box.classList.contains("open")) inp.focus();
    });

    function addMsg(text, role) {
      const d = document.createElement("div");
      d.className = "tn-msg " + role;
      d.textContent = text;
      msgs.appendChild(d);
      msgs.scrollTop = msgs.scrollHeight;
    }

    function addLoader() {
      const d = document.createElement("div");
      d.className = "tn-msg bot";
      d.innerHTML = '<div class="tn-dots"><span></span><span></span><span></span></div>';
      msgs.appendChild(d);
      msgs.scrollTop = msgs.scrollHeight;
      return d;
    }

    async function sendMsg() {
      const text = inp.value.trim();
      if (!text) return;
      inp.value = "";
      snd.disabled = true;
      addMsg(text, "user");
      const loader = addLoader();
      try {
        const res  = await fetch(API_URL, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({message:text, tenant_id:TENANT}) });
        const data = await res.json();
        loader.remove();
        addMsg(res.ok ? data.reply : "Bir hata oluştu.", "bot");
      } catch {
        loader.remove();
        addMsg("Sunucuya bağlanılamadı.", "bot");
      } finally {
        snd.disabled = false;
        inp.focus();
      }
    }

    // Geri bildirim paneli aç/kapat
    fbBtn.addEventListener("click", () => {
      const isOpen = fbPanel.classList.toggle("open");
      fbBtn.classList.toggle("active", isOpen);
      if (isOpen) fbInput.focus();
    });

    fbCancel.addEventListener("click", () => {
      fbPanel.classList.remove("open");
      fbBtn.classList.remove("active");
      fbInput.value = "";
    });

    fbSend.addEventListener("click", async () => {
      const text = fbInput.value.trim();
      if (!text) return;
      fbSend.disabled = true;
      try {
        const res  = await fetch(FEEDBACK_URL, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text, tenant_id: TENANT}),
        });
        const data = await res.json();
        fbPanel.classList.remove("open");
        fbBtn.classList.remove("active");
        fbInput.value = "";
        const typeLabel = data.type === "şikayet" ? "şikayetiniz" : data.type === "öneri" ? "öneriniz" : "görüşünüz";
        addMsg(`Geri bildiriminiz alındı, teşekkürler! ${typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1)} ekibimize iletildi.`, "bot");
      } catch {
        addMsg("Geri bildirim gönderilemedi, lütfen tekrar deneyin.", "bot");
      } finally {
        fbSend.disabled = false;
      }
    });

    snd.addEventListener("click", sendMsg);
    inp.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } });
  }

  init();
})();
