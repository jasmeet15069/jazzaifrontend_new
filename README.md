# jazzaifrontend_new

Next.js wrapper for the JAZZ AI frontend.

The current production UI is preserved in `public/jazz-index.html` and served from the root Next.js route in `app/route.js`. It keeps the same API calls and backend routing behavior as the existing `index.html`.

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Vercel Environment

Set `NEXT_PUBLIC_JAZZ_API_BASE` to the public URL of the Jazz backend.

Example:

```env
NEXT_PUBLIC_JAZZ_API_BASE=https://imperceptibly-hymnlike-leesa.ngrok-free.dev
```
