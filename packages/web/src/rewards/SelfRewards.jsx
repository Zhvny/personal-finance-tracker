// ─── SelfRewards.jsx ──────────────────────────────────────────────────────────
// Self-Reward system: users create personal goal rewards to spend Reward points.
// Zero emojis — all icons from ../icons.jsx.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from "react";
import { fetchSelfRewards, createSelfReward, redeemSelfReward, deleteSelfReward } from "./rewardStore.js";
import { IconGift, IconAward, IconTarget, IconSparkles, IconStar, IconCoin, IconCheck } from "../icons.jsx";

const CATEGORY_OPTIONS = [
  { id: "gift", label: "Gift", Icon: IconGift },
  { id: "award", label: "Treat", Icon: IconAward },
  { id: "target", label: "Goal", Icon: IconTarget },
  { id: "sparkles", label: "Special", Icon: IconSparkles },
  { id: "star", label: "Personal", Icon: IconStar },
];

function SelfRewardCard({ reward, rewardPoints, onRedeem, onDelete, loading }) {
  const canAfford = !reward.redeemed && (reward.costType !== "reward" || rewardPoints >= reward.cost);
  const isRedeemed = reward.redeemed;

  const matchedCat = CATEGORY_OPTIONS.find(c => c.id === reward.icon) || CATEGORY_OPTIONS[0];
  const CategoryIcon = matchedCat.Icon;

  return (
    <div
      className={`sr-card ${isRedeemed ? "sr-card--redeemed" : ""} ${!canAfford && !isRedeemed ? "sr-card--locked" : ""}`}
      title={reward.description || reward.title}
    >
      <div className="sr-card-icon">
        <CategoryIcon size={20} color="var(--gp-fire2)" />
      </div>
      <div className="sr-card-body">
        <div className="sr-card-title">{reward.title}</div>
        {reward.description && (
          <div className="sr-card-desc">{reward.description}</div>
        )}
        <div className="sr-card-cost">
          {reward.costType === "reward"
            ? <span className="sr-cost-reward"><IconCoin size={11} color="var(--gp-fire2)" /> {reward.cost} Reward</span>
            : <span className="sr-cost-savings">Savings Goal</span>
          }
        </div>
      </div>
      <div className="sr-card-actions">
        {isRedeemed ? (
          <span className="sr-badge-redeemed" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <IconCheck size={11} /> Redeemed
          </span>
        ) : (
          <button
            className={`sr-btn-redeem ${!canAfford ? "sr-btn-redeem--disabled" : ""}`}
            onClick={() => canAfford && onRedeem(reward.id)}
            disabled={!canAfford || loading}
            title={canAfford ? "Redeem this reward" : `Need ${reward.cost} Reward (you have ${rewardPoints})`}
          >
            {canAfford ? "Redeem" : `Need ${reward.cost}`}
          </button>
        )}
        <button
          className="sr-btn-delete"
          onClick={() => onDelete(reward.id)}
          disabled={loading}
          title="Remove reward"
          aria-label="Remove reward"
        >
          ×
        </button>
      </div>
    </div>
  );
}

