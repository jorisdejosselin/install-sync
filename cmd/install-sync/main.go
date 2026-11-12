// Command install-sync keeps each machine's software in line with a
// git-tracked desired-state manifest.
package main

import (
	"os"

	"github.com/jorisdejosselin/install-sync/internal/cli"
)

// version is set by the release build (-ldflags "-X main.version=...").
var version = "dev"

func main() {
	os.Exit(cli.Run(os.Args[1:], cli.DefaultDeps(), version))
}
