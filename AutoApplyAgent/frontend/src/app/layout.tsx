import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orion Dashboard",
  description: "AI Job Agent Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider
      signInUrl="/login"
      signUpUrl="/login"
      signInFallbackRedirectUrl="/dashboard"
      signUpFallbackRedirectUrl="/onboarding"
    >
      <html lang="en" className="h-full antialiased dark">
        <body className="min-h-full flex flex-col bg-background text-foreground font-sans">
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
