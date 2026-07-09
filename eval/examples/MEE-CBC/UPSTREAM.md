Upstream: https://github.com/EasyCrypt/easycrypt/tree/main/examples/MEE-CBC
Imported from EasyCrypt commit: eb58ec7619172737ba19f3f86ed3b264fc8d6017
Commit date: 2026-05-01T16:23:17Z
Commit subject: [docker] provers: bump alt-ergo to 2.6.3

This directory is intended as a local benchmark corpus for the Shannon Prover
workflow. Do not import unrelated upstream examples into this directory.

Local smoke check, 2026-05-05:

- Passed: FunctionalSpec.ec
- Passed: MAC_then_Pad_then_CBC.eca
- Passed: MACs.eca
- Passed: RCPA_CMA.ec
- Passed: RCPA_pad.eca
- Passed: SKE_INDR.eca
- Strict proof failure in this local EasyCrypt/prover environment: CBC.eca,
  line 821, at `rcondt{2} 3; first auto => />; smt(mulrSl).`

Include path used:

```sh
easycrypt -I easycrypt-src/theories \
  -I easycrypt-src/theories/crypto \
  -I easycrypt-src/theories/datatypes \
  -I easycrypt-src/theories/distributions \
  -I eval/examples/MEE-CBC <file>
```
