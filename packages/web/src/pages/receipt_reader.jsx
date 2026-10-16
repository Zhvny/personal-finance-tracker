// â”€â”€â”€ receipt_reader.jsx â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Receipt Reader â€” upgraded to Claude Vision AI (claude-opus-4-5).
// Falls back to legacy OCR ensemble if AI endpoint unavailable.

import { useState, useRef, useCallback, useEffect } from "react";
import { apiScanReceiptAI, apiScanReceipt, apiExportReceipt, useAIStatus } from "../finance/useApi.js";
import AIPassiveStatus from "../behavioral/AIPassiveStatus.jsx";
import { fmt, CATEGORIES, PAY_LIST, API_BASE } from "../finance/constants.js";
import { CatIcon } from "../finance/icon-maps.jsx";
import { Modal, Empty, FormGroup, FormRow } from "../components.jsx";
import { IconCamera, IconCheck, IconSparkles, IconScan, IconFlash, IconML, IconRecords, IconFile, IconIncome, IconBarChart } from "../icons.jsx";

// â”€â”€ Merchant memory API helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function apiRememberMerchant(merchantName, category) {
  try {
    await fetch(`${API_BASE}/merchant-map/remember`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchant_name: merchantName, category }),
    });
  } catch { /* non-fatal */ }
}

function ConfidenceBadge({ confidence, aiPowered, processingTime }) {
  const pct   = Math.round((confidence ?? 0) * 100);
  const color = pct >= 85 ? "var(--gr)" : pct >= 60 ? "var(--yl)" : "var(--rd)";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", borderRadius: 99, fontSize: 10, fontWeight: 700,
      background: `${color}18`, color, border: `1px solid ${color}30`,
    }}>
      {aiPowered ? "AI" : "OCR"} · {pct}% {processingTime ? `· ${processingTime}s` : ""}
    </span>
  );
}

function ReceiptCard({ receipt, index, onEdit, onExport, exported }) {
  const isIncome = receipt.transaction_type === "income";
  const color    = isIncome ? "var(--gr)" : "var(--rd)";
  const icon     = isIncome ? "â†“" : "â†‘";
  return (
    <div style={{ background:"var(--bg2)", border:"1px solid var(--bdr)", borderRadius:"var(--rl)", padding:18, marginBottom:12, borderLeft:`3px solid ${color}` }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:10, gap:10 }}>
        <div style={{ minWidth:0 }}>
          <div style={{ fontSize:15, fontWeight:700, marginBottom:4 }}>{icon} {receipt.merchant_name || "Unknown Merchant"}</div>
          <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
            <span style={{ fontSize:11, color:"var(--tx3)", fontFamily:"var(--mono)" }}>{receipt.transaction_date?.slice(0,10)}</span>
            <ConfidenceBadge 
              confidence={receipt.confidence} 
              aiPowered={receipt.engine?.startsWith("claude") || receipt.engine?.startsWith("rule") || receipt._aiPowered} 
              processingTime={receipt._processingTime}
            />
          </div>
        </div>
        <div style={{ textAlign:"right", flexShrink:0 }}>
          <div style={{ fontSize:20, fontWeight:700, fontFamily:"var(--mono)", color }}>{fmt(receipt.total_amount)}</div>
          <div style={{ fontSize:11, color:"var(--tx2)" }}>{receipt.currency}</div>
        </div>
      </div>

      <div style={{ display:"flex", gap:8, flexWrap:"wrap", marginBottom: receipt.ai_analysis ? 10 : 12 }}>
        {receipt.doc_type_label && (
          <span className="pill pu" style={{ fontWeight:700, fontSize:10, display:"inline-flex", alignItems:"center", gap:4 }}>
            <IconFile size={11} /> {receipt.doc_type_label}
          </span>
        )}
        <span className={`pill ${isIncome ? "g" : "r"}`}>{icon} {receipt.transaction_type}</span>
        <span className="pill dim" style={{ display:"inline-flex", alignItems:"center", gap:4 }}>
          {CatIcon({ cat: receipt.category, size:12 })} {receipt.category}
        </span>
        {receipt.payment_method && <span className="pill dim">{receipt.payment_method}</span>}
        {receipt.engine?.startsWith("claude") && (
          <span className="pill pu" style={{ fontSize:9 }}>Claude Vision</span>
        )}
        {receipt.engine?.startsWith("rule") && (
          <span className="pill dim" style={{ fontSize:9, color:"#60a5fa" }}>Rule Engine</span>
        )}
      </div>

      {receipt.ai_analysis && (
        <div style={{
          background:"rgba(79,110,247,.06)", border:"1px solid rgba(79,110,247,.2)",
          borderRadius:8, padding:"8px 12px", marginBottom:12,
          display:"flex", gap:8, alignItems:"flex-start",
        }}>
          <span style={{ fontSize:13, flexShrink:0, color:"var(--ind-b)", fontWeight:700 }}>AI</span>
          <div style={{ fontSize:12, color:"var(--tx2)", lineHeight:1.5 }}>{receipt.ai_analysis}</div>
        </div>
      )}

      {receipt.items?.length > 0 && (
        <div style={{ background:"var(--bg3)", borderRadius:"var(--r)", padding:"8px 12px", marginBottom:12, fontSize:12 }}>
          {receipt.items.map((item, i) => (
            <div key={i} style={{ display:"flex", justifyContent:"space-between", color:"var(--tx2)", marginBottom:2 }}>
              <span>{item.name} Ã—{item.qty ?? 1}</span>
              <span style={{ fontFamily:"var(--mono)" }}>{fmt(item.total ?? item.unit_price ?? null)}</span>
            </div>
          ))}
        </div>
      )}

      {receipt.notes && (
        <div style={{ fontSize:11, color:"var(--tx3)", marginBottom:10, fontStyle:"italic" }}>{receipt.notes}</div>
      )}

      <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
        <button className="btn btn-g btn-s" onClick={() => onEdit(index)}>Edit</button>
        {!exported.has(index) ? (
          <>
            <button className="btn btn-grn btn-s" onClick={() => onExport(index, "expense")}>Export â†’ Expense</button>
            <button className="btn btn-p btn-s"   onClick={() => onExport(index, "income")}>Export â†’ Income</button>
          </>
        ) : (
          <span className="pill g">Exported to {exported.get(index)}</span>
        )}
      </div>
    </div>
  );
}

