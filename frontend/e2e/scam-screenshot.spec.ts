import { expect, test } from "@playwright/test";

import { signedInWorker } from "./support/emulators";
import { type MockApi, mockApi } from "./support/mockApi";

// The screenshot path (NF-SA-020): choose or photograph a picture of a chat instead of pasting
// it. The picture goes to the same analyze route as a form; the backend reads it and drops it.

// A 1x1 PNG: what matters here is the type and the form, not the picture.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==",
  "base64"
);

let api: MockApi;

test.beforeEach(async ({ page }) => {
  api = await mockApi(page);
  await signedInWorker(page);
  await page.goto("/scam-check");
  await page.getByRole("button", { name: "Screenshot" }).click();
});

test("a screenshot is sent as a form to the analyze route and the verdict is shown", async ({
  page,
}) => {
  await page.getByLabel("Choose a screenshot").setInputFiles({
    name: "chat.png",
    mimeType: "image/png",
    buffer: PNG,
  });
  await expect(page.getByText("chat.png")).toBeVisible();
  await page.getByRole("button", { name: "Check this message" }).click();

  await expect(page.getByRole("heading", { name: "This looks like a scam" })).toBeVisible();
  const [sent] = api.to("POST", /\/scam\/analyze$/);
  expect(sent.contentType).toContain("multipart/form-data");
  expect(sent.raw).toContain('name="image"; filename="chat.png"');
  expect(sent.raw).toContain('name="language"');
  expect(sent.raw).toContain("SG-IN");
});

test("the camera button takes a picture that goes the same way", async ({ page }) => {
  await page.locator('input[capture="environment"]').setInputFiles({
    name: "photo.png",
    mimeType: "image/png",
    buffer: PNG,
  });

  await expect(page.getByText("photo.png")).toBeVisible();
  await page.getByRole("button", { name: "Check this message" }).click();
  await expect(page.getByRole("heading", { name: "This looks like a scam" })).toBeVisible();
  expect(api.to("POST", /\/scam\/analyze$/)[0].contentType).toContain("multipart/form-data");
});

test("a picture with no readable message gets a clear notice and can be replaced", async ({
  page,
}) => {
  api.answerAnalyzeWith("scam/analyze-error-image-unreadable.json");
  await page.getByLabel("Choose a screenshot").setInputFiles({
    name: "blank.png",
    mimeType: "image/png",
    buffer: PNG,
  });
  await page.getByRole("button", { name: "Check this message" }).click();

  await expect(page.getByRole("alert")).toContainText("could not read any message");
  await expect(page.getByText("blank.png")).toBeVisible();
  await page.getByRole("button", { name: "Remove screenshot" }).click();
  await expect(page.getByText("Choose a screenshot", { exact: true })).toBeVisible();
});

test("a file that is not an image is refused before it is sent", async ({ page }) => {
  await page.getByLabel("Choose a screenshot").setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not a picture"),
  });

  await expect(page.getByRole("alert")).toContainText("JPEG, PNG or WebP");
  expect(api.to("POST", /\/scam\/analyze$/)).toHaveLength(0);
});
