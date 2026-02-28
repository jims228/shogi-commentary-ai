export function parseCsv(text: string) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return [];
  const headers = lines[0].split(",").map((h) => h.trim());
  const rows = lines.slice(1).map((ln) => {
    // naive split, works for our simple CSV
    const cols = ln.split(",");
    const obj: Record<string, string> = {};
    for (let i = 0; i < headers.length; i++) obj[headers[i]] = (cols[i] || "").trim();
    return obj;
  });
  return rows;
}
