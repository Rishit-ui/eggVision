import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Search } from "lucide-react";

export default function HistoryPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Scan History</h1>
        <p className="text-muted-foreground">View and filter past controlled-capture research records.</p>
      </div>

      {/* Filters Skeleton */}
      <Card className="mb-6">
        <CardContent className="p-4 flex flex-col sm:flex-row gap-4 items-center">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <div className="h-9 w-full rounded-md border border-border bg-muted/30" />
          </div>
          <div className="flex gap-2 w-full sm:w-auto">
            <Skeleton className="h-9 w-32" />
            <Skeleton className="h-9 w-32" />
            <Skeleton className="h-9 w-24" />
          </div>
        </CardContent>
      </Card>

      {/* Table Skeleton */}
      <div className="border border-border rounded-lg overflow-hidden bg-background shadow-sm">
        <div className="grid grid-cols-6 p-4 border-b border-border bg-muted/40 text-sm font-medium text-muted-foreground">
          <div className="col-span-2 sm:col-span-1">Date</div>
          <div className="hidden sm:block">Image</div>
          <div>Egg Type</div>
          <div>Freshness</div>
          <div className="hidden sm:block">Confidence</div>
          <div className="text-right">Action</div>
        </div>
        
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="grid grid-cols-6 p-4 border-b border-border items-center hover:bg-muted/20 transition-colors">
            <div className="col-span-2 sm:col-span-1"><Skeleton className="h-4 w-20" /></div>
            <div className="hidden sm:block"><Skeleton className="h-10 w-10 rounded-md" /></div>
            <div><Skeleton className="h-4 w-16" /></div>
            <div><Skeleton className="h-6 w-16 rounded-full" /></div>
            <div className="hidden sm:block"><Skeleton className="h-4 w-12" /></div>
            <div className="flex justify-end"><Skeleton className="h-8 w-20 rounded-md" /></div>
          </div>
        ))}
      </div>

      {/* Pagination Skeleton */}
      <div className="flex items-center justify-between mt-6">
        <Skeleton className="h-4 w-32" />
        <div className="flex gap-2">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-9 w-20" />
        </div>
      </div>

      <div className="mt-12 text-center text-sm text-muted-foreground bg-muted/20 p-8 rounded-lg border border-dashed">
        <p>Scan history will appear here once you start scanning eggs.</p>
      </div>
    </div>
  );
}
