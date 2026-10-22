"use client";

import { useI18n } from "@/i18n/context";

export default function Loading() {
  const { t } = useI18n();
  return (
    <div
      role="status"
      aria-label={t("common.loading")}
      className="flex min-h-[400px] w-full items-center justify-center"
    >
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-slate-800 dark:border-slate-800 dark:border-t-slate-200" />
    </div>
  );
}
