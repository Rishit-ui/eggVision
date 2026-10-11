import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart3, TrendingUp, AlertCircle, PieChart } from "lucide-react";

export default function DashboardPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Quality Dashboard</h1>
        <p className="text-muted-foreground">Aggregated metrics and trends from all scanned eggs.</p>
      </div>

      {/* Stat Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { title: "Total Scans", icon: BarChart3 },
          { title: "Avg Freshness Score", icon: TrendingUp },
          { title: "Low Confidence Rate", icon: AlertCircle },
          { title: "Cracked Egg Rate", icon: PieChart }
        ].map((stat, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <stat.icon className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">--</div>
              <Skeleton className="h-3 w-16 mt-2" />
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Grid */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <Card className="col-span-1">
          <CardHeader>
            <CardTitle>Freshness Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full flex items-end justify-between gap-2 border-b border-l border-border p-4">
              {[40, 70, 100, 60, 30, 80, 50].map((h, i) => (
                <Skeleton key={i} className="w-full rounded-t-sm rounded-b-none bg-primary/20" style={{ height: `${h}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="col-span-1">
          <CardHeader>
            <CardTitle>Quality Trend (Last 7 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full flex items-center justify-center border-b border-l border-border">
              <Skeleton className="w-full h-1 bg-primary/30 rotate-3 transform origin-left" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Egg Type Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center items-center h-64">
          <div className="relative w-48 h-48">
            <Skeleton className="absolute inset-0 rounded-full" />
            <div className="absolute inset-4 rounded-full bg-card" />
          </div>
        </CardContent>
      </Card>

      <div className="mt-8 text-center text-sm text-muted-foreground">
        <p>Dashboard metrics will populate as scan data is collected.</p>
      </div>
    </div>
  );
}
