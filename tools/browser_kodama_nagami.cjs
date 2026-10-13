// Regression checks for the bibliography guide, called by browser_check.cjs.
const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async function checkBibliography(page, go, width, output, report) {
  const query = page.locator('[data-kn-filter] [name="q"]');
  const visible = () => page.locator('[data-kn-item]:visible').count();
  const shot = async name => {
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      `Bibliography page overflows at ${width}px`);
    const file = `${width}-bibliography-${name}.png`;
    await page.screenshot({path: path.join(output, file), animations: 'disabled'});
    report.screenshots.push(file);
  };

  for (const route of ['references', 'correspondence']) {
    await go(`/kodama-nagami/${route}/`);
    const shortcut = page.locator('[data-kn-search-shortcut] a');
    const bounds = await shortcut.boundingBox();
    assert(bounds && bounds.y >= 0 && bounds.y + bounds.height < 900,
      `Search shortcut should be on the first screen (${route}, ${width}px)`);
    await shot(`${route}-top`);
    await shortcut.focus();
    await page.keyboard.press('Enter');
    assert(await query.evaluate(input => document.activeElement === input));
    const inputBounds = await query.boundingBox();
    assert(inputBounds.y >= 0 && inputBounds.y + inputBounds.height < 900);
  }
  report.checks.push(`${width}: bibliography search shortcuts are visible and focus the search field`);

  const reference = '#ref-Morita1970Completions';
  await go(`/kodama-nagami/references/${reference}`);
  assert(await page.locator(`${reference} details`).evaluate(details => details.open));
  await query.fill('Urysohn');
  assert.equal(await visible(), 6);
  assert.equal(new URL(page.url()).hash, '');
  await page.reload();
  assert.equal(await query.inputValue(), 'Urysohn');
  assert.equal(await visible(), 6);
  // Previously copied URLs may still contain a stale fragment: explicit search
  // conditions must also win when opening one of those URLs directly.
  await go(`/kodama-nagami/references/?q=Urysohn${reference}`);
  assert.equal(await query.inputValue(), 'Urysohn');
  assert.equal(await visible(), 6);
  report.checks.push(`${width}: bibliography search survives reload and a stale anchor`);

  const originalDetails = await page.locator('[data-kn-item]').evaluateAll(cards =>
    Object.fromEntries(cards.map(card => [card.id, card.querySelector('details').innerHTML])));
  await query.fill('47.25');
  assert.equal(await visible(), 2);
  for (const card of await page.locator('[data-kn-item]:visible').all()) {
    assert((await card.innerText()).includes('47.25'), 'Hidden matches need visible context');
    assert((await card.locator('.kn-matches').innerText()).includes('47.25'));
    assert((await card.locator('.kn-matches p').innerText()).length < 250, 'Prefer a concise matching sentence or locator');
    assert.equal(await card.locator('details').evaluate(details => details.open), false);
    assert.equal(await card.locator('details').innerHTML(), originalDetails[await card.getAttribute('id')]);
  }
  await page.locator('[data-kn-item]:visible').first().scrollIntoViewIfNeeded();
  await shot('number-match');
  await query.fill('４７．２５');
  assert.equal(await visible(), 2);
  assert.equal(await page.locator('.kn-matches:visible').count(), 2);
  await query.fill('<img src=x onerror=alert(1)>');
  assert.equal(await visible(), 0);
  assert.equal(await page.locator('.kn-matches img').count(), 0);
  await page.getByRole('button', {name: '絞り込みを解除'}).click();
  assert.equal(await visible(), 278);
  assert.equal(await page.locator('.kn-matches:visible').count(), 0);
  report.checks.push(`${width}: hidden bibliography matches have safe visible excerpts and reset cleanly`);

  const filters = await page.locator('[data-kn-item]').first().evaluate(item =>
    Object.fromEntries(['chapter', 'section', 'relationship', 'era'].map(name => [name, item.dataset[name].split('|')[0]])));
  for (const [name, value] of Object.entries(filters)) {
    await page.locator(`[data-kn-filter] [name="${name}"]`).selectOption(value);
  }
  const filteredCount = await visible();
  assert(filteredCount > 0 && filteredCount < 278);
  await page.reload();
  for (const [name, value] of Object.entries(filters)) {
    assert.equal(await page.locator(`[data-kn-filter] [name="${name}"]`).inputValue(), value);
  }
  assert.equal(await visible(), filteredCount);
  report.checks.push(`${width}: all bibliography filters survive reload`);

  const first = '#match-morita1970-39-2-full-via-paracompact-completeness';
  const next = '#match-dieudonne-17-2-full-normality';
  await go(`/kodama-nagami/correspondence/?section=39${first}`);
  const section = page.locator('[data-kn-filter] [name="section"]');
  assert.equal(await visible(), 5);
  await page.locator(`${first} a[href="${next}"]`).click();
  assert.equal(new URL(page.url()).hash, next);
  assert.equal(await section.inputValue(), '');
  assert.equal(await visible(), 351);
  assert(await page.locator(`${next} details`).evaluate(details => details.open));
  assert.equal(await page.evaluate(() => document.activeElement.id), next.slice(1));
  await page.goBack();
  assert.equal(await section.inputValue(), '39');
  assert.equal(await visible(), 5);
  await page.goForward();
  assert.equal(await section.inputValue(), '');
  assert.equal(await visible(), 351);
  await page.goBack();
  await page.reload();
  assert.equal(await section.inputValue(), '39');
  assert.equal(await visible(), 5);
  report.checks.push(`${width}: correspondence links, Back, Forward and reload restore the right filters`);
};
