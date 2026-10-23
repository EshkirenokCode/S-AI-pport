# Public demo release

Requested scope: audit the application, fix confirmed defects, replace the visual design, refresh the repository presentation, and deploy an isolated HTTPS demo.

## Sequence

1. Audit the API, worker, tools, storage, browser state, tests, and deployment boundary. Run the existing checks as a baseline.
2. Repair lifecycle races, stale status, draft persistence, public-demo resource limits, and accessibility/recovery issues. Add regression coverage for demonstrated defects.
3. Replace the marketing-heavy shell with a compact support workspace. Rework navigation, inbox, evidence, proposal, context, dialogs, responsive states, and typography together.
4. Exercise the three workflows and negative paths in automated tests and the browser. Refresh screenshots, architecture/operations notes, and README.
5. Push user-authored release commits, verify CI, and deploy an isolated stack under saipport.gulevskii.dev. Verify HTTPS, session isolation, execution, quotas, restart behavior, and existing sites.

## Audit findings to address

- A terminal worker result did not synchronize the ticket status except after a repair.
- Rejecting a proposal left the pre-approval reply and disposition in place.
- Cancelling an already finished run still wrote a cancellation event/audit entry.
- Draft saves were accepted while a worker could overwrite the result, and the UI could acknowledge a save for a different selected ticket.
- MCP delegation was run-bound but did not bind the current worker lease.
- Successful repair assumptions were still shown as present-tense unverified claims.
- Initial session errors left the loading screen without a recovery control; session expiry was not distinguished from network failures.
- Browser state updates and actions could race ticket changes; modal focus/keyboard behavior needed improvement.
- Public session provisioning needed a global cap and expired synthetic workspaces needed bounded retention.
- The application was dominated by a large decorative introduction, with critical proposals buried after the event log; context disappeared at tablet/mobile sizes.

## Design direction

References reviewed: Norrly's Linear/Intercom entries, DevDojo Inspiration, UI Discovery, and the public Linear/Plain product pages. These are visual references, not implementation instructions or copied assets. The product uses its own identity and composition: an ink navigation column, neutral work surfaces, one blue action color, compact ticket rows, and explicit amber approval/green verified states. Keep practical information ahead of decoration. Use locally bundled typefaces and no external font requests.

## Deployment constraints

The existing server hosts other projects. Add a separate Compose project and private database/laboratory; add only a dedicated proxy host. Do not restart or reconfigure unrelated applications. Store runtime secrets outside Git. The public environment remains a synthetic demonstration with explicit offline/live labels, free-only model selection, quotas, and no real payments.
