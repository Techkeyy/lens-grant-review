# Third-party notices

## Meterless World Model reference

This repository includes files copied from [Meterless/Meterless](https://github.com/Meterless/Meterless), commit `1742dec56a66e58eef9dda2d2b865823758ca8cd` (23 October 2026): `meterless/vendor/src/`, `meterless/vendor/conformance/runner.ts`, `meterless/vendor/conformance/README.md`, `meterless/vendor/REFERENCE_README.md`, and `meterless/vendor/UPSTREAM_AGENTS.md`.

The copied reference and conformance files are distributed under Apache License 2.0. The full license text is retained at [`meterless/vendor/LICENSE`](meterless/vendor/LICENSE). Lens-specific adapter, bridge, proof, and test code lives outside `meterless/vendor/`.

The standalone [Meterless/World-Model](https://github.com/Meterless/World-Model) repository was consulted as architecture material; the runnable reference copied here came from `Meterless/Meterless`.

## Supabase JavaScript client

The public Google sign-in flow uses the UMD distribution of [`@supabase/supabase-js`](https://github.com/supabase/supabase-js), version `2.118.0`, saved as [`web/vendor/supabase.js`](web/vendor/supabase.js) from the package's versioned jsDelivr distribution. It is distributed under the MIT License. The full license text is retained at [`web/vendor/SUPABASE_LICENSE`](web/vendor/SUPABASE_LICENSE). The public client uses only the publishable or legacy anonymous key; the service-role key remains server-side.

## Results page fonts

The self-hosted results page uses [Fraunces](https://github.com/undercasetype/Fraunces) and [DM Sans](https://github.com/googlefonts/dm-fonts) WOFF2 font files in `web/fonts/`. Both are distributed under the SIL Open Font License 1.1. Their license and copyright notices are retained at [`web/fonts/OFL-Fraunces.txt`](web/fonts/OFL-Fraunces.txt) and [`web/fonts/OFL-DM-Sans.txt`](web/fonts/OFL-DM-Sans.txt).
