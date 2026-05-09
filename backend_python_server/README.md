# Jazz Jarvis Backend

Isolated FastAPI service for the `/jarvis` console. It proxies authenticated chat to the existing Jazz AI backend on port 8000 and keeps file operations inside `/root/jazzai/jarvis_workspace`.

Production service:

- Port: `43432`
- Service: `jarvis-ai.service`
- Backend core API: `http://127.0.0.1:8000`

Do not replace or modify `server14.py` for this service.
