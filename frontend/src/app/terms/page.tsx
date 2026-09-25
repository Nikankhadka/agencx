import type { Metadata } from "next";
import Link from "next/link";
import { LegalDoc, LegalList, LegalSection } from "@/components/LegalDoc";
import { LEGAL, REQUEST_DAYS } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Terms - Agencx",
  description: "The terms for using Agencx as a business, and for chatting with a business on it.",
};

/**
 * Same copy rule as the privacy page (PRD section 13): "assistant" and
 * "language model", never "AI", "agent", "automated" or "virtual".
 *
 * The quote clause states the hard rule from CLAUDE.md in plain words: a
 * language model never produces a price, the pricing engine does. Keep it true
 * to that if the pricing design ever changes.
 */
export default function TermsPage() {
  return (
    <LegalDoc title="Terms" updated={LEGAL.updated}>
      <LegalSection title="The short version">
        <p>
          Agencx gives a business its own assistant that answers its customers from the
          business&apos;s own information. {LEGAL.entity} ({LEGAL.abn}) runs it. If you are a
          business owner, these terms are the agreement between you and us. If you are a customer
          chatting with a business, sections 5 and 6 are the ones that matter to you, and the{" "}
          <Link href="/privacy" className="text-accent-active hover:underline">
            privacy page
          </Link>{" "}
          says what happens to what you type.
        </p>
      </LegalSection>

      <LegalSection title="1. What you get">
        <p>
          A page for your business at its own address, and an assistant on it that answers from what
          you have told it and uploaded, and hands the conversation to you when it should.
          Recommending items, preparing quotes and tracking orders are things you switch on
          yourself. We may change, add or remove features, and we will try to give notice of a
          change that removes something you rely on.
        </p>
      </LegalSection>

      <LegalSection title="2. Your account">
        <LegalList>
          <li>Give accurate details and keep your sign-in email under your control.</li>
          <li>
            Everything you add is yours to answer for. Make sure you have the right to upload it,
            and keep prices, hours and policies current, because the assistant answers from them.
          </li>
          <li>
            You are responsible for how you use your customers&apos; conversations, and for telling
            your customers what the assistant is and where to read the privacy page, which is linked
            from the footer of your page.
          </li>
        </LegalList>
      </LegalSection>

      <LegalSection title="3. Your content">
        <p>
          You keep ownership of what you add. You give us permission to store it, process it, and
          send the necessary parts to the providers named on the privacy page, for the one purpose
          of running your assistant. We do not use your content, or your customers&apos;
          conversations, to train models of our own.
        </p>
      </LegalSection>

      <LegalSection title="4. What you may not do">
        <LegalList>
          <li>Break the law, or use Agencx to deceive, harass or defraud anyone.</li>
          <li>Upload content you have no right to use, or that is defamatory or abusive.</li>
          <li>
            Use it for emergencies. The assistant is not a way to reach emergency services or a
            replacement for professional medical, legal or financial advice.
          </li>
          <li>
            Try to break, overload or probe the service, get around its limits, scrape it, or
            reach another business&apos;s data.
          </li>
          <li>
            Ask customers to type card numbers, passwords or other sensitive details into the chat.
          </li>
        </LegalList>
        <p>
          We may suspend a page while we look into a breach of this section, and we will tell you
          why.
        </p>
      </LegalSection>

      <LegalSection title="5. Answers from the assistant">
        <p>
          A language model writes the replies, and it can be wrong, incomplete or out of date. It is
          only as good as the information the business gave it. Treat an answer as general
          information, not advice, and confirm anything important with the business directly. The
          business, not Agencx, is responsible for what its page tells its customers.
        </p>
        <p>
          The assistant is not a person and says so if you ask. It passes a conversation to a person
          at the business when it should, but we cannot promise it always will, or that anyone will
          reply by a particular time.
        </p>
      </LegalSection>

      <LegalSection title="6. Quotes">
        <p>
          A quote is an estimate, not an offer and not a contract. The language model never
          produces a price. It only picks which of the business&apos;s items and quantities you
          mean; the amount is then worked out by a fixed pricing engine from the prices and rules
          the business entered. The business decides whether to honor a quote, and the final price
          is whatever the business confirms. If a quote looks wrong, ask the business.
        </p>
      </LegalSection>

      <LegalSection title="7. Fees">
        <p>
          Agencx is currently free to use. If that changes we will tell you before you are charged
          anything, and nothing in these terms obliges you to pay.
        </p>
      </LegalSection>

      <LegalSection title="8. Availability">
        <p>
          We provide Agencx as it is. We aim to keep it running but we do not guarantee it will
          always be available, fast or free of errors, and it depends on other companies&apos;
          services that can be slow or down. We may pause it for maintenance.
        </p>
      </LegalSection>

      <LegalSection title="9. Ending your account">
        <p>
          You can stop using Agencx at any time and ask for your data to be exported, deleted or
          both, as described on the privacy page; we answer within {REQUEST_DAYS} days. We may
          suspend or end an account that breaks these terms, or stop the service altogether, and
          where we can we will give notice and a chance to export your data first. When an account
          ends, our permission to use your content ends with it.
        </p>
      </LegalSection>

      <LegalSection title="10. Liability">
        <p>
          To the extent the law allows, we are not liable for indirect or consequential loss,
          including lost sales or profit, from a wrong answer, an estimate, a page being unavailable
          or a message not being seen. Our total liability to you for anything connected with
          Agencx is limited to {LEGAL.liabilityCap}. Nothing here excludes a right you have under
          the law that cannot be excluded, including under the Australian Consumer Law.
        </p>
      </LegalSection>

      <LegalSection title="11. The rest">
        <p>
          These terms are governed by the law of {LEGAL.jurisdiction}. If we change them in a way
          that matters we will update the date above and tell business owners; continuing to use
          Agencx afterwards means you accept the change. Write to {LEGAL.contactEmail} with any
          question.
        </p>
      </LegalSection>
    </LegalDoc>
  );
}
