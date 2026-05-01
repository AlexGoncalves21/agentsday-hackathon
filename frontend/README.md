# Frontend

Small Vite UI for browsing the Organizer graph.

Run from this directory:

```bash
npm install
npm run dev
```

The dev server exposes generated files from the repo-level `brain/` directory at `/brain/*`. Run the Organizer first so `brain/graph.json` and `brain/graph_diff.json` exist.

The UI uses the current graph plus a local browser snapshot to highlight nodes and links that changed since the previous UI visit.
