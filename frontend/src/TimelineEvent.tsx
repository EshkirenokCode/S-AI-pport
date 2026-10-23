import {
  Check,
  TriangleAlert,
  Unplug,
  ShieldCheck,
  Zap,
  ChevronRight,
} from "lucide-react";
import type { RunEvent } from "./types";
const steps: Record<string, string> = {
  get_account_context: "Account identified",
  get_billing_state: "Payment and access checked",
  get_delivery_state: "Delivery attempts inspected",
  search_documentation: "Relevant procedures found",
  read_document: "Procedure and version checked",
  propose_action: "A precise repair proposed",
  finish_investigation: "Findings prepared",
};

export function TimelineEvent({ event: e }: { event: RunEvent }) {
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
