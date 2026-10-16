import { CardSkeleton } from "./card-skeleton";

export function AnalyticsSkeleton() {
  return (
    <div className="space-y-8">
      <div>
        <div className="h-9 w-48 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
        <div className="mt-2 h-5 w-72 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <div className="col-span-4 h-[400px] animate-pulse rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
           <div className="h-6 w-32 rounded bg-slate-200 dark:bg-slate-800 mb-4" />
           <div className="h-full w-full rounded bg-slate-100 dark:bg-slate-900" />
        </div>
        <div className="col-span-3 h-[400px] animate-pulse rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
           <div className="h-6 w-32 rounded bg-slate-200 dark:bg-slate-800 mb-4" />
           <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center space-x-4">
                  <div className="h-10 w-10 rounded-full bg-slate-200 dark:bg-slate-800" />
                  <div className="space-y-2 flex-1">
                    <div className="h-4 w-1/2 rounded bg-slate-200 dark:bg-slate-800" />
                    <div className="h-3 w-1/4 rounded bg-slate-200 dark:bg-slate-800" />
                  </div>
                </div>
              ))}
           </div>
        </div>
      </div>
    </div>
  );
}
