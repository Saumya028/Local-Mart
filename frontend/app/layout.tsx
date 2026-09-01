import "./globals.css";
import type { Metadata } from "next";
import Header from "@/components/Header";
import { AuthProvider } from "@/contexts/AuthContext";

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
      <body className="bg-white text-gray-900">
        <AuthProvider>
          <Header />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
