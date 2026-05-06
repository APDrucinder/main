import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { requireBackendSession } from "@/lib/auth-server";

export default async function SettingsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  try {
    await requireBackendSession();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect("/login");
    }
    throw error;
  }

  return children;
}
