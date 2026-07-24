import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  Check,
  ExternalLink,
  Filter,
  Layers3,
  MapPin,
  Radio,
  Sparkles,
} from "lucide-react";

import { Brand } from "@/components/brand";
import { SiteFooter } from "@/components/site-footer";

const steps = [
  { number: "01", title: "We watch for openings", copy: "Sprintern checks for new internships throughout the day." },
  { number: "02", title: "Your rules cut the noise", copy: "Role, location, term, and work-mode filters create a short list you can actually act on." },
  { number: "03", title: "You hear about matches", copy: "Get an email or Telegram alert with the original application link." },
];

export default function Home() {
  return (
    <main className="marketing-page">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header">
        <div className="site-header__inner">
          <Brand />
          <nav className="site-nav" aria-label="Primary navigation">
            <a href="#how-it-works">How it works</a>
            <a href="#features">Features</a>
            <a href="#coverage">Job coverage</a>
          </nav>
          <div className="header-actions">
            <Link className="text-link" href="/sign-in">Sign in</Link>
            <Link className="button button--dark button--small" href="/sign-up">Start tracking <ArrowRight size={16} /></Link>
          </div>
        </div>
      </header>

      <section className="hero" id="main-content">
        <div className="hero__copy">
          <div className="eyebrow"><span className="status-dot" /> Internship signal is live</div>
          <h1>Stop finding internships <em>after everyone else.</em></h1>
          <p className="hero__lede">Sprintern watches new software internships, filters out the noise, and sends the right roles straight to you.</p>
          <div className="hero__actions">
            <Link className="button button--primary" href="/sign-up">Create your alert <ArrowRight size={18} /></Link>
            <a className="button button--ghost" href="#how-it-works">See how it works</a>
          </div>
          <p className="hero__note"><Check size={16} /> Free to use · Original application links</p>
        </div>

        <div className="signal-stage" aria-label="Illustration of an internship passing through Sprintern's matching pipeline">
          <div className="orbit orbit--outer" />
          <div className="orbit orbit--middle" />
          <div className="orbit orbit--inner" />
          <div className="source-node source-node--github"><Layers3 size={18} /><span>New internships</span></div>
          <div className="source-node source-node--role"><Sparkles size={18} /><span>Software</span></div>
          <div className="source-node source-node--place"><MapPin size={18} /><span>Toronto</span></div>
          <div className="signal-core">
            <span className="signal-core__icon"><Radio size={24} /></span>
            <strong>1 match</strong>
            <small>ready to send</small>
          </div>
          <div className="alert-card">
            <span className="alert-card__icon"><BellRing size={18} /></span>
            <span><strong>New match</strong><small>Software Engineer Intern</small></span>
            <ArrowRight size={16} />
          </div>
        </div>
      </section>

      <section className="proof-strip" aria-label="Current capabilities">
        <span><Layers3 size={18} /> Continuously updated jobs</span>
        <span><Radio size={18} /> Scheduled monitoring</span>
        <span><BellRing size={18} /> Email and Telegram alerts</span>
        <span><ExternalLink size={18} /> Direct apply links</span>
      </section>

      <section className="section" id="how-it-works">
        <div className="section-heading"><span className="section-kicker">A quieter job search</span><h2>From noisy board to useful alert.</h2><p>The pipeline is deliberately simple, inspectable, and built around your criteria.</p></div>
        <div className="steps-grid">
          {steps.map((step) => <article className="step-card" key={step.number}><span>{step.number}</span><h3>{step.title}</h3><p>{step.copy}</p></article>)}
        </div>
      </section>

      <section className="section feature-section" id="features">
        <div className="section-heading section-heading--left"><span className="section-kicker">Built for the application window</span><h2>Everything you need to move quickly.</h2></div>
        <div className="bento-grid">
          <article className="bento bento--wide"><span className="feature-icon"><Filter /></span><div><h3>Filters that read like your search</h3><p>Combine role, location, term, and work mode. Multiple choices within a field broaden your search; populated fields work together.</p></div><div className="filter-preview"><span>software</span><span>backend</span><span>Toronto</span><span>Summer 2027</span></div></article>
          <article className="bento"><span className="feature-icon feature-icon--teal"><BellRing /></span><h3>Alerts with the next action</h3><p>Telegram messages include the original application link, so the alert is useful the moment it arrives.</p></article>
          <article className="bento bento--ink"><span className="feature-icon"><Layers3 /></span><h3>One posting, not five copies</h3><p>Normalization and deduplication keep repeated listings from rebuilding your job list.</p></article>
        </div>
      </section>

      <section className="section source-section" id="coverage">
        <div><span className="section-kicker">One useful feed</span><h2>Consistent listings, direct applications.</h2></div>
        <div><p>Sprintern normalizes public job information into one clean feed and preserves the employer application link whenever it is available.</p><p className="source-footnote">Postings can change or expire. Sprintern monitors freshness and makes uncertainty visible instead of silently dropping jobs.</p><Link className="inline-link" href="/data-sources">How job data and accuracy work</Link></div>
      </section>

      <section className="final-cta"><span className="section-kicker">Your next application could arrive first</span><h2>Set the signal once.<br />Let Sprintern keep watch.</h2><Link className="button button--paper" href="/sign-up">Create a free alert <ArrowRight size={18} /></Link></section>
      <SiteFooter />
    </main>
  );
}
