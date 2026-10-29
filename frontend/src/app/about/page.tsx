import { Card, CardContent } from "@/components/ui/card";
import { CheckCircle2 } from "lucide-react";

export default function AboutPage() {
  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      <h1 className="text-4xl font-extrabold tracking-tight mb-8">About EggVision AI</h1>
      
      <div className="space-y-12">
        <section>
          <h2 className="text-2xl font-bold mb-4 text-primary border-b pb-2">Project Overview</h2>
          <p className="text-lg leading-relaxed text-muted-foreground">
            EggVision is an open research initiative for collecting controlled candling images and building evidence for future computer-vision models. This release does not predict air-cell size, yolk displacement, Haugh Unit, freshness, defects, spoilage, or safety.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-bold mb-4 text-primary border-b pb-2">Scientific Methodology</h2>
          <div className="space-y-4 text-muted-foreground leading-relaxed">
            <p>
              <strong>Candling-based Optical Imaging:</strong> The system relies on the traditional principle of egg candling—illuminating an egg from below in a dark environment—but digitizes and quantifies the process.
            </p>
            <p>
              <strong>Air Cell Growth:</strong> As an egg ages, moisture and carbon dioxide evaporate through the porous shell, causing the air cell at the blunt end to grow. Our models are trained to detect, segment, and measure this air cell as a primary indicator of age.
            </p>
            <p>
              <strong>Computer Vision:</strong> We use Convolutional Neural Networks (CNNs) to extract morphological features from the captured images, robust to variations in shell color (white, brown) and subtle lighting differences.
            </p>
            <p>
              <strong>Research metadata:</strong> Capture metadata such as ambient storage temperature, humidity, and egg type can be recorded for a future, separately validated research model. They are not used to produce freshness predictions in this release.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-bold mb-4 text-primary border-b pb-2">System Architecture</h2>
          <Card className="bg-muted/20 border-border/50 shadow-none">
            <CardContent className="p-6">
              <ul className="space-y-4">
                <li className="flex gap-3">
                  <CheckCircle2 className="h-6 w-6 text-primary flex-shrink-0" />
                  <div>
                    <strong className="text-foreground">Edge Device / Camera:</strong> Captures high-resolution images in a controlled chamber.
                  </div>
                </li>
                <li className="flex gap-3">
                  <CheckCircle2 className="h-6 w-6 text-primary flex-shrink-0" />
                  <div>
                    <strong className="text-foreground">FastAPI Inference Server:</strong> Python backend running PyTorch/ONNX models for real-time image processing and classification.
                  </div>
                </li>
                <li className="flex gap-3">
                  <CheckCircle2 className="h-6 w-6 text-primary flex-shrink-0" />
                  <div>
                    <strong className="text-foreground">Next.js Web Interface (This App):</strong> React-based frontend providing a responsive, accessible UI for interacting with the AI models.
                  </div>
                </li>
              </ul>
            </CardContent>
          </Card>
        </section>

        <section className="bg-destructive/5 border border-destructive/20 rounded-xl p-6">
          <h2 className="text-xl font-bold mb-4 text-destructive flex items-center gap-2">
            Limitations & Disclaimers
          </h2>
          <ul className="list-disc pl-5 space-y-2 text-muted-foreground">
            <li><strong>Not a safety guarantee:</strong> This system does not detect microbiological contamination (like Salmonella), cannot establish internal quality from an ordinary image, and cannot guarantee eggs are safe for consumption.</li>
            <li><strong>Hardware dependency:</strong> Accuracy is heavily dependent on consistent imaging conditions. Extreme variations in camera quality or lighting will affect results.</li>
            <li><strong>Research status:</strong> EggVision AI is a research prototype. All models are currently pending rigorous external validation against industry standards.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-bold mb-4 text-primary border-b pb-2">Research Reproducibility</h2>
          <p className="text-muted-foreground leading-relaxed">
            We are committed to open science. Once validation is complete, the dataset, model weights, and inference code will be made available to researchers under an open-source license to encourage replication and further innovation in agricultural AI.
          </p>
        </section>
      </div>
    </div>
  );
}
