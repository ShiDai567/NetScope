import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Network Packet Flow 3D",
  description: "Sci-Fi 3D UI visualizing network traffic across nodes",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
