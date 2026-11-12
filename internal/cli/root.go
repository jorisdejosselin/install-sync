// Package cli wires the install-sync commands.
package cli

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"runtime"
	"strings"

	"github.com/spf13/cobra"
	"golang.org/x/term"

	"github.com/jorisdejosselin/install-sync/internal/engine"
	"github.com/jorisdejosselin/install-sync/internal/gitrepo"
	"github.com/jorisdejosselin/install-sync/internal/machine"
	"github.com/jorisdejosselin/install-sync/internal/manifest"
	"github.com/jorisdejosselin/install-sync/internal/pm"
)

// Exit codes.
const (
	ExitOK           = 0
	ExitFailure      = 1
	ExitDrift        = 2
	ExitNeedsConfirm = 3
)

// ExitError carries a specific exit code.
type ExitError struct {
	Code int
	Err  error
}

func (e *ExitError) Error() string {
	if e.Err == nil {
		return fmt.Sprintf("exit %d", e.Code)
	}
	return e.Err.Error()
}
func (e *ExitError) Unwrap() error { return e.Err }

// silent marks an exit whose reason was already printed.
func silent(code int) error { return &ExitError{Code: code} }

// Deps are the outside world, replaceable in tests.
type Deps struct {
	Stdout   io.Writer
	Stderr   io.Writer
	Stdin    io.Reader
	Runner   pm.Runner
	GOOS     string
	Managers func(pm.Runner, string) map[string]pm.Manager
	// Interactive reports whether a person can answer prompts.
	Interactive bool
}

// DefaultDeps uses the real machine.
func DefaultDeps() Deps {
	return Deps{
		Stdout:      os.Stdout,
		Stderr:      os.Stderr,
		Stdin:       os.Stdin,
		Runner:      pm.ExecRunner{},
		GOOS:        runtime.GOOS,
		Managers:    pm.New,
		Interactive: isTerminal(os.Stdin),
	}
}

// isTerminal reports a real terminal (not /dev/null, a pipe or a file).
func isTerminal(f *os.File) bool { return term.IsTerminal(int(f.Fd())) }

type app struct {
	Deps
	offline bool
	noPush  bool
	in      *bufio.Reader
}

// Run executes the CLI and returns the process exit code.
func Run(args []string, d Deps, version string) int {
	a := &app{Deps: d}
	root := a.rootCmd(version)
	root.SetArgs(args)
	root.SetOut(d.Stdout)
	root.SetErr(d.Stderr)
	err := root.Execute()
	if err == nil {
		return ExitOK
	}
	var ee *ExitError
	if errors.As(err, &ee) {
		if ee.Err != nil {
			fmt.Fprintln(d.Stderr, "error:", ee.Err)
		}
		return ee.Code
	}
	fmt.Fprintln(d.Stderr, "error:", err)
	return ExitFailure
}

func (a *app) rootCmd(version string) *cobra.Command {
	root := &cobra.Command{
		Use:   "install-sync",
		Short: "Keep each machine's software in line with a git-tracked manifest",
		Long: `install-sync applies a desired-state manifest to this machine.

The manifest is a git repo with a catalog (packages.yaml) and profiles
(profiles/*.yaml). Each machine applies one profile, set in its machine config
(~/.config/install-sync/config.yaml). install-sync pulls before and commits and
pushes after every change, so you never have to touch the manifest repo.

Exit codes: 0 ok, 1 error, 2 drift found (diff), 3 needs confirmation.`,
		Version:       version,
		SilenceUsage:  true,
		SilenceErrors: true,
	}
	root.PersistentFlags().BoolVar(&a.offline, "offline", false, "do not pull or push the manifest repo")
	root.PersistentFlags().BoolVar(&a.noPush, "no-push", false, "commit changes but do not push them")
	root.AddCommand(
		a.initCmd(), a.applyCmd(), a.diffCmd(), a.addCmd(), a.removeCmd(),
		a.adoptCmd(), a.upgradeCmd(), a.statusCmd(), a.profilesCmd(),
		a.validateCmd(), a.migrateCmd(),
	)
	return root
}

func (a *app) logf(format string, args ...interface{}) {
	fmt.Fprintf(a.Stderr, format+"\n", args...)
}

func (a *app) printJSON(v interface{}) error {
	enc := json.NewEncoder(a.Stdout)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}

// confirm asks a yes/no question, or returns nil when nobody can answer.
func (a *app) confirmer() func(string) bool {
	if !a.Interactive {
		return nil
	}
	return func(prompt string) bool {
		if a.in == nil {
			a.in = bufio.NewReader(a.Stdin)
		}
		fmt.Fprint(a.Stderr, prompt, "[y/N] ")
		line, _ := a.in.ReadString('\n')
		line = strings.ToLower(strings.TrimSpace(line))
		return line == "y" || line == "yes"
	}
}

// session is everything a command needs once the machine is initialised.
type session struct {
	cfg  *machine.Config
	repo gitrepo.Repo
	m    *manifest.Manifest
	eng  *engine.Engine
}

func (a *app) open(ctx context.Context, pull bool) (*session, error) {
	cfg, _, err := machine.Load()
	if err != nil {
		return nil, err
	}
	repo := gitrepo.Repo{Dir: cfg.Manifest, R: a.Runner}
	if pull && !a.offline && repo.IsRepo(ctx) {
		if _, err := repo.Pull(ctx); err != nil {
			a.logf("! could not pull the manifest (continuing with the local copy): %v", err)
		}
	}
	m, err := manifest.Load(cfg.Manifest)
	if err != nil {
		return nil, err
	}
	if _, ok := m.Profiles[cfg.Profile]; !ok {
		return nil, fmt.Errorf("this machine applies profile %q, which is not in the manifest (available: %s)",
			cfg.Profile, strings.Join(m.ProfileNames(), ", "))
	}
	eng := engine.New(m, cfg.Profile, cfg.Order(a.GOOS), a.Managers(a.Runner, a.GOOS), a.Stderr)
	return &session{cfg: cfg, repo: repo, m: m, eng: eng}, nil
}

// commit records manifest changes and pushes them unless disabled.
func (a *app) commit(ctx context.Context, s *session, msg string) {
	if !s.repo.IsRepo(ctx) {
		a.logf("! %s is not a git repo; the change was saved but not committed", s.cfg.Manifest)
		return
	}
	committed, err := s.repo.Commit(ctx, msg)
	if err != nil {
		a.logf("! could not commit the manifest change: %v", err)
		return
	}
	if !committed {
		return
	}
	a.logf("✓ committed: %s", msg)
	if a.offline || a.noPush || !s.cfg.PushEnabled() {
		a.logf("  not pushed; run `install-sync status` to see unpushed changes")
		return
	}
	if err := s.repo.Push(ctx); err != nil {
		a.logf("! push failed (the commit is kept locally): %v", err)
		a.logf("  run `install-sync status` for details")
		return
	}
	a.logf("✓ pushed")
}
