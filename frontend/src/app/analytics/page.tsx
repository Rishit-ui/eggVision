import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AnalyticsPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Research Analytics</h1>
        <p className="text-muted-foreground">Model metrics are unavailable until a labeled study and independent evaluation have been completed.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {['Freshness MAE', 'Defect F1', 'Segmentation Dice', 'Calibration'].map((metric) => (
          <Card key={metric}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground font-medium">{metric}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Not measured</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-8 mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Classification evaluation</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="aspect-square w-full max-w-md mx-auto">
              <p className="p-6 text-sm text-muted-foreground">No validated classification model or held-out evaluation is available.</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Laboratory-linked regression</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="aspect-square w-full max-w-md mx-auto relative">
              <p className="p-6 text-sm text-muted-foreground">No paired laboratory ground truth or validated regression model is available.</p>
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
