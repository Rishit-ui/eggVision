import Link from "next/link";
import { EggOff } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-16rem)] text-center px-4">
      <div className="bg-muted/50 p-6 rounded-full mb-6">
        <EggOff className="h-16 w-16 text-muted-foreground" />
      </div>
      <h2 className="text-3xl font-bold tracking-tight mb-2">404 - Page Not Found</h2>
      <p className="text-muted-foreground max-w-md mb-8">
        Oops! We couldn&apos;t find the page you&apos;re looking for. It might have been moved or doesn&apos;t exist.
      </p>
      <Button asChild>
        <Link href="/">Return to Home</Link>
      </Button>
    </div>
  );
}
