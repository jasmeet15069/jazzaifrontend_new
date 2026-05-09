import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function jsString(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

export async function GET() {
  const htmlPath = path.join(process.cwd(), 'public', 'jarvis.html');
  const apiBase = process.env.NEXT_PUBLIC_JARVIS_API_BASE || '/api/jarvis';
  let html = await readFile(htmlPath, 'utf8');
  html = html.replace('__JARVIS_API_BASE__', jsString(apiBase));
  return new Response(html, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-store, max-age=0',
      pragma: 'no-cache',
    },
  });
}
