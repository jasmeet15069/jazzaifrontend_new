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

## CI/CD

GitHub Actions now runs on every push and pull request:

- Installs dependencies with `npm ci`.
- Builds the Next.js app with `npm run build`.

Vercel deployment is optional. If this repo is connected to Vercel through the Vercel dashboard, pushes to `main` will already deploy automatically. The included deploy workflow stays disabled until these GitHub repository secrets are added:

- `JAZZ_ENABLE_VERCEL_DEPLOY=true`
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
