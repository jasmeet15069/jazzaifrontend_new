import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const htmlPath = path.join(process.cwd(), 'public', 'jazz-index.html');
  const html = await readFile(htmlPath, 'utf8');

  return new Response(html, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-store, max-age=0',
      pragma: 'no-cache',
    },
  });
}
