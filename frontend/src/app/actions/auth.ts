// /Users/sparshyadav/Developer/React-Projects/UI/src/app/actions/auth.ts
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { login as loginRequest, logout as logoutRequest } from "@/lib/api";

export type LoginState = {
  error?: string;
};

type CookieAttrs = {
  domain?: string;
  path?: string;
  expires?: Date;
  secure?: boolean;
  httpOnly?: boolean;
  sameSite?: "lax" | "strict" | "none";
  maxAge?: number;
};

function parseSetCookie(setCookieHeader: string) {
  const parts = setCookieHeader.split(";").map((part) => part.trim());
  const [nameValue, ...attrs] = parts;
  const separator = nameValue.indexOf("=");

  if (separator <= 0) return null;

  const name = nameValue.slice(0, separator);
  const value = nameValue.slice(separator + 1);
  const options: CookieAttrs = {};

  for (const attr of attrs) {
    const [rawKey, ...rawValue] = attr.split("=");
    const key = rawKey.toLowerCase();
    const valuePart = rawValue.join("=");

    if (key === "path") options.path = valuePart || "/";
    if (key === "domain") options.domain = valuePart;
    if (key === "expires") options.expires = new Date(valuePart);
    if (key === "max-age") options.maxAge = Number(valuePart);
    if (key === "secure") options.secure = true;
    if (key === "httponly") options.httpOnly = true;
    if (key === "samesite") {
      const sameSite = valuePart.toLowerCase();
      if (sameSite === "lax" || sameSite === "strict" || sameSite === "none") {
        options.sameSite = sameSite;
      }
    }
  }

  return { name, value, options };
}

export async function login(_: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").toLowerCase().trim();
  const password = String(formData.get("password") ?? "");

  if (!email || !password) return { error: "Invalid email or password." };

  try {
    const response = await loginRequest(email, password);
    const setCookieHeader = response.headers.get("set-cookie");

    if (setCookieHeader) {
      const parsedCookie = parseSetCookie(setCookieHeader);
      if (parsedCookie) {
        const cookieStore = await cookies();
        cookieStore.set(parsedCookie.name, parsedCookie.value, parsedCookie.options);
      }
    }

  } catch (error) {
    if (error instanceof ApiError) return { error: error.message };
    return { error: "Unable to sign in right now. Please try again." };
  }

  redirect("/dashboard");
}

export async function logout() {
  try {
    await logoutRequest();
  } catch { }

  const cookieStore = await cookies();
  for (const cookie of cookieStore.getAll()) {
    cookieStore.delete(cookie.name);
  }

  redirect("/login");
}
