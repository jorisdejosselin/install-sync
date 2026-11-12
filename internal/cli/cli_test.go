package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jorisdejosselin/install-sync/internal/pm"
)

// hybrid runs git for real and fakes every package manager.
type hybrid struct {
	real pm.ExecRunner
	fake *pm.FakeRunner
}

func (h hybrid) Capture(ctx context.Context, name string, args ...string) (pm.Result, error) {
	if name == "git" {
		return h.real.Capture(ctx, name, args...)
	}
	return h.fake.Capture(ctx, name, args...)
}
func (h hybrid) Stream(ctx context.Context, name string, args ...string) error {
	return h.fake.Stream(ctx, name, args...)
}
func (h hybrid) LookPath(name string) bool {
	if name == "git" {
		return true
	}
	return h.fake.LookPath(name)
}

type env struct {
	t      *testing.T
	fake   *pm.FakeRunner
	remote string
	root   string
}

func newEnv(t *testing.T) *env {
	t.Helper()
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git not installed")
	}
	root := t.TempDir()
	for k, v := range map[string]string{
		"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
		"GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
		"GIT_CONFIG_GLOBAL": os.DevNull, "GIT_CONFIG_NOSYSTEM": "1",
		"INSTALL_SYNC_CONFIG": filepath.Join(root, "config.yaml"),
		"XDG_DATA_HOME":       filepath.Join(root, "data"),
	} {
		t.Setenv(k, v)
	}
	remote := filepath.Join(root, "remote.git")
	seed := filepath.Join(root, "seed")
	files := map[string]string{
		"packages.yaml": `packages:
  k9s:
    script:
      install: install-k9s
      check: command -v k9s
  iterm2:
    brew: {cask: true}
`,
		"profiles/base-cli.yaml": "packages:\n  - jq\n  - git\n",
		"profiles/personal.yaml": "include: [base-cli]\npackages:\n  - iterm2\n",
		"profiles/work.yaml":     "include: [base-cli]\npackages:\n  - k9s\n",
	}
	for rel, c := range files {
		p := filepath.Join(seed, rel)
		_ = os.MkdirAll(filepath.Dir(p), 0o755)
		_ = os.WriteFile(p, []byte(c), 0o644)
	}
	git := func(dir string, args ...string) {
		cmd := exec.Command("git", args...)
		cmd.Dir = dir
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("git %v: %v\n%s", args, err, out)
		}
	}
	git(root, "init", "-q", "--bare", "-b", "main", remote)
	git(seed, "init", "-q", "-b", "main")
	git(seed, "add", "-A")
	git(seed, "commit", "-qm", "seed")
	git(seed, "push", "-q", remote, "HEAD:main")

	fake := &pm.FakeRunner{
		Paths: map[string]bool{"brew": true, "sh": true},
		Responses: map[string]pm.Result{
			"brew list --formula -1":             {Stdout: "git\nchezmoi\n"},
			"brew list --cask -1":                {Stdout: ""},
			"brew leaves --installed-on-request": {Stdout: "git\nchezmoi\n"},
			"brew info --json=v2 jq":             {Stdout: `{"formulae":[{}],"casks":[]}`},
			"brew info --json=v2 yq":             {Stdout: `{"formulae":[{}],"casks":[]}`},
		},
	}
	return &env{t: t, fake: fake, remote: remote, root: root}
}

func (e *env) run(goos string, interactive bool, args ...string) (int, string, string) {
	var out, errb bytes.Buffer
	d := Deps{
		Stdout: &out, Stderr: &errb, Stdin: strings.NewReader(""),
		Runner: hybrid{fake: e.fake}, GOOS: goos, Managers: pm.New, Interactive: interactive,
	}
	code := Run(args, d, "test")
	return code, out.String(), errb.String()
}

func (e *env) remoteFile(rel string) string {
	out, err := exec.Command("git", "--git-dir", e.remote, "show", "main:"+rel).CombinedOutput()
	if err != nil {
		e.t.Fatalf("git show %s: %v\n%s", rel, err, out)
	}
	return string(out)
}

