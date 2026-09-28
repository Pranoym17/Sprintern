import Link from "next/link";

export function ServicePausedCard() {
  return (
    <div className="auth-card">
      <span className="section-kicker">Portfolio showcase</span>
      <h2>The live service is currently paused.</h2>
      <p>
        Sprintern is not accepting sign-ups or running job alerts right now. The project remains
        available as a portfolio demonstration and can be brought back online in the future.
      </p>
      <Link className="button button--dark" href="/">
        Return to Sprintern
      </Link>
    </div>
  );
}
