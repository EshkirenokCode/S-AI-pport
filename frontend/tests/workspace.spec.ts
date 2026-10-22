import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Start investigation", exact: true }),
  ).toBeVisible();
});

test("billing: inspect, approve, verify, and edit the reply", async ({
  page,
}) => {
  await mkdir("../docs/media", { recursive: true });
  await page.screenshot({ path: "../docs/media/workspace.png" });
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve & execute", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".plan-pill")).toHaveText("Free");
  await page
    .getByRole("button", { name: "Recover a paid subscription v2.1" })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Reprocessing never charges the card",
  );
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.locator(".action-card").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "../docs/media/approval.png" });
  await page
    .getByRole("button", { name: "Approve & execute", exact: true })
    .click();
  await expect(
    page.getByText("OUTCOME VERIFIED", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".plan-pill")).toHaveText("Pro");
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toContainText("No additional charge");
  await page
    .getByRole("textbox", { name: "Customer reply draft" })
    .fill("Your access is restored. I verified the Pro entitlement.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Saved", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toHaveValue("Your access is restored. I verified the Pro entitlement.");
  await page.locator(".findings").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "../docs/media/repair-verified.png" });
});

test("integration: a real retry is acknowledged", async ({ page }) => {
  await page
    .getByRole("button")
    .filter({ hasText: "Webhook deliveries have stopped" })
    .click();
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve & execute", exact: true })
    .click();
  await expect(
    page.getByText("OUTCOME VERIFIED", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".findings h3")).toContainText(
    "destination acknowledgement",
  );
});

test("configuration: use the applicable versioned source", async ({ page }) => {
  await page
    .getByRole("button")
    .filter({ hasText: "How do I configure webhook retries?" })
    .click();
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toHaveValue(/Retry attempts from 0 to 3/);
  await expect(
    page.getByRole("button", { name: "Approve & execute" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Configure webhook retries v2.4" })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "These instructions apply only to 2.4",
  );
});

test("analyst: evidence is available, approval is restricted", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Workspace settings", exact: true })
    .click();
  await page
    .getByRole("button", { name: "New analyst workspace", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await expect(
    page.getByText(
      "You can investigate. An operator must approve this repair.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve & execute" }),
  ).toHaveCount(0);
});

test("permanent integration error is escalated without a repair", async ({
  page,
}) => {
  await page
    .getByRole("button")
    .filter({ hasText: "Integration returns unauthorized" })
    .click();
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await expect(page.locator(".run-heading strong")).toHaveText("Needs review");
  await expect(
    page.getByRole("button", { name: "Approve & execute" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toBeVisible();
});

test("mobile: queue and primary actions remain accessible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", {
      name: "Paid for Pro, still on Free",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Back to inbox", exact: true })
    .click();
  await page
    .getByRole("button")
    .filter({ hasText: "How do I configure webhook retries?" })
    .click();
  await page
    .getByRole("button", { name: "Start investigation", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Customer reply draft" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "../docs/media/mobile.png", fullPage: true });
});
