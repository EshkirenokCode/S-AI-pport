import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
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
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  TriangleAlert,
  Unplug,
  X,
  Zap,
} from "lucide-react";
import { Dialog } from "./Dialog";
import { TimelineEvent } from "./TimelineEvent";
import { AccountContext } from "./AccountContext";
import type {
  Account,
  Action,
  Run,
  Session,
  Source,
  Metrics,
  Ticket,
} from "./types";

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
function localDraft(run: Run) {
  try {
    return (
      sessionStorage.getItem("saipport:draft:" + run.id) ??
      run.result.reply ??
      ""
    );
  } catch {
    return run.result.reply ?? "";
  }
}
async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const r = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({
      detail:
        r.status === 429
          ? "Demo request limit reached. Wait a moment and try again."
          : "The service could not be reached.",
    }));
    throw new ApiError(
      typeof d.detail === "string"
        ? d.detail
        : "The request could not be completed.",
      r.status,
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
    succeeded: "Executed",
    rejected: "Declined",
    stale: "Account changed",
    unknown: "Outcome uncertain",
    approved: "Approved",
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
    [metrics, setMetrics] = useState<Metrics | null>(null);
  const [draft, setDraft] = useState(""),
    [saved, setSaved] = useState(false),
    [copied, setCopied] = useState(false),
    [mobileQueue, setMobileQueue] = useState(false),
    [connected, setConnected] = useState(true),
    [contextOpen, setContextOpen] = useState(false);
  const booted = useRef(false),
    draftDirty = useRef(false),
    draftRevision = useRef(0),
    selectedRef = useRef(selected),
    draftRef = useRef(draft),
    casePanel = useRef<HTMLElement>(null);
  draftRef.current = draft;
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
      setSelected("");
      selectedRef.current = "";
      setRun(null);
      setDetail(null);
      try {
        if (role)
          await api("/demo/session", {
            method: "POST",
            body: JSON.stringify({ role }),
          });
        let s: Session;
        try {
          s = await api<Session>("/session");
        } catch (e) {
          if (!(e instanceof ApiError) || e.status !== 401) throw e;
          await api("/demo/session", { method: "POST", body: "{}" });
          s = await api<Session>("/session");
        }
        setSession(s);
        let choice: Session["provider"] = s.live_available
          ? s.provider
          : "deterministic";
        try {
          const stored = sessionStorage.getItem("saipport:provider");
          if (
            stored === "deterministic" ||
            (stored === "openrouter" && s.live_available)
          )
            choice = stored;
        } catch {
          /* Storage is optional. */
        }
        setProvider(choice);
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
    casePanel.current?.scrollTo(0, 0);
    setDetail(null);
    setRun(null);
    setTab("investigation");
    setSaved(false);
    setCopied(false);
    setContextOpen(false);
    setError("");
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
            setDraft(localDraft(r));
            draftDirty.current = localDraft(r) !== (r.result.reply || "");
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
    let refreshing = false;
    const refresh = async () => {
      if (refreshing || !active) return;
      refreshing = true;
      const revision = draftRevision.current;
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
            if (!draftDirty.current && draftRevision.current === revision)
              setDraft(r.result.reply || "");
          }
        }
        if (
          ["completed", "needs_human", "failed", "cancelled"].includes(r.status)
        ) {
          clearInterval(timer);
          es.close();
        }
      } catch (e) {
        if (active) {
          setConnected(false);
          if (e instanceof ApiError && e.status === 401)
            setError(
              "Your demo session expired. Open settings to create a fresh workspace.",
            );
        }
      } finally {
        refreshing = false;
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
    es.onerror = () => {
      if (active) setConnected(false);
    };
    es.onopen = () => setConnected(true);
    return () => {
      active = false;
      clearInterval(timer);
      es.close();
    };
  }, [runId, loadQueue]);
  async function start() {
    if (!detail) return;
    const ticketId = detail.ticket.id;
    setRun(null);
    setPending(true);
    setError("");
    setDraft("");
    draftDirty.current = false;
    try {
      const r = await api<{ id: string }>("/tickets/" + ticketId + "/runs", {
        method: "POST",
        body: JSON.stringify({ provider }),
      });
      const fresh = await api<Run>("/runs/" + r.id);
      if (selectedRef.current === ticketId) {
        setRun(fresh);
        setSaved(false);
      }
      await loadQueue();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function decision(action: Action, value: "approve" | "reject") {
    if (!run) return;
    const runId = run.id,
      ticketId = selected;
    setPending(true);
    setError("");
    try {
      await api("/actions/" + action.id + "/decision", {
        method: "POST",
        body: JSON.stringify({ decision: value, digest: action.digest }),
      });
      const fresh = await api<Run>("/runs/" + runId);
      if (selectedRef.current === ticketId) {
        setRun(fresh);
        setDraft(fresh.result.reply || "");
        draftDirty.current = false;
        try {
          sessionStorage.removeItem("saipport:draft:" + runId);
        } catch {
          /* Optional storage. */
        }
      }
      await loadQueue();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function cancel() {
    if (!run) return;
    const ticketId = selected,
      runId = run.id;
    try {
      await api("/runs/" + runId + "/cancel", { method: "POST" });
      const fresh = await api<Run>("/runs/" + runId);
      if (selectedRef.current === ticketId) setRun(fresh);
      await loadQueue();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function save() {
    if (!run) return;
    const ticketId = selected,
      runId = run.id,
      text = draft;
    try {
      await api("/runs/" + run.id + "/draft", {
        method: "PATCH",
        body: JSON.stringify({ reply: draft }),
      });
      if (selectedRef.current === ticketId && draftRef.current === text) {
        setSaved(true);
        draftRevision.current++;
        draftDirty.current = false;
        try {
          sessionStorage.removeItem("saipport:draft:" + runId);
        } catch {
          /* Optional storage. */
        }
      }
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
    setMetrics(null);
    setError("");
    setModal("activity");
    try {
      setMetrics(await api<Metrics>("/metrics"));
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
        (filter === "resolved" && t.status === "resolved") ||
        (filter === "approval" && t.run_status === "waiting_for_approval") ||
        (filter === "open" && t.status !== "resolved")),
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
  if (!session)
    return (
      <div className="boot">
        <span className="brand-mark" aria-hidden="true">
          <Inbox size={18} />
        </span>
        <h1>Opening your workspace</h1>
        <p>Loading the sample tickets.</p>
        {error ? (
          <>
            <p role="alert" className="boot-error">
              {error}
            </p>
            <button className="primary-button" onClick={() => void bootstrap()}>
              Retry connection
            </button>
          </>
        ) : (
          <LoaderCircle className="spin" />
        )}
      </div>
    );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#ticket-workspace">
        Skip to ticket
      </a>
      <header className="masthead">
        <a className="brand" href="/" aria-label="sAIpport home">
          <span className="brand-mark" aria-hidden="true">
            <Inbox size={17} />
          </span>
          <span>sAIpport</span>
        </a>
        <nav className="desk-nav" aria-label="Ticket views">
          {[
            ["all", "Inbox", "Ticket queue"],
            ["approval", "Approvals", "Approvals"],
            ["resolved", "Resolved", "Resolved tickets"],
          ].map(([value, name, ariaLabel]) => {
            const active =
              value === "all"
                ? ["all", "open"].includes(filter)
                : filter === value;
            return (
              <button
                key={value}
                className={active ? "active" : ""}
                aria-label={ariaLabel}
                aria-pressed={active}
                onClick={() => {
                  setFilter(value);
                  setContextOpen(false);
                  setMobileQueue(true);
                }}
              >
                {name}
                {value === "approval" && waiting > 0 && <span>{waiting}</span>}
              </button>
            );
          })}
        </nav>
        <div className="desk-tools">
          <span className="demo-badge">Sample data</span>
          <button
            className="icon-button"
            aria-label="Workspace activity"
            title="Workspace activity"
            onClick={() => void activity()}
          >
            <Activity size={17} />
          </button>
          <button
            className="icon-button"
            aria-label="Demo guide"
            title="Demo guide"
            onClick={() => setModal("help")}
          >
            <CircleHelp size={17} />
          </button>
          <button
            className="operator-switch"
            aria-label="Workspace settings"
            title="Workspace settings"
            onClick={() => setModal("settings")}
          >
            <Settings2 size={16} />
            <span>{session.role === "analyst" ? "Analyst" : "Operator"}</span>
          </button>
        </div>
      </header>
      <main className={mobileQueue ? "desk queue-open" : "desk"}>
        <aside
          aria-label="Ticket inbox"
          className={"queue " + (mobileQueue ? "mobile-open" : "")}
        >
          <div className="queue-heading">
            <h2>
              {filter === "resolved"
                ? "Resolved"
                : filter === "approval"
                  ? "Approvals"
                  : "Tickets"}
            </h2>
            <span className="mono">{visible.length} tickets</span>
          </div>
          <label className="search">
            <Search size={16} />
            <input
              placeholder="Search by name or ticket"
              aria-label="Search tickets"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {["all", "open"].includes(filter) && (
            <div className="queue-filters">
              {[
                ["all", "All"],
                ["open", "Open"],
              ].map(([value, name]) => (
                <button
                  key={value}
                  className={filter === value ? "active" : ""}
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
          <div className="ticket-list">
            {visible.map((ticket) => (
              <button
                key={ticket.id}
                aria-current={selected === ticket.id ? "true" : undefined}
                className={
                  "ticket-row " + (selected === ticket.id ? "active" : "")
                }
                onClick={() => {
                  setSelected(ticket.id);
                  setMobileQueue(false);
                }}
              >
                <div className="ticket-row-top">
                  <span className="ticket-number">#{ticket.number}</span>
                  <span className="customer-name">{ticket.customer}</span>
                </div>
                <h3>{ticket.subject}</h3>
                <div className="ticket-row-bottom">
                  <span className="family-tag">
                    {familyIcon(ticket.family)}
                    {ticket.family}
                  </span>
                  <span
                    className={"ticket-status " + (ticket.run_status || "open")}
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
                <p>No tickets match your filters.</p>
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
            <a
              href="https://gulevskii.dev/#saipport"
              target="_blank"
              rel="noreferrer"
            >
              Project by Ilia Gulevskii <ArrowUpRight size={13} />
            </a>
          </div>
        </aside>
        <section
          ref={casePanel}
          tabIndex={-1}
          id="ticket-workspace"
          aria-label="Selected ticket"
          className="case-panel"
        >
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
                <span className="ticket-number">Ticket #{t!.number}</span>
                <span className={"priority " + t!.priority}>
                  <span />
                  {t!.priority === "high" ? "High priority" : "Normal priority"}
                </span>
              </div>
              <div className="customer-message">
                <div className="ticket-title">
                  <h2>{t!.subject}</h2>
                </div>
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
                <p className="message-bubble">{t!.body}</p>
                <div className="message-tags">
                  <span>
                    {familyIcon(t!.family)}
                    {t!.family}
                  </span>
                  <span>
                    <Layers size={13} /> Product{" "}
                    {detail.account.product_version}
                  </span>
                  <button
                    className="mobile-context-button"
                    onClick={() => setContextOpen((v) => !v)}
                    aria-expanded={contextOpen}
                    aria-controls="account-context"
                  >
                    <CreditCard size={13} /> Account details{" "}
                    <ChevronDown size={13} />
                  </button>
                </div>
              </div>
              <div className="case-tabs">
                <button
                  className={tab === "investigation" ? "active" : ""}
                  onClick={() => setTab("investigation")}
                >
                  <Search size={15} />
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
                    <h3>Documentation sources</h3>
                    <p className="muted">
                      Procedures used in this run. See the activity log for
                      account data.
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
                          Use the run ID to match the tool calls, approval, and
                          repair receipt.
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
                        <h3>No investigation yet</h3>
                        <p>
                          Check the account, recent events, and product
                          documentation. An operator must approve any repair.
                        </p>
                        <button
                          className="primary-button"
                          onClick={() => void start()}
                          disabled={pending}
                        >
                          {pending ? (
                            <LoaderCircle size={16} className="spin" />
                          ) : (
                            <Search size={16} />
                          )}
                          Start investigation
                          <ArrowRight size={16} />
                        </button>
                        <div className="provider-inline">
                          <span>
                            {provider === "deterministic"
                              ? "Offline uses a fixed investigation script."
                              : "An OpenRouter model chooses which tools to call."}
                          </span>
                          {session.live_available && (
                            <button onClick={() => setModal("settings")}>
                              Change mode
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div
                          className="run-heading"
                          role="status"
                          aria-live="polite"
                        >
                          <div>
                            <span className={"state-dot " + run.status} />
                            <strong>
                              {run.status === "running" &&
                              run.phase === "execute"
                                ? "Applying repair"
                                : label(run.status)}
                            </strong>
                            {busy(run) && (
                              <LoaderCircle size={14} className="spin" />
                            )}
                          </div>
                          <div className="run-heading-right">
                            <span className="provider-label">
                              {run.provider === "deterministic"
                                ? "Offline"
                                : "Live"}
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
                                  <CheckCheck size={14} /> Outcome verified
                                </>
                              ) : (
                                <>Findings</>
                              )}
                            </div>
                            <h3>{run.result.summary}</h3>
                            {run.result.facts?.length ? (
                              <ul>
                                {run.result.facts.map((fact, i) => (
                                  <li key={i}>
                                    <Check size={14} />
                                    {fact.replace(
                                      /\s*\(api:[0-9a-f-]+\)/gi,
                                      "",
                                    )}
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                            {run.result.assumptions?.length ? (
                              <div className="missing-info">
                                <strong>
                                  {run.result.verification?.verified
                                    ? "Assumptions recorded before the repair"
                                    : "Not yet established"}
                                </strong>
                                {run.result.assumptions.map((item, i) => (
                                  <p key={i}>{item}</p>
                                ))}
                              </div>
                            ) : null}
                            {run.result.missing_information?.length ? (
                              <div className="missing-info">
                                <strong>
                                  {run.result.verification?.verified
                                    ? "Information requested during investigation"
                                    : "Still needed"}
                                </strong>
                                {run.result.missing_information.map((m, i) => (
                                  <p key={i}>{m}</p>
                                ))}
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
                          <div className={"action-card " + activeAction.status}>
                            <div className="action-top">
                              <span className="action-symbol">
                                <Zap size={20} />
                              </span>
                              <div>
                                <div className="section-kicker">
                                  {activeAction.status === "pending"
                                    ? "Proposed repair"
                                    : "Repair record"}
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
                                    The app checks permissions and account state
                                    again before it runs the repair.
                                  </div>
                                  {session?.role === "operator" ? (
                                    <div className="action-buttons">
                                      <button
                                        className="approve-button"
                                        disabled={pending}
                                        onClick={() =>
                                          void decision(activeAction, "approve")
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
                                          void decision(activeAction, "reject")
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
                                Proposal checksum <ChevronDown size={12} />
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
                              <span>
                                {saved
                                  ? "Saved"
                                  : draftDirty.current
                                    ? "Unsaved changes"
                                    : "Draft"}
                              </span>
                            </div>
                            <textarea
                              aria-label="Customer reply draft"
                              value={draft}
                              onChange={(e) => {
                                setDraft(e.target.value);
                                try {
                                  sessionStorage.setItem(
                                    "saipport:draft:" + run.id,
                                    e.target.value,
                                  );
                                } catch {
                                  /* Optional storage. */
                                }
                                draftRevision.current++;
                                draftDirty.current = true;
                                setSaved(false);
                              }}
                            />
                            <div className="reply-footer">
                              <span>
                                <LockKeyhole size={12} />
                                This app does not send replies.
                              </span>
                              <button
                                className="text-button"
                                onClick={() => {
                                  void navigator.clipboard
                                    .writeText(draft)
                                    .then(() => {
                                      setCopied(true);
                                      setTimeout(() => setCopied(false), 2000);
                                    })
                                    .catch(() =>
                                      setError(
                                        "Clipboard access failed. Select the reply text and copy it manually.",
                                      ),
                                    );
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
                        <details
                          className="activity-timeline"
                          open={!run.result.summary || busy(run)}
                        >
                          <summary>
                            <Activity size={15} />
                            <strong>Investigation activity</strong>
                            <span>{tools.length} tool calls</span>
                            <ChevronDown size={14} />
                          </summary>
                          <div className="timeline">
                            {run.events
                              .filter((e) => !["check"].includes(e.kind))
                              .map((e) => (
                                <TimelineEvent key={e.id} event={e} />
                              ))}
                            {busy(run) && (
                              <div className="timeline-pending">
                                <span className="pulse-dot" />
                                Waiting for the next update…
                              </div>
                            )}
                          </div>
                        </details>
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
            </>
          )}
        </section>
        <AccountContext
          account={detail?.account}
          customer={t?.customer}
          open={contextOpen}
          onClose={() => setContextOpen(false)}
          onInspect={() => {
            setTab("details");
            setContextOpen(false);
          }}
        />
      </main>
      {(modal || source) && (
        <Dialog
          title={
            source
              ? "Documentation source"
              : modal === "settings"
                ? "Workspace settings"
                : modal === "activity"
                  ? "Workspace activity"
                  : "Demo guide"
          }
          onClose={() => {
            setModal(null);
            setSource(null);
          }}
        >
          {error && modal !== "activity" && (
            <p role="alert" className="modal-error">
              {error}
            </p>
          )}
          {source ? (
            <>
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
              <h2>Workspace settings</h2>
              <p className="muted">Changes apply to new investigations.</p>
              <label className="setting-label">
                Investigation provider
                <select
                  aria-label="Investigation provider"
                  value={provider}
                  onChange={(e) => {
                    const choice = e.target.value as typeof provider;
                    setProvider(choice);
                    try {
                      sessionStorage.setItem("saipport:provider", choice);
                    } catch {
                      /* Optional storage. */
                    }
                  }}
                >
                  <option value="deterministic">Offline</option>
                  <option
                    value="openrouter"
                    disabled={!session?.live_available}
                  >
                    Live via OpenRouter
                    {!session?.live_available
                      ? session?.live_unavailable_reason
                        ? " (unavailable)"
                        : " (key required)"
                      : ""}
                  </option>
                </select>
              </label>
              <p className="hint">
                Offline follows a fixed script. In Live mode, a free model
                chooses the tools. Both modes use the same tools and require
                operator approval.
              </p>
              {session?.live_unavailable_reason && !session.live_available && (
                <p className="provider-unavailable" role="status">
                  {session.live_unavailable_reason}
                </p>
              )}
              <div className="setting-section">
                <h3>Try a different role</h3>
                <p className="muted">
                  Start over with fresh sample data and the selected role. Your
                  current workspace expires after 24 hours.
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
              <button className="primary-button" onClick={() => setModal(null)}>
                Done
                <Check size={15} />
              </button>
            </>
          ) : modal === "activity" ? (
            <>
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
                  <dl className="usage-stats">
                    <div>
                      <dt>Model calls</dt>
                      <dd>{metrics.usage.calls}</dd>
                    </div>
                    <div>
                      <dt>Tokens used</dt>
                      <dd>{Number(metrics.usage.tokens).toLocaleString()}</dd>
                    </div>
                    <div>
                      <dt>Reported cost</dt>
                      <dd>
                        {metrics.usage.reported_cost === null
                          ? "—"
                          : "$" +
                            Number(metrics.usage.reported_cost).toFixed(4)}
                      </dd>
                    </div>
                    <div>
                      <dt>Average model latency</dt>
                      <dd>
                        {metrics.usage.average_latency_ms === null
                          ? "—"
                          : Number(
                              metrics.usage.average_latency_ms,
                            ).toLocaleString() + " ms"}
                      </dd>
                    </div>
                  </dl>
                  <h3>Decision history</h3>
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
              ) : error ? (
                <div className="result-card warning">
                  <p>{error}</p>
                  <button
                    className="outline-button"
                    onClick={() => void activity()}
                  >
                    Retry activity
                  </button>
                </div>
              ) : (
                <LoaderCircle className="spin" />
              )}
            </>
          ) : (
            <>
              <h2>Try your first investigation</h2>
              <p className="muted">
                The demo uses fictional accounts. You can approve repairs and
                see the changes on those accounts.
              </p>
              <ol className="guide-steps">
                <li>
                  <span>01</span>
                  <div>
                    <strong>Investigate a ticket</strong>
                    <p>
                      Start with "Paid for Pro, still on Free." Read the account
                      data and the procedure the app found.
                    </p>
                  </div>
                </li>
                <li>
                  <span>02</span>
                  <div>
                    <strong>Review the exact repair</strong>
                    <p>
                      Check the event, expected effect, and version. Approve it
                      as an operator, or decline.
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
                An analyst can investigate but cannot approve a repair. Switch
                roles in Settings to try it.
              </p>
              <button className="primary-button" onClick={() => setModal(null)}>
                Open the workspace
                <ArrowRight size={16} />
              </button>
            </>
          )}
        </Dialog>
      )}
    </div>
  );
}
