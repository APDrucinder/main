import { cookies } from "next/headers";
import { ApiError } from "@/lib/api-client";
import { meServer } from "@/lib/api";

async function buildCookieHeader() {
  const cookieStore = await cookies();
  return cookieStore.getAll().map((item) => `${item.name}=${item.value}`).join("; ");
}

export async function requireBackendSession() {
  const cookieHeader = await buildCookieHeader();
  if (!cookieHeader) {
    throw new ApiError("Unauthorized", "UNAUTHORIZED", 401);
  }
  return meServer(cookieHeader);
}
