#!/usr/bin/env node
// Run against a fully staged site, including its Pagefind index.
// Usage: node tools/browser_check.cjs URL OUTPUT [BEFORE_OUTPUT]
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const [base, output, before] = process.argv.slice(2);
if (!base || !output) throw new Error('Usage: browser_check.cjs URL OUTPUT [BEFORE_OUTPUT]');

async function pixelDifference(page, left, right) {
  return page.evaluate(async ([a, b]) => {
    const pixels = async encoded => {
      const blob = await (await fetch(`data:image/png;base64,${encoded}`)).blob();
      const bitmap = await createImageBitmap(blob);
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = canvas.getContext('2d');
      context.drawImage(bitmap, 0, 0);
      const result = {width: bitmap.width, height: bitmap.height,
        data: context.getImageData(0, 0, bitmap.width, bitmap.height).data};
      bitmap.close();
      return result;
    };
    const [left, right] = await Promise.all([pixels(a), pixels(b)]);
    const sameSize = left.width === right.width && left.height === right.height;
    let maximumDelta = 0;
    if (sameSize) for (let i = 0; i < left.data.length; i++) {
      maximumDelta = Math.max(maximumDelta, Math.abs(left.data[i] - right.data[i]));
    }
    return {sameSize, maximumDelta};
  }, [left.toString('base64'), right.toString('base64')]);
}

