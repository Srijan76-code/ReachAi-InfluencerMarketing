import type { Metadata } from "next";
import { Contact, LegalPage } from "@/components/legal/LegalPage";

export const metadata: Metadata = { title: "Privacy policy · ReachAI" };

export default function Privacy() {
  return (
    <LegalPage title="Privacy policy" updated="November 12, 2026">
      <p>ReachAI helps founders find creators, agree fair deals with them and track the results. This page says what we collect, why, and what we never do.</p>

      <h2>What we collect</h2>
      <ul>
        <li><b>Your account:</b> your name and email, through our sign-in provider (Clerk).</li>
        <li><b>Your campaigns:</b> the briefs you write, the creators you save, your deals, notes and payments you record.</li>
        <li><b>Public creator data:</b> channel names, public stats, recent public posts and any contact details creators publish on their channels, from platform APIs such as YouTube.</li>
        <li><b>Gmail, only if you connect it:</b> see the next section.</li>
        <li><b>Results:</b> visits through creators&apos; tracking links (a count and a time, not who visited) and, if you add our snippet to your site, one count per signup with the creator&apos;s code. The snippet keeps that code in the visitor&apos;s browser on your site for 30 days and sends nothing about the person.</li>
      </ul>

      <h2>Gmail</h2>
      <p>If you connect Gmail, ReachAI asks Google for two permissions:</p>
      <ul>
        <li><b>Send email</b>, to send the messages you approve to creators, from your own address.</li>
        <li><b>Read email</b>, used only to read creators&apos; replies in the email threads ReachAI started for your deals. We don&apos;t read, search or store any other email in your inbox.</li>
      </ul>
      <p>From a creator&apos;s reply we keep the text they wrote (without the quoted earlier messages) on that deal, so you can see it and so we can suggest your next step. Your Gmail access token is encrypted and stored only on our servers. Nothing is sent without your approval.</p>
      <p>ReachAI&apos;s use and transfer of information received from Google APIs to any other app will adhere to the <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">Google API Services User Data Policy</a>, including the Limited Use requirements. We don&apos;t use Gmail data for advertising, we don&apos;t sell it, we don&apos;t let people read it except to keep the service secure or where the law requires, and we don&apos;t use it to train AI models.</p>
      <p>You can disconnect Gmail at any time in ReachAI (it revokes our access) or in your Google account settings.</p>

      <h2>How we use AI</h2>
      <p>Fair prices and your limits are worked out in our own code. A judging model (Jev, by TypeSafe AI) answers questions about public posts and about creators&apos; replies, such as what they&apos;re asking for and which next step fits. A language model writes the replies you review; to answer a creator properly it sees their latest messages in that deal&apos;s thread (including replies that came through Gmail), screened first for attempts to instruct an AI. Every amount in a draft is checked by code. These providers process data only to answer our requests and not to train their models.</p>
      <p>To suggest fair prices we may use anonymous totals of the prices ReachAI users agreed with creators of a similar size. They never include who agreed them or which creator it was.</p>

      <h2>Who we share data with</h2>
      <p>Only the services that run ReachAI: hosting (Vercel), database (Neon), background jobs (Inngest), sign-in (Clerk), Google and YouTube APIs, and the AI providers above. We never sell your data. Share links you create show only what you choose to share and never include contact details.</p>

      <h2>Keeping and deleting data</h2>
      <p>Public YouTube data is refreshed or deleted within 30 days, as YouTube&apos;s rules require. ReachAI uses YouTube API Services; see the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>. Deleting a campaign deletes its creators, deals and messages with it. To delete your account and everything in it, contact us.</p>

      <h2>Contact</h2>
      <p>Questions or deletion requests: <Contact />.</p>
    </LegalPage>
  );
}
