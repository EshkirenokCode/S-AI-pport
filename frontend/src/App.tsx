import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownLeft,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock,
  Copy,
  CreditCard,
  FileText,
  Inbox,
  Layers,
  LoaderCircle,
  LockKeyhole,
  MessageSquare,
  MoreHorizontal,
  Play,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Square,
  TriangleAlert,
  Unplug,
  X,
  Zap,
} from "lucide-react";
import type {
  Account,
  Action,
  Run,
  RunEvent,
  Session,
  Source,
  Ticket,
} from "./types";

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const r = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!r.ok) {
    const d = await r
      .json()
      .catch(() => ({ detail: "The service could not be reached." }));
    throw new Error(
      typeof d.detail === "string"
        ? d.detail
        : "The request could not be completed.",
    );
  }
  return r.json();
}
const busy = (r: Run | null) => !!r && ["queued", "running"].includes(r.status);
const label = (v: string) =>
  ({
    waiting_for_approval: "Awaiting approval",
    needs_human: "Needs review",
    completed: "Completed",
    queued: "Queued",
    running: "Investigating",
    cancelled: "Cancelled",
    failed: "Failed",
  })[v] || v.replaceAll("_", " ");
const initials = (s: string) =>
  s
    .split(" ")
    .map((x) => x[0])
    .slice(0, 2)
    .join("");
const short = (s: string) => s.slice(0, 8);
const familyIcon = (s: string) =>
  s === "billing" ? (
    <CreditCard size={15} />
  ) : s === "integration" ? (
    <Unplug size={15} />
  ) : (
    <SlidersHorizontal size={15} />
  );
const steps: Record<string, string> = {
  get_account_context: "Account identified",
  get_billing_state: "Payment and access checked",
  get_delivery_state: "Delivery attempts inspected",
  search_documentation: "Relevant procedures found",
  read_document: "Procedure and version checked",
  propose_action: "A precise repair proposed",
  finish_investigation: "Findings prepared",
};

