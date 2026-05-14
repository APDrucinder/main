import { TopNav } from "@/components/TopNav";

export default async function SettingsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <TopNav />
      {children}
    </>
  );
}
