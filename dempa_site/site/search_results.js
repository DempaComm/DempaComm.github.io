// Reconstruct only the allowed text, marks and MathML in result labels.
const excerptNodes = (markup) => {
  const template = document.createElement("template");
  template.innerHTML = markup || "";
  const fragment = document.createDocumentFragment();
  const copy = (node, parent) => {
    if (node.nodeType === Node.TEXT_NODE) {
      parent.append(document.createTextNode(node.textContent));
    } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "MARK") {
      const mark = document.createElement("mark");
      mark.textContent = node.textContent;
      parent.append(mark);
    } else {
      for (const child of node.childNodes) copy(child, parent);
    }
  };
  copy(template.content, fragment);
  return fragment;
};

const headingNodes = (markup) => {
  const template = document.createElement("template");
  template.innerHTML = markup;
  const fragment = document.createDocumentFragment();
  const mathTags = new Set("math mi mn mo mtext mrow mstyle mfrac msqrt mroot msub msup msubsup munder mover munderover mmultiscripts mprescripts none mtable mtr mtd mspace menclose mpadded mphantom mfenced semantics".split(" "));
  const mathAttributes = new Set("mathvariant stretchy symmetric largeop movablelimits accent accentunder fence separator lspace rspace linethickness bevelled rowalign columnalign columnspan rowspan notation width height depth open close separators".split(" "));
  const copy = (node, parent) => {
    if (node.nodeType === Node.TEXT_NODE) {
      parent.append(document.createTextNode(node.textContent));
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      if (["annotation", "annotation-xml", "script", "style"].includes(node.localName)) return;
      let target = parent;
      if (mathTags.has(node.localName)) {
        target = document.createElementNS("http://www.w3.org/1998/Math/MathML", node.localName);
        for (const attribute of node.attributes) {
          if (mathAttributes.has(attribute.name)) target.setAttribute(attribute.name, attribute.value);
        }
        parent.append(target);
      }
      // Unwrap source links and formatting; result labels are already links.
      for (const child of node.childNodes) copy(child, target);
    }
  };
  for (const child of template.content.childNodes) copy(child, fragment);
  return fragment;
};

export const resultItem = (data) => {
  const item = document.createElement("li");
  const title = document.createElement("h2");
  const link = document.createElement("a");
  const sections = data.sub_results || [];
  const best = sections.find(section => section.anchor) || sections[0] || data;
  link.href = best.url;
  link.textContent = data.meta?.title || data.url;
  title.append(link);
  const excerpt = document.createElement("p");
  excerpt.append(excerptNodes(best.excerpt || data.excerpt));
  item.append(title, excerpt);
  const anchored = sections.filter(section => section.anchor);
  if (anchored.length) {
    const passages = document.createElement("ul");
    passages.className = "fulltext-passages";
    for (const section of anchored.slice(0, 3)) {
      const passage = document.createElement("li");
      const jump = document.createElement("a");
      jump.href = section.url;
      const heading = data.meta?.[`heading_html_${section.anchor.id}`];
      if (heading) jump.append(headingNodes(heading));
      else jump.textContent = section.title;
      passage.append(jump);
      passages.append(passage);
    }
    item.append(passages);
  }
  return item;
};
