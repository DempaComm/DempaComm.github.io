// Public query parameters retain their existing names and validation.
export const defaults = {q: "", tag: "", year: "", group: "", content: "", paper: "", depth: 1,
  tags: true, paths: true, explicit: true, orphans: true, labels: "auto", spacing: 100};

export function readOptions(search, data, byId, groups) {
  const params = new URLSearchParams(search);
  const value = {...defaults};
  for (const key of ["q", "tag", "year", "group", "content", "paper"]) value[key] = params.get(key) || "";
  if (!byId.has(value.paper)) value.paper = "";
  if (!groups.has(value.group)) value.group = "";
  if (!data.tags.some(tag => tag.name === value.tag)) value.tag = "";
  if (!data.years.some(year => String(year) === value.year)) value.year = "";
  if (!["html", "statements", "corrections"].includes(value.content)) value.content = "";
  for (const key of ["tags", "paths", "explicit", "orphans"]) value[key] = params.get(key) !== "0";
  value.depth = params.get("depth") === "2" ? 2 : 1;
  value.labels = ["all", "none"].includes(params.get("labels")) ? params.get("labels") : "auto";
  value.spacing = Math.max(70, Math.min(160, Number(params.get("spacing")) || 100));
  return value;
}

export function optionsUrl(options, href) {
  const url = new URL(href);
  for (const [key, value] of Object.entries(options)) {
    url.searchParams.delete(key);
    if (value !== defaults[key]) url.searchParams.set(key, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
  }
  return url;
}
