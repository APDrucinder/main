import { TopNav } from "@/components/TopNav";

export default async function ApplicationsLayout({
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
