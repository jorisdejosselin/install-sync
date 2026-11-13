# Renders docs/demo/demo.gif. Run docs/demo/render.sh (needs Docker).
Output docs/demo/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1300
Set Height 760
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "source docs/demo/setup.sh" Enter
Sleep 30s
Show

Type "# A new laptop: clone the manifest and pick its profile" Enter
Sleep 500ms
Type "install-sync init --repo /demo/my-software.git --profile work" Enter
Sleep 2.5s

Type "install-sync profiles" Enter
Sleep 2.5s

Type "# What is missing on this machine?" Enter
Type "install-sync diff --no-untracked" Enter
Sleep 4s
Type "echo $?   # 2 = drift found, for scripts and agents" Enter
Sleep 2.5s

Type "install-sync apply" Enter
Sleep 12s

Type "clear" Enter
Type "# Install a new tool: added to the profile, committed and pushed" Enter
Sleep 500ms
Type "install-sync add jq" Enter
Sleep 9s

Type "git --git-dir /demo/my-software.git log --oneline" Enter
Sleep 3s

Type "# Shared profiles are protected" Enter
Type "install-sync remove curl" Enter
Sleep 3.5s

Type "clear" Enter
Type "# Agents get JSON; everything is installed now" Enter
Type "install-sync diff --json --no-untracked | jq -c '.packages[] | {package, status, manager}'" Enter
Sleep 5s
