"use client";

import { useEffect, useState } from "react";
import { AlertCircle, BarChart3, CheckCircle2, Database, RefreshCw } from "lucide-react";

import { api } from "@/lib/api";
import { DashboardResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function CountList({ items, empty }: { items: DashboardResponse["image_quality_distribution"]; empty: string }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-center justify-between border-b border-border/50 pb-2 text-sm last:border-0">
          <span>{item.label.replaceAll("_", " ")}</span>
          <span className="font-semibold tabular-nums">{item.count}</span>
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError(null);
      setData(await api.getDashboard());
    } catch (err: any) {
      setError(err.message || "Unable to load dashboard data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  const stats = data ? [
    { title: "Captured scans", value: data.total_scans, icon: BarChart3 },
    { title: "Quality-gated scans", value: data.usable_scans, icon: CheckCircle2 },
    { title: "Retake recommended", value: data.retake_scans, icon: AlertCircle },
    { title: "Model state", value: data.model_ready ? "READY" : "NOT READY", icon: Database },
  ] : [];

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Research Operations Dashboard</h1>
          <p className="mt-2 text-muted-foreground">Observed capture and image-quality data. Freshness results remain unavailable until model validation is complete.</p>
        </div>
        <Button variant="outline" onClick={() => void loadDashboard()} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {error && <div className="mb-6 rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{error}</div>}

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? <p className="text-sm text-muted-foreground">Loading recorded scan data…</p> : stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{stat.title}</CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{stat.value}</div></CardContent>
          </Card>
        ))}
      </div>

      {data && !data.model_ready && (
        <div className="mb-8 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <strong>Freshness model disabled.</strong> The dashboard intentionally does not infer freshness, age, Haugh Unit, cracks, or blood spots without a validated model artifact.
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Image-quality outcomes</CardTitle></CardHeader>
          <CardContent><CountList items={data?.image_quality_distribution || []} empty="No scans have been recorded." /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Prediction service outcomes</CardTitle></CardHeader>
          <CardContent><CountList items={data?.prediction_status_distribution || []} empty="No prediction requests have been recorded." /></CardContent>
        </Card>
      </div>
    </div>
  );
}