export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [tickets, setTickets] = useState<Ticket[]>([]),
    [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<{
      ticket: Ticket;
      account: Account;
      run_id: string | null;
    } | null>(null),
    [run, setRun] = useState<Run | null>(null);
  const [provider, setProvider] = useState<"deterministic" | "openrouter">(
      "deterministic",
    ),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all");
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [pending, setPending] = useState(false),
    [tab, setTab] = useState("investigation");
  const [modal, setModal] = useState<"settings" | "activity" | "help" | null>(
      null,
    ),
    [source, setSource] = useState<Source | null>(null),
    [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [draft, setDraft] = useState(""),
    [saved, setSaved] = useState(false),
    [copied, setCopied] = useState(false),
    [mobileQueue, setMobileQueue] = useState(false),
    [connected, setConnected] = useState(true);
  const booted = useRef(false),
    draftDirty = useRef(false),
    selectedRef = useRef(selected);
  selectedRef.current = selected;
  const loadQueue = useCallback(async () => {
    const ts = await api<Ticket[]>("/tickets");
    setTickets(ts);
    return ts;
  }, []);
  const bootstrap = useCallback(
    async (role?: string) => {
      setLoading(true);
      setError("");
      try {
        if (role)
          await api("/demo/session", {
            method: "POST",
            body: JSON.stringify({ role }),
          });
        let s: Session;
        try {
          s = await api<Session>("/session");
        } catch {
          await api("/demo/session", { method: "POST", body: "{}" });
          s = await api<Session>("/session");
        }
        setSession(s);
        setProvider(s.provider);
        const ts = await loadQueue();
        setSelected(ts[0]?.id || "");
        setRun(null);
        setModal(null);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [loadQueue],
  );
  useEffect(() => {
    if (!booted.current) {
      booted.current = true;
      void bootstrap();
    }
  }, [bootstrap]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setDetail(null);
    setRun(null);
    setTab("investigation");
    setSaved(false);
    setDraft("");
    draftDirty.current = false;
    api<NonNullable<typeof detail>>("/tickets/" + selected)
      .then(async (d) => {
        if (!active) return;
        setDetail(d);
        if (d.run_id) {
          const r = await api<Run>("/runs/" + d.run_id);
          if (active) {
            setRun(r);
            setDraft(r.result.reply || "");
          }
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [selected]);
  const runId = run?.id;
  useEffect(() => {
    if (!runId) return;
    let active = true;
    const tid = selectedRef.current;
    const refresh = async () => {
      try {
        const r = await api<Run>("/runs/" + runId);
        if (!active) return;
        setRun(r);
        setConnected(true);
        if (!["queued", "running"].includes(r.status)) {
          await loadQueue();
          const d = await api<NonNullable<typeof detail>>("/tickets/" + tid);
          if (active) {
            setDetail(d);
            if (!draftDirty.current) setDraft(r.result.reply || "");
          }
        }
        if (
          ["completed", "needs_human", "failed", "cancelled"].includes(r.status)
        ) {
          clearInterval(timer);
          es.close();
        }
      } catch {
        if (active) setConnected(false);
      }
    };
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, 1500);
    const es = new EventSource("/api/runs/" + runId + "/events");
    es.onmessage = () => {
      void refresh();
    };
    es.onerror = () => setConnected(false);
    es.onopen = () => setConnected(true);
    return () => {
      active = false;
      clearInterval(timer);
      es.close();
    };
  }, [runId, loadQueue]);
  async function start() {
    if (!detail) return;
    setPending(true);
    setError("");
    setDraft("");
    draftDirty.current = false;
    try {
      const r = await api<{ id: string }>(
        "/tickets/" + detail.ticket.id + "/runs",
        { method: "POST", body: JSON.stringify({ provider }) },
      );
      const fresh = await api<Run>("/runs/" + r.id);
      setRun(fresh);
      await loadQueue();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function decision(action: Action, value: "approve" | "reject") {
    setPending(true);
    setError("");
    try {
      await api("/actions/" + action.id + "/decision", {
        method: "POST",
        body: JSON.stringify({ decision: value, digest: action.digest }),
      });
      const fresh = await api<Run>("/runs/" + run!.id);
      setRun(fresh);
      setDraft("");
      draftDirty.current = false;
      await loadQueue();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function cancel() {
    if (!run) return;
    try {
      await api("/runs/" + run.id + "/cancel", { method: "POST" });
      setRun(await api<Run>("/runs/" + run.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function save() {
    if (!run) return;
    try {
      await api("/runs/" + run.id + "/draft", {
        method: "PATCH",
        body: JSON.stringify({ reply: draft }),
      });
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function openSource(s: Source) {
    try {
      setSource(await api<Source>("/documents/" + s.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function activity() {
    setModal("activity");
    try {
      setMetrics(await api("/metrics"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const visible = tickets.filter(
    (t) =>
      (t.subject + " " + t.customer + " " + t.number)
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "approval" && t.run_status === "waiting_for_approval") ||
        (filter === "open" &&
          !["completed", "cancelled"].includes(t.run_status || ""))),
  );
  const waiting = tickets.filter(
    (t) => t.run_status === "waiting_for_approval",
  ).length;
  const sources: Source[] = [];
  for (const e of run?.events || []) {
    for (const s of [
      ...(e.data.result?.documents || []),
      ...(e.data.result?.document ? [e.data.result.document] : []),
    ])
      if (!sources.some((d) => d.id === s.id)) sources.push(s);
  }
  const tools =
    run?.events.filter((e) => e.kind === "tool" || e.kind === "tool_error") ||
    [];
  const activeAction = run?.actions[0];
  const t = detail?.ticket;
  if (loading && !session)
    return (
      <div className="boot">
        <div className="brand-icon">
          s<span>✳</span>
        </div>
        <h1>Opening your workspace</h1>
        <p>Preparing an isolated demo with synthetic accounts.</p>
        <LoaderCircle className="spin" />
      </div>
    );
  return (
    <div className="app-shell">
      <nav className="rail" aria-label="Main navigation">
        <a className="brand-icon" href="/" aria-label="S(AI)pport home">
          s<span>✳</span>
        </a>
        <div className="rail-group">
          <button
            className="rail-button selected"
            aria-label="Ticket queue"
            onClick={() => {
              setMobileQueue((v) => !v);
              setModal(null);
            }}
          >
            <Inbox size={22} />
          </button>
          <button
            className="rail-button"
            aria-label="Workspace activity"
            onClick={() => void activity()}
          >
            <Activity size={22} />
          </button>
          <button
            className="rail-button"
            aria-label="Workspace settings"
            onClick={() => setModal("settings")}
          >
            <Settings2 size={22} />
          </button>
        </div>
        <div className="rail-bottom">
          <button
            className="rail-button"
            aria-label="Demo guide"
            onClick={() => setModal("help")}
          >
            <CircleHelp size={21} />
          </button>
          <div className="operator-avatar" title={session?.name}>
            IG
          </div>
        </div>
      </nav>
      <div className="workspace">
        <header className="topbar">
          <div className="wordmark">
            s(ai)pport
            <span className="wordmark-divider" />
            <span className="workspace-name">
              Acme workspace <ChevronDown size={13} />
            </span>
          </div>
          <div className="topbar-right">
            <span className="demo-badge">
              <span />
              Synthetic demo
            </span>
            <button
              className="operator-switch"
              onClick={() => setModal("settings")}
            >
              <span className="tiny-avatar">
                {session?.role === "analyst" ? "DA" : "DO"}
              </span>
              <span>
                {session?.role === "analyst" ? "Analyst" : "Operator"}
              </span>
              <ChevronDown size={13} />
            </button>
          </div>
        </header>
        <div className="page-heading">
          <div>
            <div className="eyebrow">
              YOUR SUPPORT DESK, WITH A SECOND PAIR OF EYES
            </div>
            <h1>
              Make the next move<span className="orange-dot">.</span>
            </h1>
            <p>From a customer question to a checked, approved resolution.</p>
          </div>
          <button
            className="outline-button guide-button"
            onClick={() => setModal("help")}
          >
            <Play size={14} /> Explore the demo <ArrowUpRight size={15} />
          </button>
        </div>
        <main className="desk">
          <aside className={"queue " + (mobileQueue ? "mobile-open" : "")}>
            <div className="queue-heading">
              <h2>
                Inbox <span>{tickets.length}</span>
              </h2>
              <button
                className="icon-button"
                aria-label="Inbox filters"
                onClick={() =>
                  setFilter((v) => (v === "approval" ? "all" : "approval"))
                }
              >
                <SlidersHorizontal size={17} />
              </button>
            </div>
            <label className="search">
              <Search size={16} />
              <input
                placeholder="Search tickets…"
                aria-label="Search tickets"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <kbd>⌕</kbd>
            </label>
            <div className="queue-filters">
              {[
                ["all", "All tickets"],
                ["open", "Open"],
                ["approval", "Approval"],
              ].map(([v, l]) => (
                <button
                  key={v}
                  className={filter === v ? "active" : ""}
                  onClick={() => setFilter(v)}
                >
                  {l}
                  {v === "approval" && waiting > 0 ? (
                    <span>{waiting}</span>
                  ) : null}
                </button>
              ))}
            </div>
            <div className="ticket-list">
              {visible.map((ticket) => (
                <button
                  key={ticket.id}
                  className={
                    "ticket-row " + (selected === ticket.id ? "active" : "")
                  }
                  onClick={() => {
                    setSelected(ticket.id);
                    setMobileQueue(false);
                  }}
                >
                  <div className="ticket-row-top">
                    <span
                      className={"customer-avatar tone-" + (ticket.number % 4)}
                    >
                      {initials(ticket.customer)}
                    </span>
                    <span className="customer-name">{ticket.customer}</span>
                    <span className="ticket-number">#{ticket.number}</span>
                  </div>
                  <h3>{ticket.subject}</h3>
                  <p>{ticket.body}</p>
                  <div className="ticket-row-bottom">
                    <span className="family-tag">
                      {familyIcon(ticket.family)}
                      {ticket.family}
                    </span>
                    <span
                      className={
                        "ticket-status " + (ticket.run_status || "open")
                      }
                    >
                      <i />
                      {ticket.run_status === "waiting_for_approval"
                        ? "Approval"
                        : ticket.run_status
                          ? label(ticket.run_status)
                          : "Open"}
                    </span>
                  </div>
                </button>
              ))}
              {visible.length === 0 && (
                <div className="empty-small">
                  <Search />
                  <p>No tickets match this view.</p>
                  <button
                    onClick={() => {
                      setQuery("");
                      setFilter("all");
                    }}
                  >
                    Clear filters
                  </button>
                </div>
              )}
            </div>
            <div className="queue-foot">
              <LockKeyhole size={13} /> Your own isolated workspace
            </div>
          </aside>
          <section className="case-panel">
            {error && (
              <div className="error-banner" role="alert">
                <TriangleAlert size={17} />
                <span>{error}</span>
                <button aria-label="Dismiss error" onClick={() => setError("")}>
                  <X size={15} />
                </button>
              </div>
            )}
            {!detail ? (
              <div className="panel-loading">
                <LoaderCircle className="spin" />
                <p>
                  {error
                    ? "The workspace could not be loaded."
                    : "Loading ticket…"}
                </p>
                {error && (
                  <button
                    className="primary-button"
                    onClick={() => void bootstrap()}
                  >
                    Retry
                  </button>
                )}
              </div>
            ) : (
              <>
                <div className="case-header">
                  <button
                    className="mobile-back icon-button"
                    aria-label="Back to inbox"
                    onClick={() => setMobileQueue(true)}
                  >
                    <ArrowLeft size={18} />
                  </button>
                  <div className="breadcrumbs">
                    <span>Inbox</span>
                    <ChevronRight size={12} />
                    <span>#{t!.number}</span>
                  </div>
                  <span className={"priority " + t!.priority}>
                    <span />
                    {t!.priority === "high"
                      ? "High priority"
                      : "Normal priority"}
                  </span>
                  <button
                    className="icon-button"
                    aria-label="Ticket details"
                    onClick={() =>
                      setTab(tab === "details" ? "investigation" : "details")
                    }
                  >
                    <MoreHorizontal size={20} />
                  </button>
                </div>
                <div className="customer-message">
                  <div className="message-meta">
                    <div className={"customer-avatar tone-" + (t!.number % 4)}>
                      {initials(t!.customer)}
                    </div>
                    <div>
                      <strong>{t!.customer}</strong>
                      <span>{t!.email}</span>
                    </div>
                    <span className="message-channel">
                      <MessageSquare size={13} />
                      Customer message
                    </span>
                  </div>
                  <h2>{t!.subject}</h2>
                  <p>{t!.body}</p>
                  <div className="message-tags">
                    <span>
                      {familyIcon(t!.family)}
                      {t!.family}
                    </span>
                    <span>
                      <Layers size={13} />
                      Product {detail.account.product_version}
                    </span>
                  </div>
                </div>
                <div className="case-tabs">
                  <button
                    className={tab === "investigation" ? "active" : ""}
                    onClick={() => setTab("investigation")}
                  >
                    <Sparkles size={15} />
                    Investigation
                    {run && <span className="tab-count">{tools.length}</span>}
                  </button>
                  <button
                    className={tab === "evidence" ? "active" : ""}
                    onClick={() => setTab("evidence")}
                  >
                    <BookOpen size={15} />
                    Sources<span className="tab-count">{sources.length}</span>
                  </button>
                  <button
                    className={tab === "details" ? "active" : ""}
                    onClick={() => setTab("details")}
                  >
                    <FileText size={15} />
                    Run details
                  </button>
                </div>
                <div className="case-body">
                  {tab === "evidence" ? (
                    <div className="sources-view">
                      <div className="section-kicker">TRACEABLE BY DESIGN</div>
                      <h3>Every conclusion needs a source.</h3>
                      <p className="muted">
                        Versioned procedures used in this investigation. Account
                        facts are available in the timeline.
                      </p>
                      {sources.map((s) => (
                        <button
                          className="source-card"
                          key={s.id}
                          onClick={() => void openSource(s)}
                        >
                          <BookOpen size={20} />
                          <div>
                            <strong>{s.title}</strong>
                            <span>
                              Version {s.version} · {s.source_key}
                            </span>
                            <p>{s.body?.slice(0, 150)}…</p>
                          </div>
                          <ArrowUpRight size={18} />
                        </button>
                      ))}
                      {!sources.length && (
                        <div className="empty-small">
                          <BookOpen />
                          <p>Sources appear after documentation is searched.</p>
                        </div>
                      )}
                    </div>
                  ) : tab === "details" ? (
                    <div className="run-details">
                      <h3>Execution record</h3>
                      {run ? (
                        <>
                          <dl>
                            {[
                              ["Run ID", run.id],
                              ["State", label(run.status)],
                              [
                                "Provider",
                                run.provider === "deterministic"
                                  ? "Deterministic · offline"
                                  : "OpenRouter · live",
                              ],
                              ["Returned model", run.model || "Not applicable"],
                              ["Prompt", run.prompt_version],
                              ["Worker acquisitions", String(run.attempts)],
                              ["Tool transport", session?.transport || ""],
                              ["Tool calls", String(tools.length)],
                              ["Model calls", String(run.usage.length)],
                              [
                                "Reported cost",
                                run.usage.length
                                  ? run.usage.some((u) => u.cost === null)
                                    ? "Not reported"
                                    : "$" +
                                      run.usage
                                        .reduce(
                                          (a, u) => a + Number(u.cost || 0),
                                          0,
                                        )
                                        .toFixed(6)
                                  : "No model calls",
                              ],
                            ].map(([k, v]) => (
                              <div key={k}>
                                <dt>{k}</dt>
                                <dd>{v}</dd>
                              </div>
                            ))}
                          </dl>
                          <p className="hint">
                            The run ID connects the worker, tool evidence,
                            approval, and operation receipt. Private model
                            reasoning is never displayed.
                          </p>
                        </>
                      ) : (
                        <p className="muted">
                          Start an investigation to create an execution record.
                        </p>
                      )}
                    </div>
                  ) : (
                    <>
                      {!run ? (
                        <div className="investigation-intro">
                          <div className="intro-illustration">
                            <div className="orbit-line" />
                            <div className="intro-icon">
                              <Sparkles size={28} strokeWidth={1.6} />
                            </div>
                            <span className="floating-check">
                              <Check size={15} />
                            </span>
                            <span className="floating-source">
                              <FileText size={16} />
                            </span>
                          </div>
                          <div className="section-kicker">
                            LESS TAB-HOPPING. MORE CLARITY.
                          </div>
                          <h3>Let's find out what happened.</h3>
                          <p>
                            Check the account, connect the evidence, and find
                            the safest next step. You stay in control of every
                            repair.
                          </p>
                          <div className="investigation-checklist">
                            <span>
                              <CreditCard size={16} />
                              Inspect account & events
                            </span>
                            <span>
                              <BookOpen size={16} />
                              Find the right procedure
                            </span>
                            <span>
                              <ShieldCheck size={16} />
                              Propose a checked action
                            </span>
                          </div>
                          <button
                            className="primary-button"
                            onClick={() => void start()}
                            disabled={pending}
                          >
                            {pending ? (
                              <LoaderCircle size={16} className="spin" />
                            ) : (
                              <Sparkles size={16} />
                            )}
                            Start investigation
                            <ArrowRight size={16} />
                          </button>
                          <div className="provider-inline">
                            <span className="provider-dot" />
                            {provider === "deterministic"
                              ? "Offline · deterministic tool driver"
                              : "Live · OpenRouter free model"}
                            <button onClick={() => setModal("settings")}>
                              Change
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="run-heading">
                            <div>
                              <span className={"state-dot " + run.status} />
                              <strong>{label(run.status)}</strong>
                              {busy(run) && (
                                <LoaderCircle size={14} className="spin" />
                              )}
                            </div>
                            <div className="run-heading-right">
                              <span className="provider-label">
                                {run.provider === "deterministic"
                                  ? "OFFLINE"
                                  : "LIVE MODEL"}
                              </span>
                              {busy(run) ? (
                                <button
                                  className="text-button"
                                  onClick={() => void cancel()}
                                >
                                  <Square size={11} />
                                  Cancel
                                </button>
                              ) : (
                                <span className="mono">{short(run.id)}</span>
                              )}
                            </div>
                          </div>
                          {!connected && (
                            <div className="connection-note">
                              <Clock size={14} />
                              Reconnecting to live updates. Saved results remain
                              available.
                            </div>
                          )}
                          <div className="timeline">
                            {run.events
                              .filter((e) => !["check"].includes(e.kind))
                              .map((e) => (
                                <TimelineEvent key={e.id} event={e} />
                              ))}
                            {busy(run) && (
                              <div className="timeline-pending">
                                <span className="pulse-dot" />
                                Checking the next piece of evidence…
                              </div>
                            )}
                          </div>
                          {run.error && (
                            <div className="result-card warning">
                              <TriangleAlert size={20} />
                              <div>
                                <h3>Further review is needed</h3>
                                <p>{run.error}</p>
                              </div>
                            </div>
                          )}
                          {run.result.summary && (
                            <div
                              className={
                                "findings " +
                                (run.result.verification?.verified
                                  ? "verified"
                                  : "")
                              }
                            >
                              <div className="section-kicker">
                                {run.result.verification?.verified ? (
                                  <>
                                    <CheckCheck size={14} /> OUTCOME VERIFIED
                                  </>
                                ) : (
                                  <>INVESTIGATION FINDINGS</>
                                )}
                              </div>
                              <h3>{run.result.summary}</h3>
                              {run.result.facts?.length ? (
                                <ul>
                                  {run.result.facts.map((fact, i) => (
                                    <li key={i}>
                                      <Check size={14} />
                                      {fact}
                                    </li>
                                  ))}
                                </ul>
                              ) : null}
                              {run.result.assumptions?.length ? (
                                <div className="missing-info">
                                  <strong>Not yet established</strong>
                                  {run.result.assumptions.map((item, i) => (
                                    <p key={i}>{item}</p>
                                  ))}
                                </div>
                              ) : null}
                              {run.result.missing_information?.length ? (
                                <div className="missing-info">
                                  <strong>Still needed</strong>
                                  {run.result.missing_information.map(
                                    (m, i) => (
                                      <p key={i}>{m}</p>
                                    ),
                                  )}
                                </div>
                              ) : null}
                              {sources.length > 0 && (
                                <div className="inline-sources">
                                  {sources.map((s) => (
                                    <button
                                      key={s.id}
                                      onClick={() => void openSource(s)}
                                    >
                                      <BookOpen size={12} />
                                      {s.title}
                                      <span>v{s.version}</span>
                                      <ArrowUpRight size={12} />
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                          {activeAction && (
                            <div
                              className={"action-card " + activeAction.status}
                            >
                              <div className="action-top">
                                <span className="action-symbol">
                                  <Zap size={20} />
                                </span>
                                <div>
                                  <div className="section-kicker">
                                    {activeAction.status === "pending"
                                      ? "YOUR DECISION"
                                      : "REPAIR RECORD"}
                                  </div>
                                  <h3>
                                    {activeAction.kind ===
                                    "reprocess_billing_event"
                                      ? "Reprocess the billing event"
                                      : "Retry the failed delivery"}
                                  </h3>
                                </div>
                                <span className="action-state">
                                  {activeAction.status === "pending" ? (
                                    <>
                                      <Clock size={12} />
                                      Approval needed
                                    </>
                                  ) : (
                                    label(activeAction.status)
                                  )}
                                </span>
                              </div>
                              <p>{activeAction.payload.expected_effect}</p>
                              <div className="action-object">
                                <span>Exact event</span>
                                <code>{activeAction.target_id}</code>
                                <span>State version</span>
                                <code>
                                  {activeAction.payload.expected_version}
                                </code>
                              </div>
                              {activeAction.status === "pending" &&
                                run.status === "waiting_for_approval" && (
                                  <>
                                    <div className="action-safety">
                                      <ShieldCheck size={14} />
                                      Permissions and current state are checked
                                      again before execution.
                                    </div>
                                    {session?.role === "operator" ? (
                                      <div className="action-buttons">
                                        <button
                                          className="approve-button"
                                          disabled={pending}
                                          onClick={() =>
                                            void decision(
                                              activeAction,
                                              "approve",
                                            )
                                          }
                                        >
                                          {pending ? (
                                            <LoaderCircle
                                              size={15}
                                              className="spin"
                                            />
                                          ) : (
                                            <Check size={16} />
                                          )}
                                          Approve & execute
                                        </button>
                                        <button
                                          className="reject-button"
                                          disabled={pending}
                                          onClick={() =>
                                            void decision(
                                              activeAction,
                                              "reject",
                                            )
                                          }
                                        >
                                          Decline
                                        </button>
                                      </div>
                                    ) : (
                                      <div className="analyst-notice">
                                        <LockKeyhole size={15} />
                                        You can investigate. An operator must
                                        approve this repair.
                                      </div>
                                    )}
                                  </>
                                )}
                              <details className="proposal-digest">
                                <summary>
                                  Proposal integrity <ChevronDown size={12} />
                                </summary>
                                <code>{activeAction.digest}</code>
                              </details>
                            </div>
                          )}
                          {run.result.reply !== undefined && !busy(run) && (
                            <div className="reply-card">
                              <div className="reply-heading">
                                <h3>
                                  <MessageSquare size={17} />
                                  Customer reply
                                </h3>
                                <span>Draft · not sent</span>
                              </div>
                              <textarea
                                aria-label="Customer reply draft"
                                value={draft}
                                onChange={(e) => {
                                  setDraft(e.target.value);
                                  draftDirty.current = true;
                                  setSaved(false);
                                }}
                              />
                              <div className="reply-footer">
                                <span>
                                  <LockKeyhole size={12} />
                                  You review. You send.
                                </span>
                                <button
                                  className="text-button"
                                  onClick={() => {
                                    void navigator.clipboard
                                      .writeText(draft)
                                      .then(() => {
                                        setCopied(true);
                                        setTimeout(
                                          () => setCopied(false),
                                          2000,
                                        );
                                      });
                                  }}
                                >
                                  {copied ? (
                                    <Check size={13} />
                                  ) : (
                                    <Copy size={13} />
                                  )}{" "}
                                  {copied ? "Copied" : "Copy"}
                                </button>
                                <button
                                  className="outline-button"
                                  onClick={() => void save()}
                                >
                                  {saved ? <Check size={13} /> : null}
                                  {saved ? "Saved" : "Save draft"}
                                </button>
                              </div>
                            </div>
                          )}
                          {[
                            "completed",
                            "needs_human",
                            "failed",
                            "cancelled",
                          ].includes(run.status) && (
                            <button
                              className="text-button rerun"
                              onClick={() => void start()}
                              disabled={pending}
                            >
                              <ArrowRight size={14} />
                              Run another investigation
                            </button>
                          )}
                        </>
                      )}
                    </>
                  )}
                </div>
                <div className="case-foot">
                  <ShieldCheck size={13} />
                  <span>Evidence first. Human-approved actions.</span>
                  <span className="case-foot-status">
                    <span />
                    {connected ? "Workspace connected" : "Reconnecting"}
                  </span>
                </div>
              </>
            )}
          </section>
          <aside className="context-panel">
            <div className="context-heading">
              <h2>Account context</h2>
              <ArrowDownLeft size={17} />
            </div>
            {detail ? (
              <>
                <div className="company-mark">
                  {detail.account.company
                    .split(" ")
                    .map((w) => w[0])
                    .join("")
                    .slice(0, 2)}
                </div>
                <h3 className="company-name">{detail.account.company}</h3>
                <p className="company-sub">{t?.customer}'s workspace</p>
                <dl className="context-facts">
                  <div>
                    <dt>Current plan</dt>
                    <dd
                      className={
                        "plan-pill " +
                        (detail.account.plan === "Pro" ? "pro" : "")
                      }
                    >
                      {detail.account.plan}
                    </dd>
                  </div>
                  <div>
                    <dt>Product version</dt>
                    <dd>{detail.account.product_version}</dd>
                  </div>
                  <div>
                    <dt>Payment</dt>
                    <dd>
                      <span
                        className={
                          "small-dot " + detail.account.billing.payment_status
                        }
                      />
                      {detail.account.billing.payment_status}
                    </dd>
                  </div>
                  <div>
                    <dt>Integration</dt>
                    <dd>
                      <span className="small-dot succeeded" />
                      {detail.account.delivery.integration_status}
                    </dd>
                  </div>
                  <div>
                    <dt>Account ID</dt>
                    <dd className="mono">{short(detail.account.id)}…</dd>
                  </div>
                </dl>
                <div className="context-divider" />
                <div className="section-kicker">WORKING BOUNDARIES</div>
                <div className="boundary">
                  <ShieldCheck size={17} />
                  <div>
                    <strong>Approval before action</strong>
                    <p>
                      Every repair is scoped to one event and checked before it
                      runs.
                    </p>
                  </div>
                </div>
                <div className="boundary">
                  <Layers size={17} />
                  <div>
                    <strong>Real calls. Test data.</strong>
                    <p>
                      This SaaS laboratory stores real state using synthetic
                      accounts.
                    </p>
                  </div>
                </div>
                <div className="context-note">
                  <span className="context-note-icon">↗</span>
                  <p>
                    A repair is complete only when a fresh check confirms it.
                  </p>
                </div>
                <button
                  className="context-trace"
                  onClick={() => setTab("details")}
                >
                  <FileText size={15} />
                  <span>Inspect execution record</span>
                  <ArrowUpRight size={15} />
                </button>
              </>
            ) : (
              <div className="skeleton-block" />
            )}
            <div className="context-footer">
              BUILT FOR THE PEOPLE
              <br />
              BEHIND THE HELP DESK.
            </div>
          </aside>
        </main>
        <footer className="workspace-footer">
          <span>
            S(AI)pport <span> / </span> A little more certainty.
          </span>
          <span>
            Isolated data <i /> Explicit approvals <i /> Verified outcomes
          </span>
        </footer>
      </div>
      {(modal || source) && (
        <div
          className="modal-backdrop"
          onClick={() => {
            setModal(null);
            setSource(null);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-label={
              source
                ? "Documentation source"
                : modal === "settings"
                  ? "Workspace settings"
                  : modal === "activity"
                    ? "Workspace activity"
                    : "Demo guide"
            }
            className="modal"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close icon-button"
              aria-label="Close dialog"
              onClick={() => {
                setModal(null);
                setSource(null);
              }}
            >
              <X size={20} />
            </button>
            {source ? (
              <>
                <div className="section-kicker">VERSIONED SOURCE</div>
                <h2>{source.title}</h2>
                <div className="source-meta">
                  Version {source.version} · Product {source.product_version} ·{" "}
                  {source.source_key}
                </div>
                <p className="source-body">{source.body}</p>
                <div className="hint mono">{source.id}</div>
              </>
            ) : modal === "settings" ? (
              <>
                <div className="section-kicker">WORKSPACE SETTINGS</div>
                <h2>Choose how to investigate.</h2>
                <p className="muted">
                  The provider is recorded on each run. Changing it affects new
                  investigations.
                </p>
                <label className="setting-label">
                  Investigation provider
                  <select
                    aria-label="Investigation provider"
                    value={provider}
                    onChange={(e) =>
                      setProvider(e.target.value as typeof provider)
                    }
                  >
                    <option value="deterministic">
                      Offline · deterministic tool driver
                    </option>
                    <option
                      value="openrouter"
                      disabled={!session?.live_available}
                    >
                      Live · OpenRouter free model
                      {!session?.live_available ? " (key required)" : ""}
                    </option>
                  </select>
                </label>
                <p className="hint">
                  Offline mode exercises the real APIs and workflow with a
                  deterministic driver. Live mode asks a free model to choose
                  and call tools. Neither mode can approve its own repair.
                </p>
                <div className="setting-section">
                  <h3>Try a different role</h3>
                  <p className="muted">
                    Create a fresh, isolated workspace. Your current workspace
                    remains stored until expiry.
                  </p>
                  <div className="role-buttons">
                    <button
                      className="outline-button"
                      disabled={loading}
                      onClick={() => void bootstrap("operator")}
                    >
                      <ShieldCheck size={15} />
                      New operator workspace
                    </button>
                    <button
                      className="outline-button"
                      disabled={loading}
                      onClick={() => void bootstrap("analyst")}
                    >
                      <Search size={15} />
                      New analyst workspace
                    </button>
                  </div>
                </div>
                <button
                  className="primary-button"
                  onClick={() => setModal(null)}
                >
                  Done
                  <Check size={15} />
                </button>
              </>
            ) : modal === "activity" ? (
              <>
                <div className="section-kicker">OBSERVABLE OPERATIONS</div>
                <h2>Workspace activity</h2>
                {metrics ? (
                  <>
                    <div className="metric-grid">
                      {(
                        (metrics.runs || []) as {
                          status: string;
                          count: number;
                        }[]
                      ).map((r) => (
                        <div key={r.status}>
                          <strong>{r.count}</strong>
                          <span>{label(r.status)}</span>
                        </div>
                      ))}
                    </div>
                    <pre className="usage-summary">
                      {JSON.stringify(metrics.usage, null, 2)}
                    </pre>
                    <div className="audit-list">
                      {(
                        (metrics.audit || []) as {
                          verb: string;
                          object_id: string;
                          created_at: string;
                        }[]
                      ).map((a, i) => (
                        <div key={i}>
                          <Check size={14} />
                          <span>{a.verb}</span>
                          <code>{short(a.object_id)}</code>
                          <time>
                            {new Date(a.created_at).toLocaleTimeString()}
                          </time>
                        </div>
                      ))}
                    </div>
                    {!(metrics.audit as unknown[])?.length && (
                      <p className="muted">
                        Start an investigation to see decisions and execution
                        records here.
                      </p>
                    )}
                  </>
                ) : (
                  <LoaderCircle className="spin" />
                )}
              </>
            ) : (
              <>
                <div className="section-kicker">A FIVE-MINUTE WALKTHROUGH</div>
                <h2>From incident to certainty.</h2>
                <p className="muted">
                  Every account here is synthetic. The tools, approvals, stored
                  state, and verification are real.
                </p>
                <ol className="guide-steps">
                  <li>
                    <span>01</span>
                    <div>
                      <strong>Investigate a ticket</strong>
                      <p>
                        Start with “Paid for Pro, still on Free.” Inspect the
                        API facts and the applicable procedure.
                      </p>
                    </div>
                  </li>
                  <li>
                    <span>02</span>
                    <div>
                      <strong>Review the exact repair</strong>
                      <p>
                        Check the event, expected effect, and version. Approve
                        it as an operator, or decline.
                      </p>
                    </div>
                  </li>
                  <li>
                    <span>03</span>
                    <div>
                      <strong>Check what changed</strong>
                      <p>
                        The worker runs the approved operation and reads the
                        account again. Then review the customer reply.
                      </p>
                    </div>
                  </li>
                </ol>
                <p className="hint">
                  Also try the failed integration and product setup questions.
                  Switch to an analyst workspace to check approval restrictions.
                  Live model access depends on the configured OpenRouter key and
                  free-provider availability.
                </p>
                <button
                  className="primary-button"
                  onClick={() => setModal(null)}
                >
                  Open the workspace
                  <ArrowRight size={16} />
                </button>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function TimelineEvent({ event: e }: { event: RunEvent }) {
  const isError = e.kind === "tool_error" || e.kind === "verification_failed";
  const title = e.data.tool ? steps[e.data.tool] || e.title : e.title;
  const result = e.data.result;
  let subtitle = "";
  if (result) {
    if (result.plan) subtitle = "Account plan: " + String(result.plan);
    if (result.documents)
      subtitle =
        result.documents.length +
        " applicable source" +
        (result.documents.length === 1 ? "" : "s");
    if (result.document)
      subtitle = result.document.title + " · v" + result.document.version;
    if (result.error) subtitle = result.error;
  }
  return (
    <details className={"timeline-event " + (isError ? "has-error" : "")}>
      <summary>
        <span className="event-icon">
          {isError ? (
            <TriangleAlert size={13} />
          ) : e.kind === "transport" ? (
            <Unplug size={13} />
          ) : e.kind === "approval" ? (
            <ShieldCheck size={13} />
          ) : e.kind === "execution" ? (
            <Zap size={13} />
          ) : (
            <Check size={13} />
          )}
        </span>
        <div>
          <strong>{title}</strong>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <time>
          {new Date(e.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </time>
        <ChevronRight size={13} className="event-chevron" />
      </summary>
      <pre>{JSON.stringify(e.data, null, 2)}</pre>
    </details>
  );
}
