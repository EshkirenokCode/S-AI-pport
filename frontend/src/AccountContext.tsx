import { X } from "lucide-react";
import type { Account } from "./types";
export function AccountContext({
  account,
  customer,
  open,
  onClose,
  onInspect,
}: {
  account?: Account;
  customer?: string;
  open: boolean;
  onClose: () => void;
  onInspect: () => void;
}) {
  return (
    <aside
      id="account-context"
      aria-label="Account context"
      className={"context-panel " + (open ? "context-open" : "")}
    >
      <div className="context-heading">
        <h2>Account context</h2>
        <button
          className="icon-button close-context"
          aria-label="Close account details"
          onClick={onClose}
        >
          <X size={17} />
        </button>
      </div>
      {account ? (
        <>
          <h3 className="company-name">{account.company}</h3>
          <p className="company-sub">{customer}'s workspace</p>
          <dl className="context-facts">
            <div>
              <dt>Current plan</dt>
              <dd
                className={"plan-pill " + (account.plan === "Pro" ? "pro" : "")}
              >
                {account.plan}
              </dd>
            </div>
            <div>
              <dt>Product version</dt>
              <dd>{account.product_version}</dd>
            </div>
            <div>
              <dt>Payment</dt>
              <dd>
                <span
                  className={"small-dot " + account.billing.payment_status}
                />
                {account.billing.payment_status}
              </dd>
            </div>
            <div>
              <dt>Integration</dt>
              <dd>
                <span
                  className={
                    "small-dot " +
                    (account.delivery.integration_status === "active"
                      ? "succeeded"
                      : "failed")
                  }
                />
                {account.delivery.integration_status}
              </dd>
            </div>
            <div>
              <dt>Account ID</dt>
              <dd className="mono">{account.id.slice(0, 8)}…</dd>
            </div>
          </dl>
          <button className="context-trace" onClick={onInspect}>
            View run details
          </button>
        </>
      ) : (
        <div className="skeleton-block" />
      )}
    </aside>
  );
}
