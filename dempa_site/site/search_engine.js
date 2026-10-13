// One lazy, retryable Pagefind import per page.
let pagefindPromise;
let failedImports = 0;
export const pagefind = () => {
  // Browsers cache failed module imports by URL. A manual retry needs a fresh
  // URL; successful and concurrent requests still share the same engine.
  const source = `/pagefind/pagefind.js${failedImports ? `?retry=${failedImports}` : ""}`;
  pagefindPromise ||= import(source).then(async engine => {
    await engine.options({highlightParam: "highlight"});
    return engine;
  }).catch(error => { pagefindPromise = undefined; failedImports += 1; throw error; });
  return pagefindPromise;
};
