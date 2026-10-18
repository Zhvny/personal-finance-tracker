"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Brain,
  Gift,
  Terminal,
  Building2,
  Activity,
  X,
  ContactRound,
  RefreshCw,
  ChevronDown,
  Check,
  Plus,
} from "lucide-react";
import { ProfileCreatorModal } from "@/components/ui/profile-creator-modal";
import { clientProxyUrl } from "@/lib/api";
import { useI18n } from "@/i18n/context";

// ── Types ────────────────────────────────────────────────────────────────────

interface ProfileData {
  active: string;
  active_type: "personal" | "business";
  available: string[];
  types: Record<string, string>;
}

// ── Navigation definitions ────────────────────────────────────────────────────

const PERSONAL_NAV = [
  { name: "Overview",   key: "nav.overview",   href: "/overview",  icon: Activity        },
  { name: "Analytics",  key: "nav.analytics",  href: "/analytics", icon: LayoutDashboard },
  { name: "Behavioral", key: "nav.behavioral", href: "/behavioral", icon: Brain          },
  { name: "Reward",     key: "nav.reward",     href: "/reward",     icon: Gift           },
  { name: "Log Cockpit", key: "nav.logs",       href: "/logs",      icon: Terminal       },
];

const BUSINESS_ONLY_NAV = [
  { name: "Business Cockpit", key: "nav.business", href: "/business", icon: Building2 },
];

// ── Profile Card ─────────────────────────────────────────────────────────────

