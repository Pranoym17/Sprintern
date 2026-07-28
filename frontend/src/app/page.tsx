import Image from "next/image";
import Link from "next/link";

import { Brand } from "@/components/brand";
import { MarketingHeaderActions } from "@/components/marketing-header-actions";
import { SiteFooter } from "@/components/site-footer";

const companies = [
  { name: "Google", logo: "/company-logos/google.svg" },
  { name: "Apple", logo: "/company-logos/apple.svg" },
  { name: "NVIDIA", logo: "/company-logos/nvidia.svg" },
  { name: "Shopify", logo: "/company-logos/shopify.svg" },
  { name: "Meta", logo: "/company-logos/meta.svg" },
];

const previewJobs = [
  { company: "Google", logo: "/company-logos/google.svg", title: "Software Developer Intern", place: "Toronto, ON", term: "Summer 2027", age: "4m" },
  { company: "Shopify", logo: "/company-logos/shopify.svg", title: "Backend Engineering Intern", place: "Remote, Canada", term: "Summer 2027", age: "11m" },
  { company: "NVIDIA", logo: "/company-logos/nvidia.svg", title: "Systems Software Intern", place: "Toronto, ON", term: "Fall 2026", age: "18m" },
];

const steps = [
  ["01", "Set your signal", "Choose the roles, locations, terms, and work modes that matter. Exclusions keep the obvious noise out."],
  ["02", "Sprintern keeps watch", "Fresh postings are normalized, checked, and matched against your criteria throughout the day."],
  ["03", "Move while the role is fresh", "Telegram sends the fast alert. Email gives you a considered daily shortlist. Both keep the original application link."],
];

export default function Home() {
  return (
    <main className="marketing-page marketing-page--editorial">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header site-header--editorial">
        <div className="site-header__inner">
          <Brand />
          <nav className="site-nav" aria-label="Primary navigation">
            <a href="#product">Product</a>
            <a href="#how-it-works">How it works</a>
            <a href="#principles">Why Sprintern</a>
          </nav>
          <MarketingHeaderActions />
        </div>
      </header>

      <section className="editorial-hero" id="main-content">
        <div className="editorial-hero__copy">
          <p className="editorial-eyebrow"><span /> Built for the application window</p>
          <h1>Stop refreshing.<br /><em>Start applying.</em></h1>
          <p>Sprintern watches for internships that fit, then gets the useful ones in front of you while they are still fresh.</p>
          <div className="editorial-hero__actions">
            <Link className="button button--primary" href="/sign-up">Create your free alert <span aria-hidden="true">↗</span></Link>
            <a className="editorial-text-link" href="#product">See the product <span aria-hidden="true">↓</span></a>
          </div>
          <ul className="hero-assurances" aria-label="Product assurances">
            <li>No credit card</li>
            <li>Direct application links</li>
            <li>Pause any time</li>
          </ul>
        </div>

        <div className="product-stage" id="product" aria-label="Preview of the Sprintern match feed">
          <div className="product-stage__chrome">
            <span className="product-stage__label">Live matches</span>
            <span className="product-stage__status"><i /> Watching</span>
          </div>
          <div className="product-stage__summary">
            <div><strong>3</strong><span>new roles<br />worth a look</span></div>
            <p>Software · Canada<br />Summer 2027</p>
          </div>
          <div className="preview-feed">
            {previewJobs.map((job, index) => (
              <article className={index === 0 ? "preview-job preview-job--new" : "preview-job"} key={job.company}>
                <span className="preview-job__logo"><Image src={job.logo} alt="" width={24} height={24} /></span>
                <div><small>{job.company}</small><strong>{job.title}</strong><span>{job.place} · {job.term}</span></div>
                <time>{job.age}</time>
                <span className="preview-job__action" aria-hidden="true">↗</span>
              </article>
            ))}
          </div>
          <div className="product-stage__alert">
            <span>New match sent to Telegram</span>
            <strong>Google · Software Developer Intern</strong>
          </div>
        </div>
      </section>

      <section className="company-rail" aria-labelledby="company-rail-title">
        <p id="company-rail-title">Watch the companies you care about</p>
        <div>
          {companies.map((company) => (
            <span key={company.name}><Image src={company.logo} alt="" width={26} height={26} /><b>{company.name}</b></span>
          ))}
        </div>
        <small>Illustrative employers. Role availability changes.</small>
      </section>

      <section className="editorial-section process-section" id="how-it-works">
        <div className="editorial-section__heading">
          <p className="section-kicker">A quieter job search</p>
          <h2>Three steps.<br />No daily scavenger hunt.</h2>
        </div>
        <div className="process-list">
          {steps.map(([number, title, copy]) => (
            <article key={number}>
              <span>{number}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="editorial-section product-principles" id="principles">
        <div className="product-principles__statement">
          <p className="section-kicker">The useful parts, kept visible</p>
          <h2>A focused feed, not another job board.</h2>
          <p>Every screen is built around the next decision: review, save, apply, or move on.</p>
        </div>
        <div className="principle-list">
          <article><span>01</span><div><h3>One clean view</h3><p>Repeated listings are collapsed while genuinely different roles stay visible.</p></div></article>
          <article><span>02</span><div><h3>Alerts with restraint</h3><p>Telegram moves instantly. Email sends a ranked daily shortlist at your chosen time.</p></div></article>
          <article><span>03</span><div><h3>Your process, intact</h3><p>Save roles, track applications, add notes, and keep deadlines in one place.</p></div></article>
        </div>
      </section>

      <section className="editorial-cta">
        <div className="editorial-cta__copy">
          <p className="section-kicker">Ready when the next role opens</p>
          <h2>Set your criteria once.<br />Keep the head start.</h2>
          <Link className="button button--paper" href="/sign-up">Build your first alert <span aria-hidden="true">↗</span></Link>
        </div>
        <Image className="editorial-cta__mark" src="/brand/sprintern-metallic.png" alt="" width={1056} height={600} />
      </section>

      <SiteFooter />
    </main>
  );
}