func TestEndToEnd(t *testing.T) {
	e := newEnv(t)

	code, _, stderr := e.run("darwin", false, "diff")
	if code != ExitFailure || !strings.Contains(stderr, "install-sync init") {
		t.Fatalf("diff before init: %d %s", code, stderr)
	}

	code, _, stderr = e.run("darwin", false, "init", "--repo", e.remote, "--profile", "nope")
	if code != ExitFailure || !strings.Contains(stderr, "available: base-cli, personal, work") {
		t.Fatalf("init unknown profile: %d %s", code, stderr)
	}
	code, _, stderr = e.run("darwin", false, "init", "--repo", e.remote, "--profile", "personal")
	if code != 0 {
		t.Fatalf("init: %d %s", code, stderr)
	}
	if code, _, stderr = e.run("darwin", false, "init", "--repo", e.remote, "--profile", "personal"); code != 0 {
		t.Fatalf("re-running init with the same profile should be a no-op: %s", stderr)
	}
	if code, _, _ = e.run("darwin", false, "init", "--repo", e.remote, "--profile", "work"); code == 0 {
		t.Fatal("switching profile without --force should fail")
	}

	code, stdout, stderr := e.run("darwin", false, "diff", "--json")
	if code != ExitDrift {
		t.Fatalf("diff exit = %d, %s", code, stderr)
	}
	var rep struct {
		Packages  []struct{ Package, Status, Manager string }
		Untracked []struct{ Manager, Name string }
	}
	if err := json.Unmarshal([]byte(stdout), &rep); err != nil {
		t.Fatalf("diff json: %v\n%s", err, stdout)
	}
	states := map[string]string{}
	for _, p := range rep.Packages {
		states[p.Package] = p.Status
	}
	if states["git"] != "ok" || states["jq"] != "missing" || states["iterm2"] != "missing" {
		t.Errorf("states = %v", states)
	}
	if len(rep.Untracked) != 1 || rep.Untracked[0].Name != "chezmoi" {
		t.Errorf("untracked = %+v", rep.Untracked)
	}

	code, stdout, stderr = e.run("darwin", false, "apply")
	if code != 0 || !strings.Contains(stdout, "installed 2") {
		t.Fatalf("apply: %d %s %s", code, stdout, stderr)
	}
	calls := strings.Join(e.fake.Calls, "\n")
	if !strings.Contains(calls, "brew install jq") || !strings.Contains(calls, "brew install --cask iterm2") {
		t.Errorf("apply calls:\n%s", calls)
	}

	// add installs and pushes.
	code, _, stderr = e.run("darwin", false, "add", "yq")
	if code != 0 || !strings.Contains(stderr, "pushed") {
		t.Fatalf("add: %d %s", code, stderr)
	}
	if !strings.Contains(e.remoteFile("profiles/personal.yaml"), "- yq") {
		t.Error("yq not pushed to remote")
	}

	// add with an explicit definition, to a shared profile, without installing.
	code, _, stderr = e.run("darwin", false, "add", "jq", "--to", "base-cli", "--manager", "winget", "--name", "jqlang.jq", "--no-install")
	if code != 0 {
		t.Fatalf("add --manager: %d %s", code, stderr)
	}
	if !strings.Contains(e.remoteFile("packages.yaml"), "winget: jqlang.jq") {
		t.Error("definition not pushed")
	}

	// an unknown package is refused with a hint.
	code, _, stderr = e.run("darwin", false, "add", "nope-xyz")
	if code != ExitFailure || !strings.Contains(stderr, "--manager brew --name") {
		t.Errorf("add unknown: %d %s", code, stderr)
	}

	// remove from an included profile needs --from.
	code, _, stderr = e.run("darwin", false, "remove", "git")
	if code != ExitFailure || !strings.Contains(stderr, "--from base-cli") {
		t.Errorf("remove shared: %d %s", code, stderr)
	}
	e.fake.Responses["brew list --formula -1"] = pm.Result{Stdout: "git\nchezmoi\nyq\n"}
	code, _, stderr = e.run("darwin", false, "remove", "yq")
	if code != 0 || !strings.Contains(strings.Join(e.fake.Calls, "\n"), "brew uninstall yq") {
		t.Errorf("remove yq: %d %s", code, stderr)
	}

	// adopt moves an untracked package in.
	code, _, stderr = e.run("darwin", false, "adopt", "chezmoi")
	if code != 0 || !strings.Contains(e.remoteFile("profiles/personal.yaml"), "- chezmoi") {
		t.Errorf("adopt: %d %s", code, stderr)
	}

	code, stdout, _ = e.run("darwin", false, "profiles", "--json")
	if code != 0 || !strings.Contains(stdout, `"current": true`) {
		t.Errorf("profiles: %d %s", code, stdout)
	}
	code, stdout, _ = e.run("darwin", false, "status")
	if code != 0 || !strings.Contains(stdout, "profile:   personal") {
		t.Errorf("status: %d %s", code, stdout)
	}
	code, stdout, _ = e.run("darwin", false, "validate")
	if code != 0 || !strings.Contains(stdout, "3 profiles") {
		t.Errorf("validate: %d %s", code, stdout)
	}
}

