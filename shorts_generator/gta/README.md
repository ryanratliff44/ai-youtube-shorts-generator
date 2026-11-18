# GTA clips (gated)

Nothing publishes unless the source is in the ledger **and** you approved the clip.

```bash
python -m shorts_generator.gta source add game.mp4 --kind own_capture
python -m shorts_generator.gta source add stream.mp4 --kind written_permission --note "OK from <streamer>, saved at <where>"
python -m shorts_generator.gta run game.mp4 --out clips --captions   # renders; all clips start pending
python -m shorts_generator.gta approve clips 1 3                      # after you watch them
python -m shorts_generator.gta publish clips --to youtube             # dry run
python -m shorts_generator.gta publish clips --to youtube --yes       # real upload, private by default
```

- Credentials: `GTA_YT_CLIENT_JSON` and `GTA_YT_TOKEN_JSON` point to files **outside** the repo, for the GTA channel (not another channel).
- Daily cap: 3 real uploads per platform per 24h (`--cap`).
- TikTok and Instagram refuse real uploads until their approved API credentials are added.
- Quality check (needs an ffmpeg build with libvmaf): `ffmpeg -i out.mp4 -i master.mp4 -lavfi libvmaf -f null -`.
