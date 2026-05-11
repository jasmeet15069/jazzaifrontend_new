import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const FALLBACK_API_BASE = 'http://45.79.124.28:8000';

function jsString(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

export async function GET() {
  const htmlPath = path.join(process.cwd(), 'public', 'jazz-index.html');
  const apiBase = process.env.NEXT_PUBLIC_JAZZ_API_BASE || process.env.JAZZ_API_BASE || FALLBACK_API_BASE;
  let html = await readFile(htmlPath, 'utf8');

  html = html.replace(
    `const DEFAULT_API_BASE = '${FALLBACK_API_BASE}';`,
    `const DEFAULT_API_BASE = '${jsString(apiBase)}';`,
  );

  return new Response(html, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-store, max-age=0',
      pragma: 'no-cache',
    },
  });
}
