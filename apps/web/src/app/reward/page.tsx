import type { Metadata } from 'next';

import RewardsPanel from './panel';

export const metadata: Metadata = {
  title: 'Rewards',
  description: 'Reward economy status from the engagement service. Shows live data when the API is reachable, otherwise an explicit empty/error state.',
  alternates: {
    canonical: '/reward',
  },
  openGraph: {
    title: 'Rewards | Alpha',
    description: 'Reward economy status from the engagement service.',
    url: '/reward',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'Alpha Rewards' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Rewards | Alpha',
    description: 'Reward economy status from the engagement service.',
  },
};

export default function RewardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Rewards</h1>
        <p className="text-muted-foreground mt-1">Live status of the reward economy, served by the engagement service.</p>
      </div>
      <RewardsPanel />
    </div>
  );
}
