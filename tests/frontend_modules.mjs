import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';

const base = pathToFileURL(process.argv[2] + '/');
const load = path => import(new URL(path, base));
// Importing every leaf also checks named exports and relative public module paths.
for (const path of ['graph/graph-dom.js', 'graph/graph-inspector.js', 'graph/graph-view.js',
  'search-engine.js', 'search-results.js']) await load(path);
const {defaults, readOptions, optionsUrl} = await load('graph/graph-state.js');
const data = {tags: [{name: '位相'}], years: [2026]};
const nodes = new Map([['paper', {}]]), groups = new Map([['topology', {}]]);
const read = value => readOptions(value, data, nodes, groups);
assert.deepEqual(read(''), defaults);
assert.deepEqual(read('?paper=missing&group=missing&tag=missing&year=1900&content=missing'), defaults);
const filters = {...defaults, q: '距離 空間', tag: '位相', paper: 'paper', group: 'topology', year: '2026',
  content: 'html', tags: false, paths: false, depth: 2, labels: 'all', spacing: 160};
const url = optionsUrl(filters, 'https://example.test/graph/?q=old&extra=keep#position');
assert.deepEqual(read(url.search), filters);
assert.equal(url.hash, '#position');
assert.equal(url.searchParams.get('extra'), 'keep');
assert.equal(optionsUrl(defaults, url).search, '?extra=keep');
assert.equal(read('?spacing=-10').spacing, 70);
assert.equal(read('?spacing=999').spacing, 160);
assert.equal(read('?spacing=not-a-number').spacing, 100);
assert.equal(read('?depth=3&labels=unknown').depth, 1);
assert.equal(read('?depth=3&labels=unknown').labels, 'auto');
assert.equal(defaults.tags, true, 'parsing does not mutate defaults');
console.log('Public module imports and graph URL contracts passed.');
