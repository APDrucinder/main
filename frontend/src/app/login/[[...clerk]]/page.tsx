import { SignIn } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function LoginPage() {
  const { userId } = await auth();
  if (userId) {
    redirect("/dashboard");
  }

  return (
    <div className="flex min-h-[calc(100vh-3rem)] w-full items-center justify-center py-10 text-white">
      <section className="grid w-full max-w-5xl grid-cols-1 overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.03] shadow-2xl shadow-black/30 backdrop-blur-2xl md:grid-cols-[1fr_0.9fr]">
        <div className="flex min-h-[520px] flex-col justify-between p-8 md:p-10">
          <div>
            <div className="mb-10 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white">
                <div className="h-5 w-5 -rotate-45 rounded-full border-[3px] border-black border-b-transparent" />
              </div>
              <span className="text-lg font-bold uppercase tracking-wide">CelerixAi</span>
            </div>

            <div className="max-w-sm">
              <p className="mb-3 text-xs font-bold uppercase tracking-[0.22em] text-white">
                Secure Access
              </p>
              <h1 className="text-4xl font-light uppercase tracking-tight md:text-5xl">
                Agent <span className="font-bold">Login</span>
              </h1>
              <p className="mt-4 text-sm leading-6 text-white/50">
                Enter your workspace credentials to continue to the dashboard.
              </p>
            </div>
          </div>

          <div className="mt-10 grid grid-cols-3 gap-3 text-center">
            {[
              ["Cookie", "HttpOnly"],
              ["Session", "Signed"],
              ["Access", "Private"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-white/10 bg-black/20 p-3">
                <p className="text-[10px] font-semibold uppercase text-white/35">{label}</p>
                <p className="mt-1 text-sm font-bold text-white">{value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center border-t border-white/10 bg-black/20 p-8 md:border-l md:border-t-0 md:p-10">
          <div className="w-full">
            <div className="mb-8">
              <h2 className="text-xl font-semibold">Welcome back</h2>
              <p className="mt-2 text-sm text-white/45"></p>
            </div>
            <SignIn
              routing="path"
              path="/login"
              fallbackRedirectUrl="/dashboard"
              signUpFallbackRedirectUrl="/onboarding"
              appearance={{
                elements: {
                  rootBox: "w-full",
                  card: "bg-white border border-gray-200 shadow-sm w-full",
                  headerTitle: "text-gray-900",
                  headerSubtitle: "text-gray-500",
                  socialButtonsBlockButton: "bg-white border border-gray-200 text-gray-900 hover:bg-gray-50",
                  socialButtonsBlockButtonText: "text-gray-900",
                  dividerLine: "bg-gray-200",
                  dividerText: "text-gray-500",
                  formFieldLabel: "text-gray-700",
                  formFieldInput: "bg-white border border-gray-200 text-gray-900",
                  footerAction: "hidden",
                  footerBottom: "hidden",
                  watermark: "hidden",
                  footer: "hidden",
                  identityPreviewText: "text-gray-900",
                  formButtonPrimary: "bg-black text-white hover:bg-gray-800",
                  internal: "hidden",
                },
                variables: {
                  colorPrimary: "#000000",
                  colorBackground: "#ffffff",
                  colorText: "#111827",
                  colorTextSecondary: "#6b7280",
                  colorInputBackground: "#ffffff",
                  colorInputText: "#111827",
                }
              }}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