function EditModal({ receipt, onSave, onClose }) {
  const [form, setForm] = useState({
    merchant_name:    receipt.merchant_name || "",
    total_amount:     receipt.total_amount  || 0,
    transaction_date: receipt.transaction_date?.slice(0,10) || "",
    transaction_type: receipt.transaction_type || "expense",
    payment_method:   receipt.payment_method  || "cash",
    category:         receipt.category        || "other",
  });
  const [rememberMerchant, setRememberMerchant] = useState(true);
  const [remembered, setRemembered] = useState(false);
  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleSave = async () => {
    const saved = { ...receipt, ...form, total_amount: +form.total_amount };
    if (rememberMerchant && form.merchant_name && form.category) {
      await apiRememberMerchant(form.merchant_name, form.category);
      setRemembered(true);
    }
    onSave(saved);
  };

  return (
    <Modal title="Edit Receipt" onClose={onClose}
      footer={
        <>
          <button className="btn btn-g" onClick={onClose}>Cancel</button>
          <button className="btn btn-p" onClick={handleSave}>Save</button>
        </>
      }>
      <FormRow>
        <FormGroup label="Merchant"><input className="fc" value={form.merchant_name} onChange={set("merchant_name")} /></FormGroup>
        <FormGroup label="Amount (IDR)"><input className="fc" type="number" value={form.total_amount} onChange={set("total_amount")} /></FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label="Date"><input className="fc" type="date" value={form.transaction_date} onChange={set("transaction_date")} /></FormGroup>
        <FormGroup label="Type">
          <select className="fc sel" value={form.transaction_type} onChange={set("transaction_type")}>
            <option value="expense">Expense</option><option value="income">Income</option>
          </select>
        </FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label="Payment">
          <select className="fc sel" value={form.payment_method} onChange={set("payment_method")}>
            {PAY_LIST.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </FormGroup>
        <FormGroup label="Category">
          <select className="fc sel" value={form.category} onChange={set("category")}>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </FormGroup>
      </FormRow>
      {/* Merchant memory toggle */}
      <div style={{ marginTop: 12, padding: "10px 12px", borderRadius: 8,
        background: "rgba(96,165,250,.08)", border: "1px solid rgba(96,165,250,.2)",
        display: "flex", alignItems: "center", gap: 10 }}>
        <input
          type="checkbox" id="rem-merchant"
          checked={rememberMerchant}
          onChange={e => setRememberMerchant(e.target.checked)}
          style={{ accentColor: "#60a5fa", width: 14, height: 14, cursor: "pointer" }}
        />
        <label htmlFor="rem-merchant" style={{ fontSize: 12, color: "var(--tx2)", cursor: "pointer", userSelect: "none" }}>
          {remembered
            ? <span style={{ color:"#60a5fa" }}><IconCheck size={11} style={{ marginRight:4, verticalAlign:"middle" }} /> Ingat bahwa <strong>{form.merchant_name || "merchant ini"}</strong> â†’ <strong>{form.category}</strong></span>
            : <>Ingat <strong>{form.merchant_name || "merchant ini"}</strong> sebagai <strong>{form.category}</strong> untuk scan berikutnya</>
          }
        </label>
      </div>
    </Modal>
  );
}

function DropZone({ onFiles, aiMode }) {
  const [dragging, setDragging] = useState(false);
  const inputRef     = useRef(); // gallery / file picker (no capture)
  const cameraRef    = useRef(); // camera only
  const handleDrop = useCallback(e => {
    e.preventDefault(); setDragging(false);
    const files = [...e.dataTransfer.files].filter(f => f.type.startsWith("image/"));
    if (files.length) onFiles(files);
  }, [onFiles]);

  // Detect if running on mobile (touch device) for showing camera button
  const isMobile = typeof window !== "undefined" && ("ontouchstart" in window || navigator.maxTouchPoints > 0);

  return (
    <div className={`drop-zone${dragging ? " drag-over" : ""}`}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      style={{ cursor: "default" }}>
      {/* hidden inputs */}
      <input ref={inputRef} type="file" accept="image/*" multiple
        style={{ display:"none" }} onChange={e => onFiles([...e.target.files])} />
      {isMobile && (
        <input ref={cameraRef} type="file" accept="image/*" capture="environment"
          style={{ display:"none" }} onChange={e => onFiles([...e.target.files])} />
      )}

      <div className="dz-ico" style={{ display:"flex", justifyContent:"center", marginBottom:10 }}>
        <IconCamera size={36} color="var(--tx3)" />
      </div>
      <div className="dz-txt" style={{ textAlign: "center", lineHeight: 1.6 }}>
        <div><strong>Upload Document (PNG/JPG/WebP)</strong></div>
        <div style={{ display:"flex", justifyContent:"center", gap:6, marginTop:8, flexWrap:"wrap" }}>
          <span style={{ fontSize:10, padding:"2px 8px", borderRadius:99, background:"var(--bg3)", color:"var(--tx2)", border:"1px solid var(--bdr)", display:"inline-flex", alignItems:"center", gap:4 }}><IconFile size={11} /> Invoice / Faktur</span>
          <span style={{ fontSize:10, padding:"2px 8px", borderRadius:99, background:"var(--bg3)", color:"var(--tx2)", border:"1px solid var(--bdr)", display:"inline-flex", alignItems:"center", gap:4 }}><IconRecords size={11} /> Kwitansi</span>
          <span style={{ fontSize:10, padding:"2px 8px", borderRadius:99, background:"var(--bg3)", color:"var(--tx2)", border:"1px solid var(--bdr)", display:"inline-flex", alignItems:"center", gap:4 }}><IconScan size={11} /> Struk / Receipt</span>
          <span style={{ fontSize:10, padding:"2px 8px", borderRadius:99, background:"var(--bg3)", color:"var(--tx2)", border:"1px solid var(--bdr)", display:"inline-flex", alignItems:"center", gap:4 }}><IconBarChart size={11} /> Mutasi Rekening</span>
          <span style={{ fontSize:10, padding:"2px 8px", borderRadius:99, background:"var(--bg3)", color:"var(--tx2)", border:"1px solid var(--bdr)", display:"inline-flex", alignItems:"center", gap:4 }}><IconIncome size={11} /> Bukti Transfer Bank</span>
        </div>
        {aiMode && (
          <div style={{ display:"flex", justifyContent:"center", gap:6, marginTop:6, flexWrap:"wrap" }}>
            <span style={{ display:"inline-flex", alignItems:"center", padding:"2px 8px", borderRadius:99, fontSize:10, fontWeight:700,
              background:"rgba(167,139,250,.15)", color:"var(--pu)", border:"1px solid rgba(167,139,250,.3)", whiteSpace:"nowrap" }}>
              Claude Vision AI
            </span>
          </div>
        )}
      </div>

      {/* Action buttons â€” Gallery + Camera on mobile, single file picker on desktop */}
      <div style={{ display:"flex", justifyContent:"center", gap:8, marginTop:14, flexWrap:"wrap" }}>
        <button className="btn btn-p btn-s" style={{ gap:5 }}
          onClick={e => { e.stopPropagation(); inputRef.current.click(); }}>
          <IconCamera size={13} /> Pilih dari Galeri
        </button>
        {isMobile && (
          <button className="btn btn-g btn-s" style={{ gap:5 }}
            onClick={e => { e.stopPropagation(); cameraRef.current.click(); }}>
            <IconCamera size={13} /> Buka Kamera
          </button>
        )}
      </div>
      <div style={{ fontSize:11, color:"var(--tx3)", marginTop:8, textAlign:"center" }}>atau seret &amp; lepas foto di sini</div>
    </div>
  );
}

function ModeBadge({ selected, onSelect, status }) {
  const [open, setOpen] = useState(false);

  const OPTIONS = [
    { id: "auto",      label: "AI Auto",       icon: <IconSparkles size={14} />, desc: "Otomatis pilih Claude/Gemini/Ollama", color: "var(--pu)" },
    { id: "claude",    label: "Vision Claude",  icon: <IconScan size={14} />, desc: "Claude 3.5 Opus (Akurasi tertinggi)", color: "#a78bfa" },
    { id: "gemini",    label: "Gemini 2.5 Flash",  icon: <IconFlash size={14} />, desc: "Gemini 2.5 Flash (Tercepat & Stabil)", color: "#4f46e5" },
    { id: "ollama",    label: "Vision Ollama",  icon: <IconML size={14} />, desc: "Local LLM (Ollama Vision)", color: "#34d399" },
    { id: "rules",     label: "OCR Offline",    icon: <IconRecords size={14} />, desc: "Rule Engine (Tanpa AI)", color: "#60a5fa" },
    { id: "Tesseract", label: "OCR Tesseract", icon: <IconFile size={14} />, desc: "Legacy OCR — Printed text", color: "var(--tx2)" },
    { id: "EasyOCR",   label: "OCR EasyOCR",   icon: <IconFile size={14} />, desc: "Legacy OCR — Stylized text", color: "var(--tx2)" },
    { id: "PaddleOCR", label: "OCR PaddleOCR", icon: <IconFile size={14} />, desc: "Legacy OCR — Documentation", color: "var(--tx2)" },
  ];

  const current = OPTIONS.find(o => o.id === selected) || OPTIONS[0];

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        onClick={() => setOpen(!open)}
        className="mode-badge"
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "5px 12px", borderRadius: 99, fontSize: 11, fontWeight: 700,
          background: `${current.color}15`, color: current.color,
          border: `1px solid ${current.color}30`, cursor: "pointer", outline: "none"
        }}
      >
        <span style={{ display: "flex", alignItems: "center" }}>{current.icon}</span>
        {current.label}
        <span style={{ fontSize: 8, opacity: 0.6 }}>▼</span>
      </button>

      {open && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 100 }} onClick={() => setOpen(false)} />
          <div style={{
            position: "absolute", top: "calc(100% + 8px)", left: 0, zIndex: 101,
            background: "var(--bg2)", border: "1px solid var(--bdr2)", borderRadius: 12,
            padding: "6px 0", minWidth: 240, boxShadow: "0 8px 32px rgba(0,0,0,.3)"
          }}>
            <div style={{ padding: "8px 14px", borderBottom: "1px solid var(--bdr)", marginBottom: 4 }}>
              <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".8px", color: "var(--tx3)" }}>
                Pilih Engine Scan Struk
              </div>
              <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 2 }}>
                {status?.active === "none" && !["Tesseract", "EasyOCR", "PaddleOCR"].includes(selected) 
                  ? "AI tidak aktif — gunakan OCR Legacy atau Rule Engine" 
                  : "Pilih mode yang sesuai dengan kualitas struk"}
              </div>
            </div>
            {OPTIONS.map(opt => (
              <button
                key={opt.id}
                onClick={() => { onSelect(opt.id); setOpen(false); }}
                style={{
                  display: "flex", width: "100%", textAlign: "left", alignItems: "center",
                  padding: "10px 14px", background: selected === opt.id ? "var(--sb-act)" : "transparent",
                  border: "none", cursor: "pointer", gap: 10
                }}
              >
                <span style={{ display: "flex", alignItems: "center" }}>{opt.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: selected === opt.id ? 700 : 400, color: selected === opt.id ? opt.color : "var(--tx)" }}>
                    {opt.label}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 1 }}>{opt.desc}</div>
                </div>
                {selected === opt.id && <IconCheck size={11} color={opt.color} />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function InfoTooltip({ text }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: "relative", display: "inline-flex" }}>
      <IconInfo 
        size={12} 
        style={{ cursor: "help", color: "var(--tx3)", opacity: 0.7 }}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)",
          background: "rgba(0,0,0,0.85)", color: "#fff", padding: "6px 10px", borderRadius: 6,
          fontSize: 10, lineHeight: 1.4, whiteSpace: "nowrap", zIndex: 1000, pointerEvents: "none",
          boxShadow: "0 4px 12px rgba(0,0,0,0.2)"
        }}>
          {text}
          <div style={{
            position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)",
            border: "5px solid transparent", borderTopColor: "rgba(0,0,0,0.85)"
          }} />
        </div>
      )}
    </div>
  );
}

