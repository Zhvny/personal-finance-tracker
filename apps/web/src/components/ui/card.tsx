export function Card({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      {title && <h3 className="mb-4 text-lg font-semibold tracking-tight">{title}</h3>}
      {children}
    </div>
  );
}
