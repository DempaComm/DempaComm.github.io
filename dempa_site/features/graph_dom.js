// DOM constructors shared by the graph controller and inspector.
const ns = "http://www.w3.org/2000/svg";
export const html = (name, className = "", text = "") => {
  const element = document.createElement(name);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
};
export const makeSvg = (name, attributes = {}) => {
  const element = document.createElementNS(ns, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
};
export const button = (text, action, className = "") => {
  const element = html("button", className, text);
  element.type = "button";
  element.addEventListener("click", action);
  return element;
};
export const link = (text, href, className = "") => {
  const element = html("a", className, text);
  element.href = href;
  return element;
};
export const shortTitle = (title, limit = 15) => Array.from(title).length > limit
  ? Array.from(title).slice(0, limit).join("") + "…" : title;