func TestScriptNeedsConfirmationWithoutTTY(t *testing.T) {
	e := newEnv(t)
	e.fake.Responses["sh -c command -v k9s"] = pm.Result{Code: 1}
	if code, _, stderr := e.run("darwin", false, "init", "--repo", e.remote, "--profile", "work"); code != 0 {
		t.Fatalf("init: %s", stderr)
	}
	// Linux-like order on darwin: force script into the order via machine config.
	cfgPath := os.Getenv("INSTALL_SYNC_CONFIG")
	data, _ := os.ReadFile(cfgPath)
	_ = os.WriteFile(cfgPath, append(data, []byte("managers: [brew, script]\n")...), 0o644)

	code, stdout, stderr := e.run("darwin", false, "apply")
	if code != ExitNeedsConfirm || !strings.Contains(stderr, "install-k9s") {
		t.Fatalf("apply without tty: %d %s %s", code, stdout, stderr)
	}
	if strings.Contains(strings.Join(e.fake.Calls, "\n"), "sh -c install-k9s") {
		t.Fatal("script ran without confirmation")
	}
	if code, _, stderr = e.run("darwin", false, "apply", "--yes"); code != 0 {
		t.Fatalf("apply --yes: %d %s", code, stderr)
	}
	if !strings.Contains(strings.Join(e.fake.Calls, "\n"), "sh -c install-k9s") {
		t.Error("script did not run with --yes")
	}
}

func TestInitCreateAndMigrate(t *testing.T) {
	e := newEnv(t)
	code, _, stderr := e.run("windows", false, "init", "--repo", e.remote, "--profile", "work-desktop", "--create", "--include", "base-cli")
	if code != 0 || !strings.Contains(stderr, "created profile work-desktop") {
		t.Fatalf("init --create: %d %s", code, stderr)
	}
	if !strings.Contains(e.remoteFile("profiles/work-desktop.yaml"), "base-cli") {
		t.Error("new profile not pushed")
	}

	old := filepath.Join(e.root, "config.json")
	_ = os.WriteFile(old, []byte(`{"machines":{"x":{"machine_name":"box","os_type":"linux"}},"packages":{"x":[{"name":"jq","package_manager":"apt"}]}}`), 0o644)
	out := filepath.Join(e.root, "migrated")
	code, stdout, stderr := e.run("linux", false, "migrate", old, "--out", out)
	if code != 0 || !strings.Contains(stdout, "profile box-linux: 1 packages") {
		t.Fatalf("migrate: %d %s %s", code, stdout, stderr)
	}
}

func TestInitReusesConfigWrittenByChezmoi(t *testing.T) {
	e := newEnv(t)
	cfgPath := os.Getenv("INSTALL_SYNC_CONFIG")
	manifestDir := filepath.Join(e.root, "data", "install-sync", "manifest")
	_ = os.WriteFile(cfgPath, []byte("profile: personal\nmanifest: "+manifestDir+"\nmanagers: [brew]\n"), 0o644)

	code, _, stderr := e.run("darwin", false, "init", "--repo", e.remote, "--profile", "personal")
	if code != 0 || !strings.Contains(stderr, "keeping the existing machine config") {
		t.Fatalf("init with chezmoi config: %d %s", code, stderr)
	}
	data, _ := os.ReadFile(cfgPath)
	if !strings.Contains(string(data), "managers: [brew]") {
		t.Errorf("config was rewritten:\n%s", data)
	}
	if _, err := os.Stat(filepath.Join(manifestDir, "profiles")); err != nil {
		t.Errorf("manifest not cloned: %v", err)
	}
	code, _, stderr = e.run("darwin", false, "init", "--repo", e.remote, "--profile", "work")
	if code != ExitFailure || !strings.Contains(stderr, "--force") {
		t.Errorf("init with another profile: %d %s", code, stderr)
	}
}
