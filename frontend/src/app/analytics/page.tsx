import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function AnalyticsPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Research Analytics</h1>
        <p className="text-muted-foreground">Model performance, dataset statistics, and research metrics.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {['MAE (Days)', 'RMSE', 'R² Score', 'Correlation'].map((metric) => (
          <Card key={metric}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground font-medium">{metric}</CardTitle>
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-8 mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Confusion Matrix</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="aspect-square w-full max-w-md mx-auto">
              <Skeleton className="w-full h-full" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Predicted vs Actual Age</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="aspect-square w-full max-w-md mx-auto relative">
              <Skeleton className="w-full h-full" />
              <div className="absolute inset-0 flex items-center justify-center">
                <Skeleton className="w-full h-1 bg-primary/40 -rotate-45 transform origin-center" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="bg-muted/40 rounded-lg p-6 text-center border border-border">
        <p className="text-muted-foreground">Research analytics will be available after model training and validation phases are complete.</p>
      </div>
    </div>
  );
}
