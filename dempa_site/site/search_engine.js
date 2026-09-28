// One lazy, retryable Pagefind import per page.
let pagefindPromise;
export const pagefind = () => {
  pagefindPromise ||= import("/pagefind/pagefind.js").then(async engine => {
    await engine.options({highlightParam: "highlight"});
    return engine;
  }).catch(error => { pagefindPromise = undefined; throw error; });
  return pagefindPromise;
};
