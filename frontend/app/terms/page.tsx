import type { Metadata } from "next";
import { Contact, LegalPage } from "@/components/legal/LegalPage";

export const metadata: Metadata = { title: "Terms of service · ReachAI" };

export default function Terms() {
  return (
    <LegalPage title="Terms of service" updated="November 12, 2026">
      <p>By using ReachAI you agree to these terms. ReachAI uses YouTube API Services, so by using it you also agree to the <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>.</p>
      <h2>The service</h2>
      <p>ReachAI suggests creators, fair prices and messages. Suggestions are estimates; you decide what to send, agree and pay. ReachAI doesn&apos;t move money: you pay creators directly.</p>
      <h2>Your responsibilities</h2>
      <ul>
        <li>Send only messages you&apos;re happy to send from your own name, and follow anti-spam laws and each platform&apos;s rules.</li>
        <li>Make sure sponsored posts are labelled as ads where the law requires it.</li>
        <li>Keep your account secure.</li>
      </ul>
      <h2>Connected accounts</h2>
      <p>If you connect Gmail, ReachAI sends only the messages you approve and reads only replies in threads it started. See the <a href="/privacy">privacy policy</a>.</p>
      <h2>No warranty</h2>
      <p>ReachAI is provided as is. We aren&apos;t liable for the outcome of deals or campaigns made with it.</p>
      <h2>Contact</h2>
      <p><Contact /></p>
    </LegalPage>
  );
}
