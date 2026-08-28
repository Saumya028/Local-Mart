import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "LocalMart",
  description: "Your neighborhood, at your fingertips",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900">{children}</body>
    </html>
  );
}
