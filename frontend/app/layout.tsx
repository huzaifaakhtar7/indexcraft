import type { Metadata } from "next";
import Nav from "@/components/Nav";
import { StoreProvider } from "@/lib/store";
import "./globals.css";

export const metadata: Metadata = {
  title: "IndexCraft",
  description: "Measured Index Design Assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <StoreProvider>
          <Nav />
          <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
          <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-slate-400 sm:px-6">
            IndexCraft · Measured Index Design Assistant · every fix is tested on a copy, never on your data
          </footer>
        </StoreProvider>
      </body>
    </html>
  );
}
