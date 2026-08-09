import { ApiStatus } from "@/components/api-status";

export default function Home() {
  const appEnvironment = process.env.NEXT_PUBLIC_APP_ENV ?? "local";

  return (
    <main className="shell">
      <section className="foundation-card" aria-labelledby="page-title">
        <p className="eyebrow">Foundation stage · {appEnvironment}</p>
        <h1 id="page-title">ScentIQ</h1>
        <p className="lede">
          The application foundation is online. Product capabilities will be
          introduced in the next milestone.
        </p>
        <ApiStatus />
      </section>
    </main>
  );
}
