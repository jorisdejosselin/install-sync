# install-sync owns git for the manifest repo

The main users are AI agents running `install-sync add <pkg>` on many machines, and they should not need to know where the manifest repo lives or how to sync it. So install-sync pulls before every operation and commits and pushes after every change, by default, for its own dedicated manifest repo. Repo creation via provider APIs, tokens and remote-URL rewriting are dropped: the repo is created once by hand and `init --repo <url>` clones it.
