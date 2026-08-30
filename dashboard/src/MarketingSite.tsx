const whatsappUrl =
  "https://wa.me/94764460037?text=URGENT%3A%20Your%20bank%20account%20will%20be%20suspended.%20Click%20http%3A%2F%2Ffake-bank.example%2Flogin";

const sections = [
  {
    label: "1",
    title: "Forward anything suspicious",
    body: "Send a suspicious message, link, image, or voice note to AEGIS directly on WhatsApp.",
  },
  {
    label: "2",
    title: "The agent investigates",
    body: "Gemini analyzes manipulation patterns, checks shared threat memory, and prepares a plain-language verdict.",
  },
  {
    label: "3",
    title: "You get safer next steps",
    body: "AEGIS replies in the same chat with the risk level, why it looks dangerous, and what to do next.",
  },
];

const stats = [
  ["Channel", "WhatsApp-native"],
  ["Runtime", "Cloud Run"],
  ["Agent", "Google ADK + Gemini"],
  ["Memory", "Firestore + Pub/Sub"],
];

export function MarketingSite() {
  return (
    <div className="min-h-screen bg-[#f6f8fb] text-[#15202b]">
      <header className="fixed inset-x-0 top-0 z-30 border-b border-white/20 bg-[#071017]/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-3" aria-label="AEGIS Scam Guard home">
            <img src="/assets/aegis-logo.png" alt="" className="h-10 w-10 rounded" />
            <span className="text-sm font-semibold text-white">AEGIS Scam Guard</span>
          </a>
          <nav className="hidden items-center gap-7 text-sm text-slate-200 md:flex">
            <a href="#problem" className="hover:text-white">
              Problem
            </a>
            <a href="#solution" className="hover:text-white">
              Solution
            </a>
            <a href="#proof" className="hover:text-white">
              Proof
            </a>
          </nav>
          <a
            href={whatsappUrl}
            className="rounded bg-[#1fa855] px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#178a45]"
          >
            Try on WhatsApp
          </a>
        </div>
      </header>

      <main>
        <section className="relative flex min-h-[92vh] items-end overflow-hidden bg-[#071017] pt-24 text-white">
          <img
            src="/screenshots/whatsapp-scam-verdict.png"
            alt=""
            className="absolute inset-y-0 right-0 h-full w-full object-cover opacity-24"
          />
          <div className="absolute inset-0 bg-[linear-gradient(90deg,#071017_0%,rgba(7,16,23,.92)_36%,rgba(7,16,23,.42)_100%)]" />
          <div className="relative z-10 mx-auto grid w-full max-w-7xl gap-10 px-4 pb-16 sm:px-6 lg:grid-cols-[1.05fr_.95fr] lg:px-8">
            <div className="max-w-3xl">
              <p className="mb-5 text-sm font-semibold uppercase tracking-[0.28em] text-[#83e6ad]">
                WhatsApp-native AI scam protection
              </p>
              <h1 className="max-w-4xl text-5xl font-semibold leading-tight sm:text-6xl lg:text-7xl">
                AEGIS Scam Guard
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-200">
                Forward a suspicious message to AEGIS and get a fast, plain-language scam risk verdict powered
                by a production agent running on Gemini and Google Cloud.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <a
                  href={whatsappUrl}
                  className="rounded bg-[#1fa855] px-6 py-3 text-center text-sm font-semibold text-white shadow-lg shadow-green-950/40 hover:bg-[#178a45]"
                >
                  Message +94 76 446 0037
                </a>
                <a
                  href="#proof"
                  className="rounded border border-white/30 px-6 py-3 text-center text-sm font-semibold text-white hover:bg-white/10"
                >
                  View Live Proof
                </a>
              </div>
            </div>

            <div className="self-end border-l border-white/20 pl-6">
              <div className="grid grid-cols-2 gap-x-8 gap-y-6">
                {stats.map(([name, value]) => (
                  <div key={name}>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{name}</p>
                    <p className="mt-2 text-base font-semibold text-white">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="problem" className="bg-white py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid gap-12 lg:grid-cols-[.9fr_1.1fr]">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#c03a2b]">The problem</p>
                <h2 className="mt-4 text-3xl font-semibold leading-tight sm:text-4xl">
                  Scam messages reach people before help does.
                </h2>
              </div>
              <div className="grid gap-5 text-base leading-7 text-slate-700 sm:grid-cols-2">
                <p>
                  Fraudsters use urgency, fake authority, and convincing links to push people into decisions
                  before they can verify what is real.
                </p>
                <p>
                  Most victims already have WhatsApp open. What they do not have is a fast security analyst in
                  the same conversation, explaining the risk in simple language.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section id="solution" className="bg-[#edf4f7] py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl">
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#176b87]">The solution</p>
              <h2 className="mt-4 text-3xl font-semibold leading-tight sm:text-4xl">
                An autonomous agent that turns forwarded messages into protective action.
              </h2>
            </div>
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              {sections.map((item) => (
                <article key={item.title} className="rounded border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex h-10 w-10 items-center justify-center rounded bg-[#0c2731] text-sm font-semibold text-white">
                    {item.label}
                  </div>
                  <h3 className="mt-5 text-lg font-semibold">{item.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-600">{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="proof" className="bg-[#071017] py-20 text-white">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid gap-10 lg:grid-cols-[.85fr_1.15fr]">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#83e6ad]">Production proof</p>
                <h2 className="mt-4 text-3xl font-semibold leading-tight sm:text-4xl">
                  Built on real Google Cloud infrastructure.
                </h2>
                <p className="mt-5 text-base leading-7 text-slate-300">
                  AEGIS uses Cloud Run services, Pub/Sub, Firestore, Cloud KMS, Scheduler, and Gemini through an
                  agent workflow. The deployed WhatsApp bot can be tested directly from the call to action.
                </p>
                <a
                  href={whatsappUrl}
                  className="mt-8 inline-block rounded bg-[#1fa855] px-6 py-3 text-sm font-semibold text-white hover:bg-[#178a45]"
                >
                  Send a Test Message
                </a>
              </div>
              <div className="grid gap-4">
                <img
                  src="/screenshots/gcp-console.png"
                  alt="Google Cloud Console showing AEGIS Cloud Run services"
                  className="w-full rounded border border-white/10"
                />
                <img
                  src="/screenshots/gcp-logs-webhook-message-sent.png"
                  alt="Google Cloud Logs Explorer showing live AEGIS webhook and message logs"
                  className="w-full rounded border border-white/10"
                />
              </div>
            </div>
          </div>
        </section>

        <section className="bg-white py-16">
          <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
            <div>
              <h2 className="text-2xl font-semibold">Check a suspicious message now.</h2>
              <p className="mt-2 text-slate-600">Forward it to AEGIS Scam Guard on WhatsApp.</p>
            </div>
            <a
              href={whatsappUrl}
              className="rounded bg-[#1fa855] px-6 py-3 text-center text-sm font-semibold text-white hover:bg-[#178a45]"
            >
              Open WhatsApp
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 text-sm text-slate-600 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <p>AEGIS Scam Guard</p>
          <p>
            Created by{" "}
            <a href="https://srimonishan.com/" className="font-semibold text-[#176b87] hover:text-[#0c2731]">
              Srimonishan
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