async function run() {
  await fs.mkdir(output, {recursive: true});
  const browser = await chromium.launch({
    ...(process.env.BROWSER_EXECUTABLE ? {executablePath: process.env.BROWSER_EXECUTABLE} : {}),
  });
  const report = {browser: browser.version(), conditions: {date: '2026-09-28', motion: 'reduce', fonts: 'offline fallback', random: 'fixed'}, screenshots: [], comparisons: [], checks: [], errors: []};
  try {
    for (const width of [1280, 390, 320]) {
      const context = await browser.newContext({viewport: {width, height: 900}, reducedMotion: 'reduce', locale: 'ja-JP', timezoneId: 'Asia/Tokyo'});
      // Keep the daily recommendation and fallback fonts reproducible offline.
      await context.addInitScript(() => {
        Math.random = () => 0.25;
        crypto.getRandomValues = values => { values.fill(0); return values; };
        const OriginalDate = Date;
        window.Date = class extends OriginalDate {
          constructor(...args) { super(...(args.length ? args : ['2026-09-28T12:00:00+09:00'])); }
          static now() { return new OriginalDate('2026-09-28T12:00:00+09:00').getTime(); }
        };
      });
      await context.route('https://**/*', route => route.abort());
      const page = await context.newPage();
      page.on('pageerror', error => report.errors.push(`${width}: ${error.message}`));
      const go = async route => {
        await page.goto(new URL(route, base).href);
        await page.evaluate(() => document.fonts.ready);
      };
      const shot = async name => {
        await page.evaluate(() => {
          document.activeElement?.blur();
          window.scrollTo(0, 0);
          return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        });
        const file = `${width}-${name}.png`;
        if (name.startsWith('graph')) {
          const graphState = await page.locator('#paper-graph').evaluate(svg => ({
            markup: svg.outerHTML, width: svg.clientWidth, height: svg.clientHeight,
            scrollX, scrollY, pixelRatio: devicePixelRatio,
          }));
          await fs.writeFile(path.join(output, `${width}-${name}.json`), JSON.stringify(graphState, null, 2));
          if (before) assert.deepEqual(graphState,
            JSON.parse(await fs.readFile(path.join(before, `${width}-${name}.json`), 'utf8')),
            `Graph DOM or geometry difference: ${file}`);
        }
        const image = await page.screenshot({path: path.join(output, file), fullPage: true, animations: 'disabled'});
        if (before) {
          const reference = await fs.readFile(path.join(before, file));
          const exact = image.equals(reference);
          const difference = exact ? {sameSize: true, maximumDelta: 0} : await pixelDifference(page, reference, image);
          // SVG compositing may round an 8-bit color channel by one even with
          // identical DOM/geometry/CSS. No geometry or larger pixel change passes.
          assert.ok(difference.sameSize && difference.maximumDelta <= (name.startsWith('graph') ? 1 : 0),
            `Visual difference: ${file} (${JSON.stringify(difference)})`);
          report.comparisons.push({file, exact, ...difference});
        }
        report.screenshots.push(file);
      };
      await go('/');
      await page.waitForSelector('#today-paper a');
      await shot('home');
      const graphLink = page.getByRole('link', {name: '関係図を開く', exact: true});
      await graphLink.focus();
      await page.keyboard.press('Enter');
      await page.waitForURL(new URL('/graph/', base).href);
      assert.equal(new URL(page.url()).pathname, '/graph/');
      await page.waitForSelector('#paper-graph [data-graph-slug]');
      report.checks.push(`${width}: home graph link opens the interactive graph with Enter`);
      for (const [route, name] of [['/math/', 'math'], ['/explore/', 'explore'], ['/reading-paths/', 'paths'], ['/lineage/', 'lineage'], ['/404.html', '404']]) {
        await go(route); await shot(name);
      }

      await go('/archive/');
      await page.waitForFunction(() => document.querySelectorAll('.paper-card:not([hidden])').length === 10);
      await shot('archive');
      await page.locator('#paper-more').click();
      assert.equal(await page.locator('.paper-card:visible').count(), 20);
      await page.locator('.paper-card:visible h3 a, .paper-card:visible h2 a').nth(12).click();
      await page.goBack();
      await page.waitForFunction(() => document.querySelectorAll('.paper-card:not([hidden])').length === 20);
      await page.locator('#paper-query').fill('zz-no-match-9876');
      assert.equal(await page.locator('.paper-card:visible').count(), 0);
      await shot('archive-empty');
      await page.locator('#paper-reset').click();
      assert.equal(await page.locator('.paper-card:visible').count(), 10);
      report.checks.push(`${width}: archive pagination, return and reset`);

      await go('/search/?q=' + encodeURIComponent('ディリクレ積分'));
      await page.waitForFunction(() => document.querySelector('#fulltext-results').children.length === 2);
      await shot('search');
      await page.locator('#fulltext-results h2 a').first().click();
      await page.waitForSelector('.pagefind-highlight');
      await shot('reader');
      await page.goBack();
      await page.waitForFunction(() => document.querySelector('#fulltext-results').children.length === 2);
      await page.locator('#fulltext-reset').click();
      assert.equal(await page.locator('#fulltext-query').inputValue(), '');
      assert.equal(await page.locator('#fulltext-results > li').count(), 0);
      assert.equal(new URL(page.url()).searchParams.has('q'), false);
      await page.locator('#fulltext-query').fill('数学');
      await page.locator('#fulltext-search-form').evaluate(form => form.requestSubmit());
      await page.locator('#fulltext-query').fill('');
      await page.waitForTimeout(500);
      assert.equal(await page.locator('#fulltext-results > li').count(), 0);
      report.checks.push(`${width}: Japanese full text, highlight, return and cancellation`);

      await go('/statements/years/2020/');
      await page.waitForSelector('#statement-query');
      await shot('statements');
      await page.locator('#statement-query').fill('zz-no-match-9876');
      assert.equal(await page.locator('.statement-list li[data-kind]:visible').count(), 0);
      await page.locator('#statement-reset').click();
      assert.ok(await page.locator('.statement-list li[data-kind]:visible').count() > 0);
      report.checks.push(`${width}: statement filtering and reset`);

      await go('/graph/');
      await page.waitForSelector('#paper-graph [data-graph-slug]');
      const total = await page.locator('#paper-graph [data-graph-slug]').count();
      const graphData = await (await page.request.get(new URL("/graph/paper-graph.json", base).href)).json();
      assert.equal(total, graphData.nodes.length);
      await shot('graph');
      await page.locator('#graph-zoom-in').click();
      const node = page.locator('#paper-graph [data-graph-slug]').first();
      await node.focus(); await page.keyboard.press('Enter');
      await page.waitForSelector('#graph-detail-heading');
      const title = await page.locator('#graph-detail-heading').textContent();
      await shot('graph-selected');
      const view = await page.locator('#paper-graph').getAttribute('viewBox');
      await page.locator('#graph-detail a').filter({hasText: '原稿ページ'}).click();
      await page.goBack();
      await page.waitForSelector('#graph-detail-heading');
      assert.equal(await page.locator('#graph-detail-heading').textContent(), title);
      assert.equal(await page.locator('#paper-graph').getAttribute('viewBox'), view);
      await page.locator('#graph-detail button').filter({hasText: 'この原稿の周辺を見る'}).click();
      assert.ok(await page.locator('#paper-graph [data-graph-slug]').count() < total);
      await page.locator('#graph-all').click();
      await page.locator('#graph-query').fill('zz-no-match-9876');
      await page.waitForFunction(() => document.querySelectorAll('#paper-graph [data-graph-slug]').length === 0);
      await shot('graph-empty');
      await page.locator('#graph-empty-reset').click();
      await page.waitForFunction(total => document.querySelectorAll('#paper-graph [data-graph-slug]').length === total, total);
      report.checks.push(`${width}: graph keyboard selection, zoom, return, neighborhood, empty and reset`);
      await context.close();
    }
    assert.deepEqual(report.errors, [], 'Browser runtime errors');
    console.log(`OK: ${report.checks.length} interaction groups, ${report.screenshots.length} screenshots${before ? ', visual and graph DOM comparisons passed' : ''}`);
  } finally {
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
