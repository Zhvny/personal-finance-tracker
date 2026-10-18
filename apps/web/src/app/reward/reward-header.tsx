"use client";

import { useI18n } from "@/i18n/context";

export function RewardHeader() {
  const { t } = useI18n();
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{t("reward.page_title", "Rewards")}</h1>
      <p className="text-muted-foreground mt-1">
        {t("reward.page_subtitle", "Live status of the reward economy, served by the engagement service.")}
      </p>
    </div>
  );
}
