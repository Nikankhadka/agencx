import type { Metadata } from "next";
import { LegalDoc, LegalList, LegalSection } from "@/components/LegalDoc";
import { LEGAL, REQUEST_DAYS } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Privacy - Agencx",
  description: "What Agencx collects, who sees it, how long it is kept, and how to ask for it back.",
};

/**
 * The numbers here are the ones in docs/agencx/design/retention.md (D36) and the
 * request path in docs/agencx/deploy.md Step 8 (D35). Change them together.
 *
 * Copy rule (PRD section 13): no "AI", "agent", "automated" or "virtual" in
 * routine copy. This page still has to say plainly that a language model reads
 * what a customer types, so it says "language model" and "assistant" and never
 * softens what that means. privacy.test.tsx pins the banned words.
 */
export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy" updated={LEGAL.updated}>
      <LegalSection title="Who this covers">
        <p>
          Agencx gives a small business its own assistant that answers its customers from the
          business&apos;s own information. It is run by {LEGAL.entity} ({LEGAL.abn}). This page
          covers two groups of people: <strong>business owners</strong>, who sign in to set an
          assistant up, and <strong>customers</strong>, who chat with a business through its page.
        </p>
        <p>
          Questions and requests go to {LEGAL.contactEmail}. What we do with a request is under
          &quot;Your requests&quot; below.
        </p>
      </LegalSection>

      <LegalSection title="What we collect">
        <p>
          <strong>From a business owner:</strong>
        </p>
        <LegalList>
          <li>The email address you sign in with. We send a six-digit code; there is no password.</li>
          <li>
            Everything you tell the assistant while setting up, and everything you add: documents,
            prices, services, photos and your logo, opening hours, and your contact details.
          </li>
          <li>The conversations your customers have with your assistant, described below.</li>
        </LegalList>
        <p>
          <strong>From a customer of a business:</strong>
        </p>
        <LegalList>
          <li>
            Whatever you type into the chat, word for word. That can include your name, phone number
            or email if you write them, so please leave out anything you would not want the business
            to read, such as card numbers, passwords or medical details.
          </li>
          <li>
            The email address you give if you ask to be put in touch with a person at the business.
          </li>
          <li>
            If you ask for a quote, the quote, so you and the business have the same figures.
          </li>
        </LegalList>
        <p>
          <strong>From everyone:</strong> your IP address. We use it for a moment, in memory, to
          slow down anyone sending requests faster than a person could, and we do not store it in
          our database. The companies that host Agencx keep ordinary request logs that include it.
          We use no advertising or analytics cookies and no tracking scripts. Signing in sets one
          cookie that keeps an owner signed in; customers get none.
        </p>
        <p>
          We also keep usage records (how much model work a conversation used, and what it cost)
          with no message text in them. This is how each business&apos;s daily limit is
          enforced.
        </p>
      </LegalSection>

      <LegalSection title="Who sees a conversation">
        <p>
          A customer is talking to a business, through Agencx. The business owner can read every
          conversation on their page, including any contact details the customer gave, and can take
          over a chat themselves. The business is responsible for how it uses what its customers
          tell it. Agencx handles that text on the business&apos;s behalf to run the assistant and
          does not use it for anything else.
        </p>
        <p>
          The assistant is not a person. It says so honestly if a customer asks, and it hands the
          conversation to a person at the business when it should.
        </p>
        <p>
          The Agencx operator can see any account&apos;s data when that is needed to keep the
          service working or to answer a request.
        </p>
      </LegalSection>

      <LegalSection title="Who else handles the data">
        <p>
          The service runs on other companies&apos; infrastructure. Each one receives only what it
          needs to do its part.
        </p>
        <LegalList>
          <li>
            <strong>Supabase</strong> holds the database (accounts, businesses, conversations),
            handles sign-in, and stores uploaded files.
          </li>
          <li>
            <strong>Vercel</strong> hosts the website and the server behind it.
          </li>
          <li>
            <strong>Cloudinary</strong> stores and serves the photos a business uploads.
          </li>
          <li>
            <strong>Language model providers</strong> read the text and write the replies. Agencx
            uses <strong>Google AI Studio</strong>, <strong>Groq</strong> and{" "}
            <strong>OpenRouter</strong>, and can switch between them if one is slow or down. Each
            receives the customer&apos;s message, the recent conversation, and the parts of the
            business&apos;s own information needed to answer. During setup it also receives what the
            owner types and the documents they add.
          </li>
          <li>
            <strong>Google</strong> also turns a business&apos;s documents into a search index, and{" "}
            <strong>Cohere</strong> ranks which passages best fit a question.
          </li>
          <li>
            <strong>Sentry</strong> receives error reports when something breaks. We have switched
            off everything that could carry a customer&apos;s message, so a report holds the
            technical error and the page it happened on.
          </li>
          <li>
            <strong>Langfuse</strong>, only if we turn diagnostic tracing on, receives routing
            decisions, timings and counts for each reply, not the message text.
          </li>
        </LegalList>
        <p>
          <strong>Free plans matter here.</strong> Some of these providers offer free plans, and
          under the terms of a free plan a provider may keep the text sent to it and use it to
          improve its own products, including training. We choose providers with that in mind, but we
          cannot promise that a provider will not retain text it receives, and we cannot make one
          delete it. That is the main reason not to type anything sensitive into a chat.
        </p>
        <p>
          These companies may process data in other countries, including the United States. We do not
          sell personal information and we do not share it for advertising.
        </p>
      </LegalSection>

      <LegalSection title="How long we keep it">
        <LegalList>
          <li>
            <strong>Customer conversations:</strong> deleted 365 days after the last message.
          </li>
          <li>
            <strong>Conversations nobody answered:</strong> if the assistant never replied and no
            one was contacted, deleted after 30 days. These are almost always a visitor who typed a
            line and left, or a bot.
          </li>
          <li>
            <strong>Conversations with a quote:</strong> kept, because a quote is a commercial record.
            They are removed when the business&apos;s account is deleted, or on a written request.
          </li>
          <li>
            <strong>A business&apos;s own content and account:</strong> kept while the account is
            open.
          </li>
          <li>
            <strong>Usage records:</strong> kept for the life of the account. They hold counts and
            costs, not message text.
          </li>
        </LegalList>
        <p>
          Clean-up runs about once a month, so a conversation can outlast its limit by up to a
          month. A business owner can also delete any single customer conversation from their
          console at any time; the one exception is a conversation with a quote, which we remove on
          request.
        </p>
        <p>
          Deleting something removes it from our database and our files. It does not reach copies
          that a language model provider already received (see above), the request logs kept by our
          hosts, or backups, where deleted data stays until the backup itself expires.
        </p>
      </LegalSection>

      <LegalSection title="Your requests">
        <p>
          <strong>A business owner</strong> can ask for a copy of everything we hold about their
          business, or for the account and all of its data to be deleted. Write to {LEGAL.contactEmail}{" "}
          from the email address you sign in with, and we will answer within {REQUEST_DAYS} days.
          We send the copy as one file. It holds everything in your account, with three exceptions:
          the raw bytes of uploaded files and of your cover image (we send those separately if you
          ask), the search index we derive from your documents, and your sign-in address, which our
          sign-in provider holds. A deletion removes the account, its conversations and quotes, its
          files, and the sign-in itself, and we confirm the date it was done.
        </p>
        <p>
          <strong>A customer</strong> should first ask the business, which holds the conversation
          and can delete it. If you would rather ask us, write to {LEGAL.contactEmail} with the
          business&apos;s name and roughly when you chatted, and we will help the business action
          it within {REQUEST_DAYS} days. We may need enough detail to find the conversation.
        </p>
        <p>
          You can also ask to see or correct personal information we hold about you. If you are not
          satisfied with our answer, you can complain to your privacy regulator; in Australia that is
          the Office of the Australian Information Commissioner.
        </p>
      </LegalSection>

      <LegalSection title="Security">
        <p>
          Everything travels over an encrypted connection. Each business&apos;s data is kept apart
          from every other business&apos;s inside the database, and owners sign in with a code sent
          to their email. No system is perfectly secure. If we learn that personal information has
          been exposed in a way that could cause harm, we will tell the people affected and any
          regulator the law requires.
        </p>
      </LegalSection>

      <LegalSection title="Children">
        <p>Agencx is for businesses and their customers. It is not aimed at children.</p>
      </LegalSection>

      <LegalSection title="Changes">
        <p>
          If this page changes in a way that matters, we will update the date above and tell
          business owners. The current version is always the one on this page.
        </p>
      </LegalSection>
    </LegalDoc>
  );
}
