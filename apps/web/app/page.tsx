import { SignedIn, SignedOut } from "@clerk/nextjs";
import { ArrowRight, BarChart3, Beaker, CalendarDays, CloudSun, Compass, Sparkles } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDemoFragranceById, getDemoToday } from "@/lib/demo";

const features = [
  [Sparkles, "Collection", "One considered view of every bottle, decant, and sample."],
  [CloudSun, "Weather-aware", "Match projection and character to the forecast."],
  [CalendarDays, "Event-aware", "Move from a workday to dinner without guessing."],
  [BarChart3, "Insights", "See what earns wear, what overlaps, and what is missing."],
  [Beaker, "Layering Lab", "Explore thoughtful pairs from the scents you own."],
  [Compass, "Discover", "Find additions that expand rather than repeat."],
] as const;

export default function Home() {
  const today = getDemoToday();
  const fragrance = getDemoFragranceById(today.recommendation.primary.fragranceId)!;
  return (
    <main className="landing">
      <nav className="landing-nav container" aria-label="Marketing navigation">
        <Link href="/" className="brand"><span className="brand__mark">S</span><span>ScentIQ</span></Link>
        <SignedIn><Button asChild size="sm"><Link href="/dashboard">Open ScentIQ <ArrowRight size={16} /></Link></Button></SignedIn>
        <SignedOut><Button asChild size="sm"><Link href="/sign-in">Sign in <ArrowRight size={16} /></Link></Button></SignedOut>
      </nav>
      <section className="hero container">
        <div className="hero__copy">
          <Badge>Personal fragrance intelligence</Badge>
          <h1 className="serif">ScentIQ</h1>
          <p className="hero__lede">Your life already has a rhythm. Wear a fragrance that belongs in it.</p>
          <p className="muted">ScentIQ considers your collection, the weather, and what is next—then offers a clear, personal recommendation.</p>
          <div className="cluster"><SignedIn><Button asChild><Link href="/dashboard">Open ScentIQ <ArrowRight size={17} /></Link></Button></SignedIn><SignedOut><Button asChild><Link href="/sign-in">Sign in <ArrowRight size={17} /></Link></Button></SignedOut><Button asChild variant="ghost"><Link href="#how-it-works">See how it works</Link></Button></div>
        </div>
        <div className="hero__preview" aria-label="Today recommendation preview">
          <div className="preview-top"><span>{today.weather.condition} · {today.weather.high}°</span><Badge>{today.recommendation.primary.score}% match</Badge></div>
          <div className="bottle-art" style={{ "--bottle-tone": fragrance.tone } as React.CSSProperties}><span>{fragrance.brand}</span><strong>{fragrance.name}</strong></div>
          <p className="eyebrow">Recommended today</p>
          <h2 className="serif">{fragrance.name}</h2>
          <p>{today.recommendation.primary.reason}</p>
          <div className="preview-reasons">{today.recommendation.reasons.map((reason) => <span key={reason}>{reason}</span>)}</div>
        </div>
      </section>
      <section className="value-strip"><div className="container"><strong>Collection + schedule + weather</strong><span>→</span><em>What should I wear?</em></div></section>
      <section className="landing-section container">
        <p className="eyebrow">A wardrobe that thinks ahead</p>
        <h2 className="serif">Less scrolling. Better choices.</h2>
        <div className="feature-grid">{features.map(([Icon, title, copy]) => <article key={title}><Icon size={22} /><h3>{title}</h3><p>{copy}</p></article>)}</div>
      </section>
      <section id="how-it-works" className="landing-section landing-how"><div className="container"><p className="eyebrow">How it works</p><h2 className="serif">Your taste becomes useful context.</h2><ol><li><span>01</span><strong>Add your collection</strong><p>Bottles, decants, samples, and ratings.</p></li><li><span>02</span><strong>Set the scene</strong><p>Schedule connections arrive later; the demo shows the idea now.</p></li><li><span>03</span><strong>Choose with confidence</strong><p>Wear, log, and let future recommendations improve.</p></li></ol></div></section>
      <footer className="landing-footer container"><span className="serif">ScentIQ</span><span>Interactive demo · Product data is illustrative</span></footer>
    </main>
  );
}
