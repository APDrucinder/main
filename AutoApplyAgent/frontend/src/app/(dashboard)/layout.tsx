export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex-1 w-full px-6 flex flex-col min-h-screen relative">
      <main className="flex-1 pb-10 overflow-visible custom-scroll">{children}</main>
    </div>
  );
}
