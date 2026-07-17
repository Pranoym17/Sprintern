import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Sprintern — Internship alerts without the refresh loop", template: "%s · Sprintern" },
  description: "Track Summer 2027 software internships with focused filters and instant Telegram alerts.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
