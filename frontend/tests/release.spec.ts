import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Start investigation", exact: true }),
  ).toBeVisible();
});

test("unsaved reply survives switching tickets and reloading", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve & execute", exact: true })
    .click();
  await expect(
    page.getByText("OUTCOME VERIFIED", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Customer reply draft" })
    .fill("A locally preserved reply awaiting review.");
  await page
    .getByRole("button")
    .filter({ hasText: "Webhook deliveries have stopped" })
    .click();
  await page
    .getByRole("button")
    .filter({ hasText: "Paid for Pro, still on Free" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toHaveValue("A locally preserved reply awaiting review.");
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toHaveValue("A locally preserved reply awaiting review.");
});

test("decline shows final review state and keeps access unchanged", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await page.getByRole("button", { name: "Decline", exact: true }).click();
  await expect(page.locator(".run-heading strong")).toHaveText("Needs review");
  await expect(page.locator(".findings")).toContainText("declined");
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toHaveValue(/escalated/);
  await expect(page.locator(".plan-pill")).toHaveText("Free");
});

test("dialog traps focus, closes with Escape, and restores focus", async ({
  page,
}) => {
  const settings = page.getByRole("button", {
    name: "Workspace settings",
    exact: true,
  });
  await settings.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  for (let i = 0; i < 9; i++) {
    await page.keyboard.press("Tab");
    expect(
      await dialog.evaluate((el) => el.contains(document.activeElement)),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(settings).toBeFocused();
});

test("session outage has a recovery control without creating extra workspaces", async ({
  page,
}) => {
  let sessions = 0;
  await page.route("**/api/session", (route) =>
    route.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } }),
  );
  await page.route("**/api/demo/session", (route) => {
    sessions++;
    return route.continue();
  });
  await page.reload();
  await expect(page.getByRole("alert")).toHaveText("Temporarily unavailable");
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeVisible();
  expect(sessions).toBe(0);
  await page.unroute("**/api/session");
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(
    page.getByRole("button", { name: "Start investigation", exact: true }),
  ).toBeVisible();
});

test("tablet and mobile expose account context without horizontal overflow", async ({
  page,
}) => {
  for (const width of [1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page
      .getByRole("button", { name: "Account details", exact: true })
      .click();
    await expect(
      page.getByRole("complementary", { name: "Account context" }),
    ).toBeVisible();
    await expect(page.locator(".plan-pill")).toHaveText("Free");
    await page.getByRole("button", { name: "Close account details" }).click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});

test("workspace, approval and settings meet automated WCAG A/AA checks", async ({
  page,
}) => {
  const check = async () => {
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      result.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
    ).toEqual([]);
  };
  await check();
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve & execute", exact: true }),
  ).toBeVisible();
  await check();
  await page
    .getByRole("button", { name: "Workspace settings", exact: true })
    .click();
  await check();
});

test("unavailable live access explains the deployment restriction", async ({
  page,
}) => {
  await page.route("**/api/session", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        live_available: false,
        live_unavailable_reason:
          "Provider access is unavailable from this deployment network.",
      },
    });
  });
  await page.reload();
  await page
    .getByRole("button", { name: "Workspace settings", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Provider access is unavailable from this deployment network.",
  );
  const provider = page.getByLabel("Investigation provider", { exact: true });
  await provider.press("ArrowDown");
  await provider.press("Enter");
  await expect(provider).toHaveValue("deterministic");
});