function ActiveProfileCard({
  profile,
  onRefresh,
}: {
  profile: ProfileData | null;
  onRefresh: () => void;
}) {
  const router = useRouter();
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [switching, setSwitching] = useState<string | null>(null);
  const [creatorOpen, setCreatorOpen] = useState(false);

  const handleSwitch = useCallback(
    async (name: string) => {
      if (name === profile?.active) {
        setSwitcherOpen(false);
        return;
      }
      setSwitching(name);
      try {
        await fetch(clientProxyUrl("api/profile/switch"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: name }),
        });
        setSwitcherOpen(false);
        router.refresh();
      } catch {
        // silently fail, UI will auto-refetch
      } finally {
        setSwitching(null);
      }
    },
    [profile, router]
  );

  if (!profile) {
    // Loading skeleton
    return (
      <div className="p-3 border-t border-border/60">
        <div className="p-3.5 rounded-xl bg-muted/30 border border-border/50 animate-pulse">
          <div className="h-3 w-24 bg-muted rounded mb-3" />
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-muted shrink-0" />
            <div className="space-y-1.5 flex-1">
              <div className="h-3 w-20 bg-muted rounded" />
              <div className="h-2.5 w-14 bg-muted rounded" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  const isBusiness = profile.active_type === "business";
  const displayName =
    (profile.active.charAt(0).toUpperCase() + profile.active.slice(1)).slice(0, 32);

  return (
    <div className="p-3 border-t border-border/60">
      <div className="relative">
        <button
          onClick={() => setSwitcherOpen((v) => !v)}
          aria-label="Switch profile"
          aria-expanded={switcherOpen}
          className={`w-full text-left p-3 rounded-2xl border transition-all duration-200 shadow-sm
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
            ${
              isBusiness
                ? "bg-gradient-to-r from-amber-500/10 via-card to-card border-amber-500/30 hover:border-amber-500/50"
                : "bg-card border-border/70 hover:border-border hover:bg-muted/40"
            }`}
        >
          {/* Label & Type Badge row */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
              Profile
            </span>
            <span
              className={`inline-flex items-center justify-center p-1 rounded-full text-[9px] font-bold
                ${
                  isBusiness
                    ? "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30"
                    : "bg-emerald-500/15 text-emerald-500 border border-emerald-500/30"
                }`}
              title={isBusiness ? "Business Profile" : "Personal Profile"}
            >
              {isBusiness ? (
                <Building2 size={10} strokeWidth={2.5} />
              ) : (
                <ContactRound size={10} strokeWidth={2.5} />
              )}
            </span>
          </div>

          {/* Profile identity & switcher indicator */}
          <div className="flex items-center justify-between gap-2.5">
            <div className="flex items-center gap-2.5 min-w-0">
              <div
                className={`h-8 w-8 rounded-lg shrink-0 flex items-center justify-center border shadow-xs
                  ${
                    isBusiness
                      ? "bg-amber-500/20 border-amber-500/30 text-amber-600 dark:text-amber-400"
                      : "bg-foreground/5 border-border text-foreground"
                  }`}
              >
                {isBusiness ? (
                  <Building2 size={15} strokeWidth={2} />
                ) : (
                  <ContactRound size={15} strokeWidth={2} />
                )}
              </div>

              <div className="min-w-0">
                <p className="text-sm font-bold truncate leading-snug">
                  {displayName}
                </p>
                <p className="text-[10px] text-muted-foreground font-medium">
                  {profile.available.length} active profile{profile.available.length !== 1 ? "s" : ""}
                </p>
              </div>
            </div>

            <div className="h-6 w-6 rounded-lg bg-muted/60 flex items-center justify-center shrink-0 text-muted-foreground">
              <ChevronDown
                size={13}
                className={`transition-transform duration-200 ${
                  switcherOpen ? "rotate-180 text-foreground" : ""
                }`}
              />
            </div>
          </div>
        </button>

        {/* Switcher dropdown */}
        <AnimatePresence>
          {switcherOpen && (
            <motion.div
              key="switcher"
              initial={{ opacity: 0, y: -6, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.97 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              className="absolute bottom-full left-0 right-0 mb-1.5 z-50 rounded-xl
                bg-background/95 backdrop-blur-sm border border-border shadow-lg shadow-black/10 overflow-hidden"
            >
              <div className="p-1.5">
                <p className="px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Switch Profile
                </p>
                {profile.available.map((name) => {
                  const type = profile.types[name] ?? "personal";
                  const isActive = name === profile.active;
                  const isBiz = type === "business";
                  const label =
                    (name.charAt(0).toUpperCase() + name.slice(1)).slice(0, 32);
                  return (
                    <button
                      key={name}
                      onClick={() => handleSwitch(name)}
                      disabled={switching !== null}
                      className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm
                        transition-colors duration-100
                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                        ${
                          isActive
                            ? "bg-foreground/8 font-medium"
                            : "hover:bg-muted/70 text-muted-foreground hover:text-foreground"
                        }`}
                    >
                      <div
                        className={`h-6 w-6 rounded-md shrink-0 flex items-center justify-center
                          ${
                            isBiz
                              ? "bg-amber-100 dark:bg-amber-900/50"
                              : "bg-muted"
                          }`}
                      >
                        {switching === name ? (
                          <RefreshCw
                            size={11}
                            className="animate-spin text-muted-foreground"
                          />
                        ) : isBiz ? (
                          <Building2
                            size={11}
                            className="text-amber-700 dark:text-amber-400"
                            strokeWidth={2}
                          />
                        ) : (
                          <ContactRound
                            size={11}
                            className="text-muted-foreground"
                            strokeWidth={2}
                          />
                        )}
                      </div>
                      <span className="flex-1 text-left">{label}</span>
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`text-[10px] font-medium uppercase tracking-wide
                            ${
                              isBiz
                                ? "text-amber-600 dark:text-amber-400"
                                : "text-muted-foreground"
                            }`}
                        >
                          {isBiz ? "Business" : "Personal"}
                        </span>
                        {isActive && (
                          <Check
                            size={12}
                            className="text-foreground shrink-0"
                            strokeWidth={2.5}
                          />
                        )}
                      </div>
                    </button>
                  );
                })}

                {/* New Profile */}
                <div className="mt-1 pt-1 border-t border-border/50">
                  <button
                    onClick={() => {
                      setSwitcherOpen(false);
                      setCreatorOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm
                      text-muted-foreground hover:text-foreground hover:bg-muted/70
                      transition-colors duration-100
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <div className="h-6 w-6 rounded-md bg-muted flex items-center justify-center shrink-0">
                      <Plus size={11} strokeWidth={2.5} className="text-muted-foreground" />
                    </div>
                    <span>New Profile</span>
                  </button>
                </div>
              </div>

              {/* Profile Creator Modal */}
              <ProfileCreatorModal
                isOpen={creatorOpen}
                onClose={() => setCreatorOpen(false)}
                onCreated={() => {
                  setCreatorOpen(false);
                  onRefresh();
                }}
                existingProfiles={profile.available}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export function Sidebar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { locale, setLocale, t } = useI18n();
  const [hovered, setHovered] = useState<number | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Profile data
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [profileError, setProfileError] = useState(false);

  const fetchProfile = useCallback(async () => {
    try {
      const res = await fetch(clientProxyUrl("api/profile/"), {
        cache: "no-store",
      });
      if (!res.ok) throw new Error("API error");
      const data: ProfileData = await res.json();
      setProfile(data);
      setProfileError(false);
    } catch {
      setProfileError(true);
    }
  }, []);

  useEffect(() => {
    const initial = setTimeout(fetchProfile, 0);
    // Refresh every 30s
    const id = setInterval(fetchProfile, 30_000);
    return () => {
      clearTimeout(initial);
      clearInterval(id);
    };
  }, [fetchProfile]);

  // Build navigation based on profile type
  const isBusiness = profile?.active_type === "business";
  const navigation = isBusiness
    ? [...PERSONAL_NAV, ...BUSINESS_ONLY_NAV]
    : PERSONAL_NAV;

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Focus close button when sidebar opens on mobile
  useEffect(() => {
    if (!isOpen) return;
    const t = setTimeout(() => closeRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [isOpen]);

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
            onClick={onClose}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>

      {/* Sidebar panel */}
      <aside
        aria-label="Sidebar Navigation"
        className={`fixed inset-y-0 left-0 z-50 w-72 flex flex-col
          bg-background/95 backdrop-blur-xl border-r border-border
          transition-transform duration-300 ease-[cubic-bezier(0.175,0.885,0.32,1.275)]
          lg:translate-x-0
          ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        {/* Header */}
        <div className="flex h-16 items-center justify-between px-5 border-b border-border/60">
          <Link
            href="/"
            onClick={onClose}
            className="flex items-center gap-2.5 font-bold text-lg rounded-lg
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <div className="bg-foreground text-background p-1.5 rounded-lg">
              <LayoutDashboard size={18} />
            </div>
            <span>AlphaFinance</span>
          </Link>

          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close sidebar"
            className="lg:hidden p-2 rounded-lg text-muted-foreground
              hover:text-foreground hover:bg-muted transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X size={20} />
          </button>
        </div>

        {/* Nav links */}
        <nav aria-label="Main Links" className="flex-1 mt-4 px-3 space-y-0.5 overflow-y-auto">
          {navigation.map((item, idx) => {
            const isActive =
              pathname === item.href ||
              pathname.startsWith(item.href + "/");

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={onClose}
                onMouseEnter={() => setHovered(idx)}
                onMouseLeave={() => setHovered(null)}
                aria-current={isActive ? "page" : undefined}
                className="relative flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                  transition-colors duration-150"
              >
                {/* Magnetic active indicator */}
                {isActive && (
                  <motion.div
                    layoutId="activePill"
                    className="absolute inset-0 rounded-xl bg-foreground/8 border border-border"
                    transition={{ type: "spring", stiffness: 400, damping: 34 }}
                  />
                )}

                {/* Hover glider */}
                {hovered === idx && !isActive && (
                  <motion.div
                    layoutId="hoverGlider"
                    className="absolute inset-0 rounded-xl bg-muted/70"
                    transition={{ type: "spring", stiffness: 500, damping: 36 }}
                  />
                )}

                {/* Left accent bar on active */}
                {isActive && (
                  <motion.div
                    layoutId="activeBar"
                    className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-foreground"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}

                <item.icon
                  size={18}
                  className={`relative z-10 transition-colors ${
                    isActive ? "text-foreground" : "text-muted-foreground"
                  }`}
                />
                <span
                  className={`relative z-10 font-medium transition-colors ${
                    isActive ? "text-foreground" : "text-muted-foreground"
                  }`}
                >
                  {t(item.key, item.name)}
                </span>

                {/* Active dot badge */}
                {isActive && (
                  <motion.span
                    layoutId="activeDot"
                    className="absolute right-3 z-10 h-1.5 w-1.5 rounded-full bg-foreground"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Language Switcher */}
        <div className="px-5 py-2.5 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
          <span>{t("common.language", "Language")}:</span>
          <button
            onClick={() => setLocale(locale === "en" ? "id" : "en")}
            className="px-2.5 py-1 text-xs font-bold rounded-md bg-muted text-foreground border border-border hover:bg-muted/80 transition-colors"
            title={locale === "en" ? "Ganti ke Bahasa Indonesia" : "Switch to English"}
          >
            {locale.toUpperCase()}
          </button>
        </div>

        {/* Active Profile Card */}
        {profileError ? (
          <div className="p-3 border-t border-border/60">
            <div className="p-3.5 rounded-xl bg-muted/30 border border-border/50">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1.5">
                Active Profile
              </p>
              <p className="text-xs text-muted-foreground">API unavailable</p>
            </div>
          </div>
        ) : (
          <ActiveProfileCard profile={profile} onRefresh={fetchProfile} />
        )}
      </aside>
    </>
  );
}
