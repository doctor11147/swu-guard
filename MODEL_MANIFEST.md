# Model Manifest

No model weights are committed to this repository.

| Runtime capability | Expected location | Acquisition |
|---|---|---|
| SCRFD detector | `app/models/insightface/models/buffalo_sc/` | Downloaded by InsightFace on first use; subject to InsightFace model terms |
| EdgeFace embedder | `edgeface/checkpoints/edgeface_s_gamma_05.pt` | Included by the pinned EdgeFace upstream revision; verify weight terms |
| MiniFAS liveness models | `Silent-Face-Anti-Spoofing/resources/anti_spoof_models/` | Included by the pinned Silent-FAS upstream revision |
| Quality gate | None | The public version uses Laplacian sharpness and requires no weight |

Datasets are not required to run the application. Evaluation datasets must be
downloaded separately under their own licenses and must never be committed.
