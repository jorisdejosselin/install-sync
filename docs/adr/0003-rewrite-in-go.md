# Rewrite in Go as v1

install-sync is the first thing installed on a bare laptop, before brew or Python exist, and the Python version needed a fragile Nuitka/PyInstaller pipeline to ship a 17 MB binary. Since the desired-state model replaces ~90% of the code anyway, v1 is a Go rewrite in the same repo, released as single static binaries via goreleaser; the Python version is tagged `v0` and a one-time `install-sync migrate` converts the old `config.json`.
