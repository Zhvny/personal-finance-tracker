"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, User, Briefcase, Plus, RefreshCw, Check } from "lucide-react";
import { clientProxyUrl } from "@/lib/api";

interface ProfileCreatorProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
  existingProfiles: string[];
}

type ProfileUseType = "personal" | "business";

export function ProfileCreatorModal({
  isOpen,
  onClose,
  onCreated,
  existingProfiles,
}: ProfileCreatorProps) {
  const [name, setName] = useState("");
  const [useType, setUseType] = useState<ProfileUseType>("personal");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const reset = () => {
    setName("");
    setUseType("personal");
    setError(null);
    setSuccess(false);
    setSubmitting(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmed = name.trim().toLowerCase();
    if (!trimmed) {
      setError("Profile name is required.");
      return;
    }
    if (trimmed.length > 32) {
      setError("Profile name must be 32 characters or fewer.");
      return;
    }
    const RESERVED = ['admin', 'root', 'system', 'api', 'null', 'undefined', 'default', 'config', 'test', 'qa'];
    if (RESERVED.includes(trimmed)) {
      setError("This profile name is reserved. Choose a different name.");
      return;
    }
    if (existingProfiles.includes(trimmed)) {
      setError(`Profile "${trimmed}" already exists.`);
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(clientProxyUrl("api/profile/create"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed, type: useType }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${res.status}`);
      }

      setSuccess(true);
      setTimeout(() => {
        handleClose();
        onCreated();
      }, 900);
    } catch (err: any) {
      setError(err.message || "Failed to create profile.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
            onClick={handleClose}
            aria-hidden="true"
          />

          {/* Modal */}
          <motion.div
            key="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-profile-title"
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ type: "spring", stiffness: 420, damping: 30 }}
            className="fixed z-[70] left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
              w-full max-w-sm mx-auto
              bg-background border border-border rounded-2xl shadow-2xl shadow-black/15
              overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
              <div>
                <h2
                  id="create-profile-title"
                  className="text-sm font-semibold text-foreground"
                >
                  New Profile
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Choose a use type before creating
                </p>
              </div>
              <button
                onClick={handleClose}
                aria-label="Close"
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground
                  hover:bg-muted transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-5">
              {/* Use-type selector */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2.5">
                  Profile Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {(["personal", "business"] as ProfileUseType[]).map((type) => {
                    const isSelected = useType === type;
                    const isBiz = type === "business";
                    return (
                      <button
                        key={type}
                        type="button"
                        onClick={() => setUseType(type)}
                        className={`relative flex flex-col items-start gap-2 p-3.5 rounded-xl border
                          text-left transition-all duration-150
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                          ${
                            isSelected
                              ? isBiz
                                ? "bg-amber-50 dark:bg-amber-950/30 border-amber-300 dark:border-amber-700/60"
                                : "bg-foreground/5 border-foreground/25"
                              : "border-border/60 hover:border-border hover:bg-muted/40"
                          }`}
                      >
                        {/* Check indicator */}
                        {isSelected && (
                          <div
                            className={`absolute top-2.5 right-2.5 h-4 w-4 rounded-full
                              flex items-center justify-center
                              ${
                                isBiz
                                  ? "bg-amber-500 text-white"
                                  : "bg-foreground text-background"
                              }`}
                          >
                            <Check size={10} strokeWidth={3} />
                          </div>
                        )}

                        {/* Icon */}
                        <div
                          className={`h-7 w-7 rounded-lg flex items-center justify-center
                            ${
                              isBiz
                                ? "bg-amber-100 dark:bg-amber-900/50"
                                : "bg-muted"
                            }`}
                        >
                          {isBiz ? (
                            <Briefcase
                              size={14}
                              className="text-amber-700 dark:text-amber-400"
                              strokeWidth={2}
                            />
                          ) : (
                            <User
                              size={14}
                              className="text-muted-foreground"
                              strokeWidth={2}
                            />
                          )}
                        </div>

                        <div>
                          <p className="text-sm font-semibold leading-tight">
                            {isBiz ? "Business" : "Personal"}
                          </p>
                          <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
                            {isBiz
                              ? "BI/BA cockpit, project analytics, EVM"
                              : "Expenses, income, investments"}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Profile name */}
              <div>
                <label
                  htmlFor="profile-name-input"
                  className="block text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2"
                >
                  Profile Name
                </label>
                <input
                  id="profile-name-input"
                  type="text"
                  value={name}
                  onChange={(e) => {
                    const raw = e.target.value.toLowerCase();
                    const sanitized = raw.replace(/[^a-z0-9_]/g, '').slice(0, 32);
                    setName(sanitized);
                  }}
                  placeholder="e.g. work, freelance, personal"
                  autoComplete="off"
                  spellCheck={false}
                  maxLength={32}
                  className="w-full h-10 px-3.5 rounded-xl border border-border/70 bg-muted/30
                    text-sm text-foreground placeholder:text-muted-foreground/60
                    focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent
                    transition-colors"
                />
                <p className="mt-1 text-[10px] text-muted-foreground text-right">{name.length}/32</p>
                {error && (
                  <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>
                )}
              </div>

              {/* Business note */}
              {useType === "business" && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="rounded-xl bg-amber-50 dark:bg-amber-950/20
                    border border-amber-200/70 dark:border-amber-800/40 px-3.5 py-3"
                >
                  <p className="text-[11px] text-amber-700 dark:text-amber-400 leading-relaxed">
                    Business profiles include the BI/BA Cockpit with Investment
                    Tracker, Expense Tracker, Income Tracker, and Receipt Reader
                    aligned with project analytics.
                  </p>
                </motion.div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={submitting || success}
                className={`w-full h-10 rounded-xl text-sm font-semibold
                  flex items-center justify-center gap-2
                  transition-all duration-150
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                  disabled:opacity-60 disabled:cursor-not-allowed
                  ${
                    success
                      ? "bg-emerald-500 text-white"
                      : useType === "business"
                      ? "bg-amber-500 hover:bg-amber-600 text-white"
                      : "bg-foreground text-background hover:bg-foreground/90"
                  }`}
              >
                {success ? (
                  <>
                    <Check size={15} strokeWidth={2.5} />
                    Profile Created
                  </>
                ) : submitting ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus size={14} strokeWidth={2.5} />
                    Create {useType === "business" ? "Business" : "Personal"} Profile
                  </>
                )}
              </button>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
