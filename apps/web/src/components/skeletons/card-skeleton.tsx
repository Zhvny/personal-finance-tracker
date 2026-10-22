export function CardSkeleton() {
  return (
    <div aria-hidden="true" className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950 animate-pulse">
      <div className="mb-4 h-6 w-1/3 rounded bg-slate-200 dark:bg-slate-800" />
      <div className="space-y-3">
        <div className="h-4 w-full rounded bg-slate-200 dark:bg-slate-800" />
        <div className="h-4 w-5/6 rounded bg-slate-200 dark:bg-slate-800" />
      </div>
    </div>
  );
}
