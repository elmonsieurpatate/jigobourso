// Une panne d’aperçu reste visible sans boucle réseau ; la reprise explicite recharge les poids.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE);
const BASE = process.env.BASE || "http://127.0.0.1:18089";
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.JIGO_CHROMIUM });
  try {
    const context = await browser.newContext();
    const login = await context.request.post(BASE + "/api.php?r=auth/login", {
      headers: { Origin: BASE },
      data: { username: "review_user", password: "review-local-password" },
    });
    assert.equal(login.status(), 200);
    const page = await context.newPage();
    let failed = true,
      requests = 0;
    await page.route("**/api.php?*", async (route) => {
      if (new URL(route.request().url()).searchParams.get("r") !== "admin/scores/preview") return route.continue();
      requests++;
      if (failed)
        return route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ error: "Panne simulée de l’aperçu" }),
        });
      return route.continue();
    });
    await page.goto(BASE + "/admin.html#scores");
    const retry = page.locator('[data-a="retry-weights"]');
    await retry.waitFor();
    assert.match(await page.locator("#as-err").innerText(), /Panne simulée/);
    const settled = requests;
    await page.waitForTimeout(700);
    assert.equal(requests, settled, "aucune boucle de reprise automatique");
    failed = false;
    await retry.click();
    await retry.waitFor({ state: "detached" });
    assert.ok(requests > settled, "le bouton réessaie réellement");
    await page.locator('[data-a="tab"][data-v="profils"]').click();
    await page.locator("#as-rktable tbody tr").first().waitFor();
    const rows = await page.locator("#as-rktable tbody tr").count();
    assert.ok(rows > 0, "la vue du classement rend les lignes réelles");
    const sort = page.locator('#as-rktable [data-sort="name"]');
    if (await sort.count()) {
      const sorted = page.waitForResponse((r) => new URL(r.url()).searchParams.get("r") === "admin/scores/ranking");
      await sort.click();
      assert.equal((await sorted).status(), 200);
    }
    await page.locator('[data-a="tab"][data-v="simulation"]').click();
    await page.locator("#as-q").fill("TEST03.PA");
    await page.locator('[data-a="sim-run"]').click();
    await page.locator(".as-dec tbody tr").first().waitFor();
    await page.locator('[data-a="tab"][data-v="suivi"]').click();
    await page.getByText("Titres notés", { exact: true }).waitFor();
    await context.close();
    console.log("Aperçu : panne visible, aucune boucle, reprise explicite réussie");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
