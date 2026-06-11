# Third-Party Notices

This repository does not vendor the following upstream source trees, datasets,
or model weights. The setup script clones selected dependencies into ignored
directories. Review each upstream license before use.

| Component | Source and pinned revision | License or restriction |
|---|---|---|
| EdgeFace | https://github.com/otroshi/edgeface.git at `ce86851cfc37979a9cd2558598d0e9bc592cbba3` | BSD-3-Clause; verify model-weight terms before deployment |
| Silent-Face-Anti-Spoofing | https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git at `b6d5f04ad78778917853b25c778acef6d5626d15` | Apache-2.0 |
| InsightFace Python package | https://github.com/deepinsight/insightface | Code and pretrained model packs have different terms; pretrained models are restricted to non-commercial research |
| FAISS | Installed from `faiss-cpu`; source at https://github.com/facebookresearch/faiss | MIT |
| art-design-pro | https://github.com/Daymychen/art-design-pro.git at `6b6d781a63eb51782841ac9c29c2bb42a23911f2` | MIT; visual layout reference |
| soybean-admin | https://github.com/soybeanjs/soybean-admin.git at `9afb335ed6857d2d84f7d0dd4ceddaab856e1dc7` | MIT; visual layout reference |
| vue-element-plus-admin | https://github.com/kailong321200875/vue-element-plus-admin.git at `38047fba67ea1e0fac9d576caf0facd39c96d235` | MIT; interaction reference |
| vue-pure-admin | https://github.com/pure-admin/vue-pure-admin.git at `ab218398ffd75825913ada95fd61a6bea3e220dd` | MIT; interaction reference |

Full MIT notices for the four referenced frontend projects are preserved in
the `licenses/` directory.

Frontend package licenses remain available through `frontend/pnpm-lock.yaml`
and the corresponding package registries.

Project-authored adapters and frontend components may identify upstream
projects as technical or visual references. Those upstream repositories are
not copied wholesale into this repository.
