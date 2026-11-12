package pm

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/jorisdejosselin/install-sync/internal/manifest"
)

// Set is a set of installed package keys (see Manager.Key).
type Set map[string]bool

// Manager is one package manager on this machine.
type Manager interface {
	Name() string
	// Usable reports whether the package manager exists on this machine.
	Usable() bool
	// Implied reports whether packages without an explicit entry may be
	// tried with this manager under their own name.
	Implied() bool
	// Key normalises a native name for comparisons.
	Key(native string) string
	// Installed lists what is installed (as keys).
	Installed(ctx context.Context) (Set, error)
	// Manual lists what the user installed on purpose, for untracked
	// detection. ok is false when the manager cannot tell.
	Manual(ctx context.Context) (names []string, ok bool, err error)
	// Probe checks an implied entry exists in the manager's repositories. It
	// may enrich the entry (e.g. mark a brew cask).
	Probe(ctx context.Context, e manifest.Entry) (manifest.Entry, bool, error)
	// IsInstalled checks one entry against the installed set.
	IsInstalled(ctx context.Context, e manifest.Entry, installed Set) (bool, error)
	Install(ctx context.Context, e manifest.Entry) error
	Uninstall(ctx context.Context, e manifest.Entry) error
	Upgrade(ctx context.Context, es []manifest.Entry) error
}

// Refresher is implemented by managers whose package index must be updated
// before installing (apt). Engines call Refresh before apply and add.
type Refresher interface {
	Refresh(ctx context.Context) error
}

// New returns all package managers known for goos, by name.
func New(r Runner, goos string) map[string]Manager {
	return map[string]Manager{
		manifest.Brew:   &brew{r: r},
		manifest.Apt:    &apt{r: r},
		manifest.Winget: &winget{r: r},
		manifest.Snap:   &snap{r: r},
		manifest.Npm:    &npm{r: r, windows: goos == "windows"},
		manifest.Script: &script{r: r, windows: goos == "windows"},
	}
}

func lowerKey(s string) string { return strings.ToLower(strings.TrimSpace(s)) }

func sudo(args ...string) (string, []string) {
	if os.Geteuid() == 0 {
		return args[0], args[1:]
	}
	return "sudo", args
}

func setFrom(keys []string, key func(string) string) Set {
	s := Set{}
	for _, k := range keys {
		s[key(k)] = true
	}
	return s
}

func captureOK(ctx context.Context, r Runner, name string, args ...string) (Result, error) {
	res, err := r.Capture(ctx, name, args...)
	if err != nil {
		return res, err
	}
	if !res.OK() {
		return res, fmt.Errorf("%s %s: exit %d: %s", name, strings.Join(args, " "), res.Code, strings.TrimSpace(res.Stderr))
	}
	return res, nil
}
