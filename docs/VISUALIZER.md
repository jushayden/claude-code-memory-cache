# The Live 3D Memory Graph (optional)

![The live 3D memory graph](assets/memory-graph.png)

Every chunk in your memory store rendered as a node in an interactive 3D force
graph — semantically similar memories cluster together, hub memories grow larger,
and the whole thing **lights up in real time** as your Claude sessions search and
save memory. Think Obsidian's graph view, in 3D, wired to your agent's brain.

Entirely optional: nothing else in the system depends on it.

## Start it

```bash
pip install -r requirements-visualizer.txt
python visualizer/graph_server.py --open
```

First run builds the graph (embeds every chunk locally + computes a 3D layout —
a minute or two for a few thousand chunks; cached afterward). Then it serves at
`http://127.0.0.1:8010` (localhost only).

Flags: `--port`, `--open`, `--rebuild` (after lots of new memories), `--max-nodes`.

## What you get

- **Nodes** = memory chunks, colored by type (decisions, learnings, preferences,
  architecture, vault docs...), sized by connectedness — hubs tower over one-offs.
- **Edges** = k-nearest-neighbor semantic similarity.
- **Live pulses**: when any session runs `memory_search`, the hit nodes flash and
  a light travels along the connections between results, from the strongest match
  outward. `memory_save` pops a new node in, wired to its neighbors. (Requires the
  updated `memory_server/server.py` in this repo — it notifies the visualizer
  fire-and-forget; if the visualizer isn't running, nothing happens.)
- **Hologram mode**: HUD toggle — monochrome cyan, additive glow, and a radial
  force that wraps the graph onto a rotating hollow globe. Pulses go hot orange.
- **2D view** at `/2d` if you prefer the classic flat graph.

Controls: drag to rotate, scroll/pinch to zoom, hover to read a memory, click to
fly to it. The camera slowly auto-orbits (`spin` toggle in the HUD).

## Kiosk / wall-display mode

`http://127.0.0.1:8010/?lite&kiosk` — `lite` disables bloom and thins effects for
weak GPUs (e.g. a Raspberry Pi); `kiosk` compacts the UI for small touchscreens
and adds on-screen zoom buttons. To show it on another device, expose the port on
your private network (e.g. Tailscale: `tailscale serve --bg --tcp 8010 tcp://127.0.0.1:8010`).
Don't expose it to the public internet — it has no auth by design (localhost tool).

## Concurrency note

ChromaDB allows one writer. The visualizer reads your store once at startup and
caches a snapshot, which coexists fine with a running memory server in most
setups — but if you hit locking issues, either run the visualizer while sessions
are idle, or serve Chroma over HTTP (`chroma run --path <your store>`) and point
the visualizer at it with `MEMORY_CACHE_CHROMA_HTTP=127.0.0.1:8000`.

## Credits

Bundled libraries (all MIT): [three.js](https://threejs.org),
[3d-force-graph](https://github.com/vasturiano/3d-force-graph),
[force-graph](https://github.com/vasturiano/force-graph), and three.js'
UnrealBloomPass. Vendored into `visualizer/static/` so the page works fully offline.