export default function ReceiptReader({ onToast }) {
  const [receipts,    setReceipts]  = useState([]);
  const [scanning,    setScanning]  = useState(false);
  const [scanError,   setScanError] = useState(null);
  const [scanProgress, setProgress] = useState({ done:0, total:0 });
  const [editIdx,     setEditIdx]   = useState(null);
  const [exported,    setExported]  = useState(new Map());
  const [aiAvailable, setAiAvailable] = useState(null);
  const [showStatus, setShowStatus] = useState(false);
  const [selectedEngine, setSelectedEngine] = useState(() => {
    try { return localStorage.getItem("ft:ocr_engine") || "auto"; } catch { return "auto"; }
  });

  const { status: aiStatus, loading: aiStatusLoading, setProvider } = useAIStatus();

  const handleEngineChange = val => {
    setSelectedEngine(val);
    try { localStorage.setItem("ft:ocr_engine", val); } catch {}
    // If user selects a specific AI provider, try to switch global provider too
    if (["claude", "gemini", "ollama", "rules"].includes(val)) {
      setProvider(val);
    } else if (val === "auto") {
      setProvider("auto");
    }
  };

  const handleFiles = async files => {
    setScanning(true);
    setScanError(null);
    setProgress({ done:0, total:files.length });
    const results = [];
    const t0_batch = Date.now();
    let lastErr = null;

    for (let i = 0; i < files.length; i++) {
      setProgress({ done:i, total:files.length });
      const t0 = Date.now();
      try {
        let res;
        // Determine path: AI vs Legacy
        const isLegacy = ["Tesseract", "EasyOCR", "PaddleOCR"].includes(selectedEngine);
        
        if (isLegacy) {
          res = await apiScanReceipt(files[i], selectedEngine);
        } else {
          // AI path (auto, claude, gemini, ollama, rules)
          try {
            res = await apiScanReceiptAI(files[i], selectedEngine === "auto" ? null : selectedEngine);
            if (res.ok !== false) setAiAvailable(true);
          } catch (aiErr) {
            if (selectedEngine === "auto" && (aiErr.message?.includes("503") || aiErr.message?.includes("ANTHROPIC"))) {
              setAiAvailable(false);
              res = await apiScanReceipt(files[i]);
            } else throw aiErr;
          }
        }

        if (res.ok && res.receipts?.length) {
          const elapsed = (Date.now() - t0) / 1000;
          results.push(...res.receipts.map(r => ({ 
            ...r, 
            _aiPowered: res.ai_powered,
            _processingTime: elapsed 
          })));
        } else {
          lastErr = `${files[i].name}: ${res.error || "No data parsed"}`;
          onToast(lastErr, "error");
        }
      } catch (e) {
        lastErr = `${files[i].name}: ${e.message}`;
        onToast(lastErr, "error");
      }
    }
    setProgress({ done:files.length, total:files.length });
    setScanning(false);

    if (lastErr && results.length === 0) {
      setScanError(lastErr);
    }

    if (results.length) {
      setReceipts(p => [...results, ...p]);
      const totalElapsed = ((Date.now() - t0_batch) / 1000).toFixed(1);
      const labels = {
        auto: "AI Auto", claude: "Vision Claude", gemini: "Vision Gemini",
        ollama: "Vision Ollama", rules: "OCR Offline",
        Tesseract: "OCR Tesseract", EasyOCR: "OCR EasyOCR", PaddleOCR: "OCR PaddleOCR"
      };
      const method = labels[selectedEngine] || (results[0]?._aiPowered ? "AI" : "OCR");
      onToast(`${results.length} receipt(s) diproses dengan ${method} dalam ${totalElapsed}s.`);
    }
  };

  const handleExport = async (idx, target) => {
    try {
      await apiExportReceipt(target, receipts[idx]);
      setExported(m => new Map(m).set(idx, target));
      onToast(`Exported to ${target} tracker.`);
    } catch (e) { onToast("Export failed: " + e.message, "error"); }
  };

  const handleSaveEdit = updated => {
    setReceipts(p => p.map((r, i) => i === editIdx ? updated : r));
    setEditIdx(null);
  };

  const handleExportAll = async () => {
    let count = 0;
    for (let i = 0; i < receipts.length; i++) {
      if (exported.has(i)) continue;
      const target = receipts[i].transaction_type === "income" ? "income" : "expense";
      try { await apiExportReceipt(target, receipts[i]); setExported(m => new Map(m).set(i, target)); count++; }
      catch { /* skip */ }
    }
    onToast(`Exported ${count} receipts.`);
  };

  return (
    <div>
      <h1 className="sr-only">Receipt Reader — AI-Powered OCR for Expense Scanning</h1>
      {/* AI provider status &amp; OCR Engine Selector — Unified ModeBadge */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:16, flexWrap:"wrap", gap:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <ModeBadge selected={selectedEngine} onSelect={handleEngineChange} status={aiStatus} />
          <AIPassiveStatus status={aiStatus} loading={aiStatusLoading} />
        </div>
        
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          {/* Action buttons could go here if needed, or leave empty for cleaner look */}
        </div>
      </div>

      <DropZone 
        onFiles={handleFiles} 
        aiMode={!["Tesseract", "EasyOCR", "PaddleOCR"].includes(selectedEngine) && aiAvailable !== false} 
      />

      {scanError && (
        <div style={{
          background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.25)",
          borderRadius: "var(--r)", padding: "14px 18px", marginTop: 14,
          display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--rd)", display: "flex", alignItems: "center", gap: 6 }}>
              <IconWarning size={15} color="var(--rd)" /> Gagal Membaca Struk
            </div>
            <div style={{ fontSize: 11, color: "var(--tx2)", marginTop: 2 }}>
              {typeof scanError === "string" ? scanError : scanError?.message || String(scanError)}
            </div>
          </div>
          <button className="btn btn-g btn-s" onClick={() => setScanError(null)}>Tutup</button>
        </div>
      )}

      {scanning && (
        <div style={{ background:"var(--ind-d)", border:"1px solid rgba(79,110,247,.3)", borderRadius:"var(--r)", padding:"14px 18px", marginTop:14, display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ width:20, height:20, borderRadius:"50%", border:"2px solid var(--ind-b)", borderTopColor:"transparent", animation:"spin 1s linear infinite", flexShrink:0 }} />
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ fontSize:13, fontWeight:600 }}>
              {aiStatus?.active === "claude" ? "Claude Vision sedang membaca struk..."
               : aiStatus?.active === "gemini" ? "Gemini sedang membaca struk..."
               : aiStatus?.active === "ollama" ? "Ollama sedang menganalisis struk..."
               : aiStatus?.active === "rules" ? "Rule Engine sedang memproses struk..."
               : "Scanning receipts..."}
            </div>
            <div style={{ fontSize:11, color:"var(--tx2)", marginTop:2 }}>{scanProgress.done} / {scanProgress.total} diproses</div>
          </div>          <div style={{ width:80, flexShrink:0 }}>
            <div className="prog-wrap">
              <div className="prog-fill" style={{ width:`${scanProgress.total > 0 ? scanProgress.done/scanProgress.total*100 : 0}%`, background:"var(--ind)" }} />
            </div>
          </div>
        </div>
      )}

      {receipts.length > 0 && (
        <div style={{ marginTop:20 }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14, flexWrap:"wrap", gap:8 }}>
            <div style={{ fontSize:13, color:"var(--tx2)" }}>
              <strong style={{ color:"var(--tx)" }}>{receipts.length}</strong> receipt(s) ·{" "}
              <span style={{ color:"var(--gr)" }}>{[...exported.values()].filter(v => v==="income").length} income</span> ·{" "}
              <span style={{ color:"var(--rd)" }}>{[...exported.values()].filter(v => v==="expense").length} expense</span> exported
            </div>
            <div style={{ display:"flex", gap:8 }}>
              <button className="btn btn-g btn-s" onClick={() => { setReceipts([]); setExported(new Map()); }}>Clear</button>
              <button className="btn btn-p btn-s" onClick={handleExportAll}>Export All</button>
            </div>
          </div>
          {receipts.map((r, i) => (
            <ReceiptCard key={i} receipt={r} index={i} onEdit={setEditIdx} onExport={handleExport} exported={exported} />
          ))}
        </div>
      )}

      {!scanning && receipts.length === 0 && (
        <div style={{ marginTop:24 }}>
          <div style={{ background:"var(--bg2)", border:"1px solid var(--bdr)", borderRadius:"var(--rl)", padding:24 }}>
            <div style={{ fontSize:13, fontWeight:700, marginBottom:12, color:"var(--tx2)", textTransform:"uppercase", letterSpacing:".8px" }}>How to Use</div>
            {[
              ["1.", "Upload struk foto",      "PNG/JPG/WebP â€” foto kamera atau screenshot"],
              ["2.", "AI membaca struk",        "Claude/Gemini/Ollama menganalisis gambar, tidak perlu OCR manual"],
              ["3.", "Ekstraksi otomatis",      "Nama merchant, jumlah, tanggal, metode bayar, kategori + insight AI"],
              ["4.", "Edit jika perlu",         "Klik Edit untuk koreksi data sebelum export"],
              ["5.", "Export ke tracker",       "Langsung masuk ke DB Expense/Income yang sama dengan CLI"],
            ].map(([num, title, desc]) => (
              <div key={num} style={{ display:"flex", gap:12, marginBottom:12 }}>
                <span style={{ fontSize:14, flexShrink:0, fontFamily:"var(--mono)", color:"var(--ind-b)", fontWeight:700 }}>{num}</span>
                <div>
                  <div style={{ fontSize:13, fontWeight:600 }}>{title}</div>
                  <div style={{ fontSize:11, color:"var(--tx3)", marginTop:2 }}>{desc}</div>
                </div>
              </div>
            ))}
            {/* AI Key requirement info removed from here as it is now in the subtle status badge */}
            </div>
            </div>
            )}

      {editIdx !== null && (
        <EditModal receipt={receipts[editIdx]} onSave={handleSaveEdit} onClose={() => setEditIdx(null)} />
      )}
    </div>
  );
}

