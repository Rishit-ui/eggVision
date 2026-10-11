import Link from "next/link";
import { Egg } from "lucide-react";

export function Footer() {
  return (
    <footer className="w-full border-t border-border bg-muted/40 py-8 md:py-12 mt-auto">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-4">
          <div className="md:col-span-2 space-y-4">
            <Link href="/" className="flex items-center space-x-2">
              <Egg className="h-5 w-5 text-primary" />
              <span className="font-semibold text-lg tracking-tight">EggVision AI</span>
            </Link>
            <p className="text-sm text-muted-foreground max-w-sm">
              AI-Powered Non-Destructive Egg Freshness Detection using controlled optical imaging.
            </p>
            <div className="p-4 bg-muted rounded-lg border border-border mt-4 text-xs text-muted-foreground">
              <strong>Disclaimer:</strong> This system estimates freshness-related quality indicators based on visual characteristics. It does not guarantee microbiological safety and is a research prototype.
            </div>
          </div>
          
          <div>
            <h4 className="font-medium mb-4">Resources</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/about" className="text-muted-foreground hover:text-foreground transition-colors">
                  About the Project
                </Link>
              </li>
              <li>
                <Link href="/analytics" className="text-muted-foreground hover:text-foreground transition-colors">
                  Research Analytics
                </Link>
              </li>
              <li>
                <a href="#" className="text-muted-foreground hover:text-foreground transition-colors">
                  Documentation
                </a>
              </li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-medium mb-4">Links</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="#" className="text-muted-foreground hover:text-foreground transition-colors">
                  GitHub Repository
                </a>
              </li>
              <li>
                <Link href="/admin" className="text-muted-foreground hover:text-foreground transition-colors">
                  Admin Portal
                </Link>
              </li>
            </ul>
          </div>
        </div>
        
        <div className="mt-8 pt-8 border-t border-border flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} EggVision AI. Research Prototype.
          </p>
          <div className="flex space-x-4 text-xs text-muted-foreground">
            <a href="#" className="hover:text-foreground">Privacy</a>
            <a href="#" className="hover:text-foreground">Terms</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
