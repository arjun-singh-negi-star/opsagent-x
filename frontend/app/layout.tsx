import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpsAgent-X",
  description: "Autonomous multi-agent DevOps & reliability engineering console.",
};

// Deliberately system fonts, not next/font/google: this avoids a build-time
// network dependency on Google's font CDN, which matters on locked-down CI
// runners. Swap in next/font (or self-hosted font files) if you want a
// custom typeface and your build environment has unrestricted egress.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <div className="mx-auto max-w-6xl px-6 py-8">{children}</div>
      </body>
    </html>
  );
}
