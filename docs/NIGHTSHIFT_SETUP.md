# Meterless Nightshift provider setup

Lens's only model-provider adapter is [`nightshift.py`](../nightshift.py). It uses the [official Meterless Runtime provider contract](https://github.com/Meterless/Meterless/blob/main/docs/agent-ready/add-meterless-provider.md): OpenAI-compatible `/v1/models` and `/v1/chat/completions`, a real bearer token, `meterless-app: lens`, `meterless-scope: user`, and a `meterless/auto` routing model. The World Model reference runtime under `meterless/` is a separate Engine integration.

## Current hardware and proof status

The development PC reports **Intel HD Graphics 620** and no dedicated NVIDIA GPU. Meterless's [Windows edition](https://meterless.ai/windows.html) lists an NVIDIA CUDA GPU. The [Participant Setup Guide, pages 17–20](https://hackathon-server.genai.works/api/v1/cdn/proxy/hackathon/7e1b7ca3995b4673b30a73555c87e71f.pdf), calls for an installed, running Nightshift Runtime/API hotspot and says the free browser experience should not be assumed to expose one. No live Nightshift request has been completed or deployed for Lens as of 27 October 2026. The code and mocked tests are preparation, not a completed hackathon requirement.

## When a supported runtime is available

1. Install Nightshift from Meterless on a supported machine, or use an event-provided/teammate hotspot that permits Lens requests. Obtain the actual runtime token from that runtime; never use the placeholder `rt-local`.
2. Keep the token in local `.env.local` or the server's private environment, never in Git or a browser prompt. Set `NIGHTSHIFT_BASE_URL`, `NIGHTSHIFT_RUNTIME_TOKEN`, and optionally `NIGHTSHIFT_MODEL` as shown in [`.env.example`](../.env.example). A remote URL must use HTTPS.
3. Run `python -m nightshift`. It sends a **synthetic** 8-versus-4 question. A successful response prints `status: used`, the returned model and request ID; it never prints the token. A nonzero exit means the gate is still open.
4. Run Lens with the same private settings. Check the synthetic Zetaris case and inspect **Selected follow-up → AI routing**. The screen and investigation trace must show Nightshift's returned model and request ID, and the selected code must match a real open finding. Save a screenshot or video of this same run.

The model chooses among already-open, allowlisted evidence questions. Lens itself owns evidence links, calculations, source hashes, Zetaris SQL and status. Invalid or unavailable model responses are labelled as such; a fixed follow-up order keeps the review usable but **does not** count as a successful Nightshift request.
