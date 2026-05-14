import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
});

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
      <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
        <body className="min-h-full flex bg-background text-foreground font-sans">
          <div className="flex-1 w-full px-6 flex flex-col min-h-screen relative">
            <main className="flex-1 pb-10 overflow-visible custom-scroll">{children}</main>
          </div>
        </body>
      </html>
    </ClerkProvider>
  );
}
