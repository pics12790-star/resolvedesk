// Run from the repository root with ResolveDesk running in Luna mode.
// Uses the frontend's existing Playwright dependency; no fixtures or mocked APIs.
const { chromium } = require('../../apps/web/node_modules/playwright');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const out = path.resolve('runtime/readme-luna/capture');
  await fs.mkdir(out, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    recordVideo: { dir: out, size: { width: 1600, height: 1000 } },
    locale: 'en-US', timezoneId: 'Asia/Kolkata',
  });
  const page = await context.newPage();
  const video = page.video();
  const chapters = [];
  const start = Date.now();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  async function chapter(name) {
    chapters.push({ name, seconds: +((Date.now() - start) / 1000).toFixed(2) });
    console.log(name);
  }
  async function pause(ms = 2500) { await page.waitForTimeout(ms); }
  async function show(locator) {
    await locator.scrollIntoViewIfNeeded();
    await locator.hover();
    await pause(800);
  }
  try {
    await page.goto('http://127.0.0.1:8000');
    await page.getByRole('button', { name: 'Start investigation', exact: true }).waitFor();
    const health = await (await context.request.get('http://127.0.0.1:8000/api/health')).json();
    if (health.agent_mode !== 'luna') throw new Error('Expected a real Luna server');
    await chapter('Support inbox · Luna agent');
    await page.screenshot({ path: `${out}/01-inbox.png` });
    await pause(4000);
    const runResponse = page.waitForResponse(r => r.url().endsWith('/api/tickets/T-1001/runs') && r.request().method() === 'POST');
    await show(page.getByRole('button', { name: 'Start investigation', exact: true }));
    await page.getByRole('button', { name: 'Start investigation', exact: true }).click();
    const { id: runId } = await (await runResponse).json();
    await chapter('Live investigation · classification, retrieval, MCP tools');
    await page.getByRole('heading', { name: 'Investigation activity' }).scrollIntoViewIfNeeded();
    for (let i = 0; i < 120; i++) {
      const run = await (await context.request.get(`http://127.0.0.1:8000/api/runs/${runId}`)).json();
      if (run.status === 'awaiting_approval') break;
      if (['failed', 'escalated', 'resolved'].includes(run.status)) throw new Error(`Unexpected run result: ${run.status}: ${run.error || ''}`);
      if (i === 119) throw new Error('Investigation timed out');
      await pause(1000);
    }
    await page.getByRole('button', { name: 'Approve replacement', exact: true }).waitFor();
    await chapter('Policy sources · citations and supporting evidence');
    const policies = page.locator('.policy-citations details');
    for (let i = 0; i < Math.min(await policies.count(), 2); i++) {
      const summary = policies.nth(i).locator('summary');
      await show(summary); await summary.click(); await pause(3500);
    }
    const toolEvidence = page.locator('.timeline li').filter({ hasText: 'get order' }).locator('summary').first();
    if (await toolEvidence.count()) {
      await show(toolEvidence); await toolEvidence.click(); await pause(3500); await toolEvidence.click();
    }
    await chapter('Human review · proposed replacement and customer response');
    await page.locator('.proposal-panel').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${out}/02-approval.png` });
    await pause(6500);
    await show(page.getByRole('button', { name: 'Approve replacement', exact: true }));
    await page.getByRole('button', { name: 'Approve replacement', exact: true }).click();
    await page.getByText('Replacement created', { exact: true }).waitFor({ timeout: 60000 });
    await chapter('Approved action · verified replacement receipt');
    await page.locator('.receipt').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${out}/03-receipt.png` });
    await pause(6000);
    await page.locator('.run-metrics').scrollIntoViewIfNeeded(); await pause(3500);
    const run = await (await context.request.get(`http://127.0.0.1:8000/api/runs/${runId}`)).json();
    const audit = await (await context.request.get(`http://127.0.0.1:8000/api/runs/${runId}/audit`)).json();
    if (run.status !== 'resolved' || !run.state?.receipt) throw new Error('Missing resolved receipt');
    if (!run.state.metrics?.some(m => m.provider === 'openai')) throw new Error('No live OpenAI model calls recorded');
    await show(page.getByRole('button', { name: 'Evaluations', exact: true }));
    await page.getByRole('button', { name: 'Evaluations', exact: true }).click();
    await page.getByRole('heading', { name: 'Evaluation runs', exact: true }).waitFor();
    await chapter('Saved historical evaluations · separate from this live run');
    await page.getByText('Resolution accuracy', { exact: true }).waitFor();
    await pause(6000);
    await page.screenshot({ path: `${out}/04-evaluations.png` });
    await page.getByRole('button', { name: 'Inbox', exact: true }).click();
    await page.getByText('Replacement created', { exact: true }).waitFor();
    await page.locator('.proposal-panel').scrollIntoViewIfNeeded();
    await pause(4000);
    await fs.writeFile(`${out}/workflow.json`, JSON.stringify({ health, run, audit, chapters, browserErrors: errors }, null, 2));
    if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
  } catch (error) {
    await page.screenshot({ path: `${out}/failure.png` });
    console.error(await page.locator('body').innerText());
    throw error;
  } finally {
    await context.close();
    await video.saveAs(path.resolve('docs/design/workflow-luna.webm'));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
