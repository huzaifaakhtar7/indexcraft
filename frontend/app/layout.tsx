import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "IndexCraft",
  description: "Measured Index Design Assistant",
};

const links = [
  { href: "/", label: "Connect" },
  { href: "/analyze", label: "Query" },
  { href: "/diagnosis", label: "Diagnosis" },
  { href: "/result", label: "Result" },
  { href: "/history", label: "History" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b bg-white">
          <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-4 px-4 py-3">
            <span className="font-bold">IndexCraft</span>
            {links.map((l) => (
              <Link key={l.href} href={l.href} className="text-sm text-slate-600 hover:text-slate-900">
                {l.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
