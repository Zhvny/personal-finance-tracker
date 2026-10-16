import { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://finance-tracker.example.com';
  // lastModified reflects when each route was last meaningfully updated.
  // Update these when page content changes significantly.
  const now = new Date();
  const lastModified = now;

  return [
    {
      url: baseUrl,
      lastModified,
      changeFrequency: 'daily',
      priority: 1,
    },
    {
      url: `${baseUrl}/analytics`,
      lastModified,
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/behavioral`,
      lastModified,
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/reward`,
      lastModified,
      changeFrequency: 'weekly',
      priority: 0.8,
    },
  ];
}
