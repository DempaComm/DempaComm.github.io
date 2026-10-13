// Exercise a real failed module import: browsers remember failures by URL.
const assert = require('node:assert/strict');

module.exports = async function checkSearchRecovery(page, go, width, report) {
  const moduleRoute = '**/pagefind/pagefind.js*';
  let requests = 0;
  let fail = true;
  await page.route(moduleRoute, route => {
    requests += 1;
    return fail ? route.abort('failed') : route.continue();
  });
  try {
    await go('/search/?q=' + encodeURIComponent('ディリクレ積分'));
    const waitForFailure = () => page.waitForFunction(() =>
      document.querySelector('#fulltext-status').textContent.includes('読み込めません'));
    await waitForFailure();
    assert.equal(requests, 1);
    await page.locator('#fulltext-search-form button[type="submit"]').click();
    await waitForFailure();
    assert.equal(requests, 2, 'A failed retry must not prevent another network request');
    fail = false;
    // Two submissions during the same import should share one engine. Only
    // the newest query may render, with no duplicate results.
    await page.locator('#fulltext-search-form').evaluate(form => {
      form.requestSubmit(); form.requestSubmit();
    });
    await page.waitForFunction(() => document.querySelector('#fulltext-results').children.length === 2);
    assert.equal(requests, 3);
    assert.equal(await page.locator('#fulltext-query').inputValue(), 'ディリクレ積分');
    await page.locator('#fulltext-query').fill('数学');
    await page.locator('#fulltext-search-form button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector('#fulltext-results').children.length > 2);
    assert.equal(requests, 3, 'Subsequent searches should reuse the recovered engine');
    report.checks.push(`${width}: full-text search recovers after repeated import failures and shares the recovered engine`);
  } finally {
    await page.unroute(moduleRoute);
  }
};
