// Exercise the generated search API and WASM against local files, without a browser.
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {pathToFileURL} from "node:url";
import path from "node:path";
import vm from "node:vm";
import {indexedKatakanaSegments} from "../dempa_site/site/pagefind_query.js";

const segments = word => ({segment: word});
const split = {segment: () => ["ディリ", "ク", "レ", " ", "ディリ", "ク", "レ", "積分"].map(segments)};
const vocabulary = new Set(["ディリクレ"]);
assert.deepEqual(indexedKatakanaSegments("", "ja", split, vocabulary).map(v => v.segment),
  ["ディリクレ", " ", "ディリクレ", "積分"]);
assert.deepEqual(indexedKatakanaSegments("", "en", split, vocabulary), split.segment());
assert.deepEqual(indexedKatakanaSegments("", "ja", split, new Set()), split.segment());
const spaced = {segment: () => ["ディリ", " ", "クレ"].map(segments)};
assert.deepEqual(indexedKatakanaSegments("", "ja", spaced, vocabulary), spaced.segment());

const site = process.argv[2];
new vm.Script(await readFile(path.join(site, "pagefind/pagefind-worker.js"), "utf8"));
globalThis.fetch = async url => new Response(await readFile(path.join(site, new URL(url, "http://local").pathname)));
globalThis.document = {currentScript: null, querySelector: () => ({getAttribute: () => "ja"})};
const module = await import(pathToFileURL(path.join(site, "pagefind/pagefind.js")));
const engine = module.createInstance({basePath: "http://local/pagefind/", baseUrl: "/", noWorker: true, highlightParam: "highlight"});
try {
  await engine.init();
  for (const query of ["ディリクレ", "ディリクレ積分", "積分", "パラコンパクト", '"ディリクレ 積分"']) {
    const response = await engine.search(query);
    assert.equal(response.results.length, 1, `${query}: matching text must be found`);
    const data = await response.results[0].data();
    assert.match(data.url, /2026-07-28-01/);
    assert.match(data.excerpt, /<mark>/, `${query}: the actual match must be highlighted`);
    if (query.includes("ディリクレ")) {
      assert.ok(new URL(data.url, "http://local").searchParams.getAll("highlight").includes("ディリクレ"),
        "reader highlights must retain dakuten");
    }
  }
  assert.equal((await engine.search("存在しない検索語xyz")).results.length, 0);
} finally {
  await engine.destroy();
}
