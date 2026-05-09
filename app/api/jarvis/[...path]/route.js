export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const JARVIS_BACKEND_BASE = (process.env.JARVIS_BACKEND_BASE || 'http://45.79.124.28:43432').replace(/\/+$/, '');

async function proxy(request, context) {
  const source = new URL(request.url);
  const parts = source.pathname.replace(/^\/api\/jarvis\/?/, '');
  const target = `${JARVIS_BACKEND_BASE}/${parts}${source.search}`;
  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('connection');

  const init = {
    method: request.method,
    headers,
    body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
    duplex: 'half',
    redirect: 'manual',
  };

  const response = await fetch(target, init);
  const outHeaders = new Headers(response.headers);
  outHeaders.delete('content-encoding');
  outHeaders.delete('content-length');
  outHeaders.set('cache-control', 'no-store, max-age=0');
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: outHeaders,
  });
}

export async function GET(request, context) { return proxy(request, context); }
export async function POST(request, context) { return proxy(request, context); }
export async function PATCH(request, context) { return proxy(request, context); }
export async function PUT(request, context) { return proxy(request, context); }
export async function DELETE(request, context) { return proxy(request, context); }
