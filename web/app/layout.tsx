import type { Metadata, Viewport } from "next";
import { Instrument_Sans } from "next/font/google";
import "@/index.css";

const instrumentSans = Instrument_Sans({
	subsets: ["latin"],
	display: "swap",
	variable: "--font-instrument-sans",
});

export const viewport: Viewport = {
	width: "device-width",
	initialScale: 1,
	maximumScale: 1,
};

export const metadata: Metadata = {
	title: "Custom LLM Recipe | Agora Conversational AI",
	description:
		"Recipe: Bring your own LLM to Agora Conversational AI Engine via a custom OpenAI-compatible proxy.",
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" className={`${instrumentSans.variable} h-full`}>
			<body className="h-full min-h-screen">{children}</body>
		</html>
	);
}