function CreateRewardForm({ onCreated, onCancel, loading, setLoading }) {
  const [form, setForm] = useState({ title: "", cost: 50, costType: "reward", description: "", icon: "gift" });
  const [err, setErr] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) { setErr("Title is required"); return; }
    if (form.cost <= 0) { setErr("Cost must be positive"); return; }
    setErr("");
    setLoading(true);
    try {
      const result = await createSelfReward(form);
      onCreated(result);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="sr-create-form" onSubmit={handleSubmit} noValidate>
      <div className="sr-create-header">Create Self-Reward</div>

      <div className="sr-form-row">
        <label className="sr-label">Category Icon</label>
        <div className="sr-emoji-picker">
          {CATEGORY_OPTIONS.map(cat => {
            const CatIcon = cat.Icon;
            const isSelected = form.icon === cat.id;
            return (
              <button
                key={cat.id} type="button"
                className={`sr-emoji-opt ${isSelected ? "selected" : ""}`}
                onClick={() => setForm(f => ({ ...f, icon: cat.id }))}
                title={cat.label}
              >
                <CatIcon size={16} color={isSelected ? "var(--gp-fire2)" : "var(--gp-tx2)"} />
              </button>
            );
          })}
        </div>
      </div>

      <div className="sr-form-row">
        <label className="sr-label">Title</label>
        <input
          className="sr-input"
          type="text"
          placeholder="e.g. Caramel Macchiato"
          value={form.title}
          onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
          maxLength={60}
          required
        />
      </div>

      <div className="sr-form-row sr-form-row--half">
        <div>
          <label className="sr-label">Cost Type</label>
          <select
            className="sr-select"
            value={form.costType}
            onChange={e => setForm(f => ({ ...f, costType: e.target.value }))}
          >
            <option value="reward">Reward Points</option>
            <option value="savings">Savings (Memo)</option>
          </select>
        </div>
        <div>
          <label className="sr-label">{form.costType === "reward" ? "Reward Cost" : "Amount"}</label>
          <input
            className="sr-input"
            type="number"
            min={1}
            value={form.cost}
            onChange={e => setForm(f => ({ ...f, cost: Number(e.target.value) }))}
          />
        </div>
      </div>

      <div className="sr-form-row">
        <label className="sr-label">Description <span style={{ opacity: 0.5 }}>(optional)</span></label>
        <input
          className="sr-input"
          type="text"
          placeholder="Why do you deserve this?"
          value={form.description}
          onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          maxLength={120}
        />
      </div>

      {err && <div className="sr-form-err">{err}</div>}

      <div className="sr-form-btns">
        <button type="button" className="sr-btn-cancel" onClick={onCancel} disabled={loading}>Cancel</button>
        <button type="submit" className="sr-btn-create" disabled={loading}>
          {loading ? "Creating…" : "Create Reward"}
        </button>
      </div>
    </form>
  );
}

export default function SelfRewards({ rewardPoints = 0 }) {
  const [rewards, setRewards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [toast, setToast] = useState(null);
  const [filter, setFilter] = useState("all"); // all | active | redeemed

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3200);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchSelfRewards();
      setRewards(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreated = (result) => {
    setRewards(result.state?.selfRewards ?? rewards);
    setShowForm(false);
    showToast("Self-reward created!");
  };

  const handleRedeem = async (id) => {
    setLoading(true);
    try {
      const result = await redeemSelfReward(id);
      setRewards(result.state?.selfRewards ?? rewards);
      showToast("Reward redeemed! You earned it.");
    } catch (ex) {
      showToast(ex.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Remove this self-reward?")) return;
    setLoading(true);
    try {
      const result = await deleteSelfReward(id);
      setRewards(result.state?.selfRewards ?? rewards);
      showToast("Reward removed.");
    } catch (ex) {
      showToast(ex.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const filtered = rewards.filter(r => {
    if (filter === "active")  return !r.redeemed;
    if (filter === "redeemed") return  r.redeemed;
    return true;
  });

  return (
    <div className="sr-root">
      {/* Toast */}
      {toast && (
        <div className={`sr-toast sr-toast--${toast.type}`}>{toast.msg}</div>
      )}

      {/* Header */}
      <div className="sr-header">
        <div className="sr-header-left">
          <span className="sr-title">Self-Rewards</span>
          <span className="sr-subtitle">
            Spend your <strong>{rewardPoints}</strong> Reward points on personal goals
          </span>
        </div>
        <button
          className="sr-btn-new"
          onClick={() => setShowForm(true)}
          disabled={showForm}
        >
          + New Reward
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <CreateRewardForm
          onCreated={handleCreated}
          onCancel={() => setShowForm(false)}
          loading={loading}
          setLoading={setLoading}
        />
      )}

      {/* Filter tabs */}
      {rewards.length > 0 && (
        <div className="sr-filter-tabs">
          {[["all","All"],["active","Active"],["redeemed","Redeemed"]].map(([val, label]) => (
            <button
              key={val}
              className={`sr-filter-tab ${filter === val ? "active" : ""}`}
              onClick={() => setFilter(val)}
            >{label}</button>
          ))}
        </div>
      )}

      {/* Reward list */}
      {loading && rewards.length === 0 ? (
        <div className="sr-empty">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="sr-empty">
          {rewards.length === 0
            ? <>No self-rewards yet. Create one to motivate yourself!</>
            : <>No {filter} rewards.</>}
        </div>
      ) : (
        <div className="sr-list">
          {filtered.map(r => (
            <SelfRewardCard
              key={r.id}
              reward={r}
              rewardPoints={rewardPoints}
              onRedeem={handleRedeem}
              onDelete={handleDelete}
              loading={loading}
            />
          ))}
        </div>
      )}
    </div>
  );
}
