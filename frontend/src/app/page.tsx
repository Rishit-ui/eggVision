import Link from "next/link";
import { ArrowRight, Camera, Search, BarChart3, Clock, CheckCircle2, ShieldAlert, Cpu, Network, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative px-4 py-24 sm:px-6 lg:px-8 bg-gradient-to-b from-primary/5 to-background overflow-hidden">
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 bg-primary/10 rounded-full blur-3xl opacity-50" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 bg-primary/10 rounded-full blur-3xl opacity-50" />
        
        <div className="container mx-auto max-w-5xl text-center relative z-10">
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-foreground mb-6">
            AI-Powered Non-Destructive <br className="hidden md:block" />
            <span className="text-primary">Egg Freshness</span> Detection
          </h1>
          <p className="mt-4 text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
            Analyze egg freshness using controlled optical imaging and AI — without breaking the egg. Fast, reliable, and data-driven quality assessment for agriculture.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Button asChild size="lg" className="h-12 px-8 text-base">
              <Link href="/scan">
                Start Scanning <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="h-12 px-8 text-base bg-background/50 backdrop-blur">
              <Link href="/about">Learn More</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Notice Callout */}
      <section className="container mx-auto px-4 max-w-4xl -mt-8 relative z-20">
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg shadow-sm">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <ShieldAlert className="h-5 w-5 text-blue-500" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">Research Prototype Notice</h3>
              <div className="mt-1 text-sm text-blue-700">
                <p>EggVision AI is a research prototype under active development. All accuracy metrics are pending validation on diverse datasets.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 bg-background">
        <div className="container mx-auto px-4 max-w-5xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">How It Works</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">Our four-step workflow combines physical imaging with advanced computer vision to assess internal egg quality.</p>
          </div>

          <div className="grid md:grid-cols-4 gap-8">
            {[
              { icon: Camera, title: "1. Capture", desc: "Place egg in scanning chamber and capture image" },
              { icon: Search, title: "2. Analyze", desc: "AI processes image for freshness indicators" },
              { icon: BarChart3, title: "3. Results", desc: "Get freshness score, confidence, and analysis" },
              { icon: Clock, title: "4. Track", desc: "Monitor egg quality trends over time" }
            ].map((step, i) => (
              <div key={i} className="flex flex-col items-center text-center relative group">
                <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-6 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <step.icon className="h-8 w-8 text-primary group-hover:text-primary-foreground transition-colors" />
                </div>
                <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
                <p className="text-muted-foreground text-sm leading-relaxed">{step.desc}</p>
                
                {i < 3 && (
                  <div className="hidden md:block absolute top-8 left-[60%] w-full h-px bg-border -z-10" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Key Features */}
      <section className="py-20 bg-muted/30 border-y border-border">
        <div className="container mx-auto px-4 max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Key Features</h2>
            <p className="text-muted-foreground">Comprehensive optical analysis powered by deep learning.</p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              "Air Cell Analysis", "Yolk Assessment", "Crack Detection", "Freshness Scoring",
              "Confidence Rating", "Explainable AI", "Batch Processing", "Edge Deployment"
            ].map((feature, i) => (
              <Card key={i} className="border-border/50 hover:shadow-md transition-shadow bg-background/50 backdrop-blur">
                <CardHeader className="p-4 pb-2">
                  <CheckCircle2 className="h-6 w-6 text-primary mb-2" />
                  <CardTitle className="text-base">{feature}</CardTitle>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Technology & Targets */}
      <section className="py-20 bg-background">
        <div className="container mx-auto px-4 max-w-5xl">
          <div className="grid md:grid-cols-2 gap-16">
            <div>
              <h2 className="text-2xl font-bold tracking-tight mb-6">Technology Stack</h2>
              <ul className="space-y-6">
                <li className="flex gap-4">
                  <div className="mt-1 bg-muted p-2 rounded-lg h-fit"><Cpu className="h-5 w-5 text-primary" /></div>
                  <div>
                    <h4 className="font-medium">Computer Vision</h4>
                    <p className="text-sm text-muted-foreground mt-1">PyTorch-based CNNs optimized for morphological feature extraction.</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <div className="mt-1 bg-muted p-2 rounded-lg h-fit"><Database className="h-5 w-5 text-primary" /></div>
                  <div>
                    <h4 className="font-medium">FastAPI Backend</h4>
                    <p className="text-sm text-muted-foreground mt-1">High-performance async inference server managing model weights.</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <div className="mt-1 bg-muted p-2 rounded-lg h-fit"><Network className="h-5 w-5 text-primary" /></div>
                  <div>
                    <h4 className="font-medium">Next.js Frontend</h4>
                    <p className="text-sm text-muted-foreground mt-1">React Server Components, edge-ready architecture, responsive design.</p>
                  </div>
                </li>
              </ul>
            </div>
            
            <div className="bg-muted/40 p-8 rounded-2xl border border-border">
              <h2 className="text-2xl font-bold tracking-tight mb-6">Development Targets</h2>
              <p className="text-sm text-muted-foreground mb-6">We are currently targeting the following benchmarks for the production release:</p>
              
              <div className="space-y-4">
                <div className="bg-background p-4 rounded-xl border border-border shadow-sm flex items-center justify-between">
                  <span className="font-medium text-sm">Inference Time</span>
                  <span className="text-primary font-bold">&lt; 2s</span>
                </div>
                <div className="bg-background p-4 rounded-xl border border-border shadow-sm flex items-center justify-between">
                  <span className="font-medium text-sm">Egg Types Supported</span>
                  <span className="text-primary font-bold">3+</span>
                </div>
                <div className="bg-background p-4 rounded-xl border border-border shadow-sm flex items-center justify-between">
                  <span className="font-medium text-sm">Deployment Mode</span>
                  <span className="text-primary font-bold">Edge/Offline</span>
                </div>
                <div className="bg-background p-4 rounded-xl border border-border shadow-sm flex items-center justify-between">
                  <span className="font-medium text-sm">Analysis Method</span>
                  <span className="text-primary font-bold">Non-destructive</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
