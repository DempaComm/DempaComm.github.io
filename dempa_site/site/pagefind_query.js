// Preserve indexed katakana words when the browser's ICU dictionary splits
// them differently from Pagefind's build-time Japanese dictionary.
export function indexedKatakanaSegments(term, language, segmenter, vocabulary) {
  const segments = [...segmenter.segment(term)];
  if (language.split("-")[0].toLowerCase() !== "ja") return segments;
  const katakana = /^[\u30A1-\u30FA\u30FC]+$/u;
  const result = [];
  for (let i = 0; i < segments.length; i++) {
    let word = segments[i].segment;
    let last = i;
    let joined = word;
    if (katakana.test(word)) {
      for (let j = i + 1; j < segments.length && katakana.test(segments[j].segment); j++) {
        joined += segments[j].segment;
        if (vocabulary.has(joined.normalize("NFKC"))) {
          word = joined;
          last = j;
        }
      }
    }
    result.push({segment: word});
    i = last;
  }
  return result;
}
