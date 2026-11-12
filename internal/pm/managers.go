package pm

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"

	"github.com/jorisdejosselin/install-sync/internal/manifest"
)

// ---- brew ----

type brew struct{ r Runner }

func (b *brew) Name() string  { return manifest.Brew }
func (b *brew) Usable() bool  { return b.r.LookPath("brew") }
func (b *brew) Implied() bool { return true }

// Key compares tapped formulae (owner/tap/name) by their short name.
func (b *brew) Key(n string) string { return lowerKey(path.Base(n)) }

func (b *brew) Installed(ctx context.Context) (Set, error) {
	f, err := captureOK(ctx, b.r, "brew", "list", "--formula", "-1")
	if err != nil {
		return nil, err
	}
	c, err := captureOK(ctx, b.r, "brew", "list", "--cask", "-1")
	if err != nil {
		return nil, err
	}
	return setFrom(append(lines(f.Stdout), lines(c.Stdout)...), b.Key), nil
}

func (b *brew) Manual(ctx context.Context) ([]string, bool, error) {
	f, err := captureOK(ctx, b.r, "brew", "leaves", "--installed-on-request")
	if err != nil {
		return nil, true, err
	}
	c, err := captureOK(ctx, b.r, "brew", "list", "--cask", "-1")
	if err != nil {
		return nil, true, err
	}
	return append(lines(f.Stdout), lines(c.Stdout)...), true, nil
}

// Probe finds the package in brew and resolves aliases to the real name
// (`kubectl` is the formula `kubernetes-cli`), so installed checks match.
func (b *brew) Probe(ctx context.Context, e manifest.Entry) (manifest.Entry, bool, error) {
	res, err := b.r.Capture(ctx, "brew", "info", "--json=v2", e.Name)
	if err != nil || !res.OK() {
		return e, false, err
	}
	var info struct {
		Formulae []struct {
			FullName string `json:"full_name"`
		} `json:"formulae"`
		Casks []struct {
			FullToken string `json:"full_token"`
		} `json:"casks"`
	}
	if err := json.Unmarshal([]byte(res.Stdout), &info); err != nil {
		return e, false, fmt.Errorf("brew info %s: %w", e.Name, err)
	}
	switch {
	case len(info.Formulae) > 0:
		if n := info.Formulae[0].FullName; n != "" {
			e.Name = n
		}
		return e, true, nil
	case len(info.Casks) > 0:
		e.Cask = true
		if n := info.Casks[0].FullToken; n != "" {
			e.Name = n
		}
		return e, true, nil
	}
	return e, false, nil
}

func (b *brew) IsInstalled(_ context.Context, e manifest.Entry, s Set) (bool, error) {
	return s[b.Key(e.Name)], nil
}

func (b *brew) Install(ctx context.Context, e manifest.Entry) error {
	if e.Cask {
		return b.r.Stream(ctx, "brew", "install", "--cask", e.Name)
	}
	return b.r.Stream(ctx, "brew", "install", e.Name)
}

func (b *brew) Uninstall(ctx context.Context, e manifest.Entry) error {
	if e.Cask {
		return b.r.Stream(ctx, "brew", "uninstall", "--cask", e.Name)
	}
	return b.r.Stream(ctx, "brew", "uninstall", e.Name)
}

func (b *brew) Upgrade(ctx context.Context, es []manifest.Entry) error {
	var formulae, casks []string
	for _, e := range es {
		if e.Cask {
			casks = append(casks, e.Name)
		} else {
			formulae = append(formulae, e.Name)
		}
	}
	var errs []error
	if len(formulae) > 0 {
		errs = append(errs, b.r.Stream(ctx, "brew", append([]string{"upgrade", "--formula"}, formulae...)...))
	}
	if len(casks) > 0 {
		errs = append(errs, b.r.Stream(ctx, "brew", append([]string{"upgrade", "--cask"}, casks...)...))
	}
	return errors.Join(errs...)
}

// ---- apt ----

type apt struct {
	r        Runner
	updated  bool
	listsDir string // for tests; default /var/lib/apt/lists
}

func (a *apt) Name() string        { return manifest.Apt }
func (a *apt) Usable() bool        { return a.r.LookPath("apt-get") && a.r.LookPath("dpkg-query") }
func (a *apt) Implied() bool       { return true }
func (a *apt) Key(n string) string { return lowerKey(n) }

func (a *apt) Installed(ctx context.Context) (Set, error) {
	res, err := captureOK(ctx, a.r, "dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\n")
	if err != nil {
		return nil, err
	}
	s := Set{}
	for _, l := range lines(res.Stdout) {
		parts := strings.SplitN(l, "\t", 2)
		if len(parts) == 2 && strings.HasPrefix(parts[1], "ii") {
			s[a.Key(parts[0])] = true
		}
	}
	return s, nil
}

// Manual lists the "leaves" among manually installed packages: those no other
// installed package depends on or recommends, and that are not part of the
// base system (Essential, or priority required/important). Base images and WSL
// mark hundreds of libraries as manual; this keeps only what was chosen.
func (a *apt) Manual(ctx context.Context) ([]string, bool, error) {
	res, err := captureOK(ctx, a.r, "apt-mark", "showmanual")
	if err != nil {
		return nil, true, err
	}
	info, err := captureOK(ctx, a.r, "dpkg-query", "-W",
		"-f=${Package}\t${db:Status-Abbrev}\t${Priority}\t${Essential}\t${Depends}, ${Pre-Depends}, ${Recommends}\n")
	if err != nil {
		return nil, true, err
	}
	base, needed := map[string]bool{}, map[string]bool{}
	for _, l := range lines(info.Stdout) {
		f := strings.SplitN(l, "\t", 5)
		if len(f) < 5 || !strings.HasPrefix(f[1], "ii") {
			continue
		}
		if f[3] == "yes" || f[2] == "required" || f[2] == "important" {
			base[f[0]] = true
		}
		for _, dep := range strings.FieldsFunc(f[4], func(r rune) bool { return r == ',' || r == '|' }) {
			name := strings.TrimSpace(dep)
			if i := strings.IndexAny(name, " (:"); i >= 0 {
				name = name[:i]
			}
			if name != "" {
				needed[name] = true
			}
		}
	}
	var out []string
	for _, n := range lines(res.Stdout) {
		if !base[n] && !needed[n] {
			out = append(out, n)
		}
	}
	return out, true, nil
}

// ErrAptListsEmpty means apt has never fetched package lists on this machine.
var ErrAptListsEmpty = errors.New("apt package lists are empty; `install-sync apply` (or `sudo apt-get update`) fetches them")

func (a *apt) listsEmpty() bool {
	dir := a.listsDir
	if dir == "" {
		dir = "/var/lib/apt/lists"
	}
	matches, _ := filepath.Glob(filepath.Join(dir, "*_Packages*"))
	return len(matches) == 0
}

// Refresh runs `apt-get update` once per session, before probing for installs.
func (a *apt) Refresh(ctx context.Context) error {
	if a.updated {
		return nil
	}
	name, args := sudo("apt-get", "update")
	if err := a.r.Stream(ctx, name, args...); err != nil {
		return err
	}
	a.updated = true
	return nil
}

func (a *apt) Probe(ctx context.Context, e manifest.Entry) (manifest.Entry, bool, error) {
	res, err := a.r.Capture(ctx, "apt-cache", "show", e.Name)
	if err != nil {
		return e, false, err
	}
	found := res.OK() && strings.TrimSpace(res.Stdout) != ""
	if !found && !a.updated && a.listsEmpty() {
		return e, false, ErrAptListsEmpty
	}
	return e, found, nil
}

func (a *apt) IsInstalled(_ context.Context, e manifest.Entry, s Set) (bool, error) {
	return s[a.Key(e.Name)], nil
}

func (a *apt) Install(ctx context.Context, e manifest.Entry) error {
	if e.Repo != nil {
		if err := a.setupRepo(ctx, e); err != nil {
			return err
		}
	}
	if err := a.Refresh(ctx); err != nil {
		return err
	}
	name, args := sudo("apt-get", "install", "-y", e.Name)
	return a.r.Stream(ctx, name, args...)
}

// setupRepo adds the entry's apt repository once.
func (a *apt) setupRepo(ctx context.Context, e manifest.Entry) error {
	list := "/etc/apt/sources.list.d/install-sync-" + e.Name + ".list"
	if _, err := os.Stat(list); err == nil {
		return nil
	}
	// A bare system may lack the tools needed to fetch and convert the key.
	if !a.r.LookPath("curl") || !a.r.LookPath("gpg") {
		if err := a.Refresh(ctx); err != nil {
			return err
		}
		name, args := sudo("apt-get", "install", "-y", "curl", "gpg", "ca-certificates")
		if err := a.r.Stream(ctx, name, args...); err != nil {
			return err
		}
	}
	keyring := "/usr/share/keyrings/install-sync-" + e.Name + ".gpg"
	arch, err := captureOK(ctx, a.r, "dpkg", "--print-architecture")
	if err != nil {
		return err
	}
	source := strings.NewReplacer(
		"{arch}", strings.TrimSpace(arch.Stdout),
		"{codename}", osCodename(),
		"{keyring}", keyring,
	).Replace(e.Repo.Source)

	fetch := "curl -fsSL " + shellQuote(e.Repo.Key)
	if !strings.HasSuffix(e.Repo.Key, ".gpg") {
		fetch += " | gpg --dearmor"
	}
	script := fmt.Sprintf("set -e; %s > %s; printf '%%s\\n' %s > %s",
		fetch, shellQuote(keyring), shellQuote(source), shellQuote(list))
	name, args := sudo("sh", "-c", script)
	if err := a.r.Stream(ctx, name, args...); err != nil {
		return err
	}
	a.updated = false
	return nil
}

func (a *apt) Uninstall(ctx context.Context, e manifest.Entry) error {
	name, args := sudo("apt-get", "remove", "-y", e.Name)
	return a.r.Stream(ctx, name, args...)
}

func (a *apt) Upgrade(ctx context.Context, es []manifest.Entry) error {
	name, args := sudo("apt-get", "update")
	if err := a.r.Stream(ctx, name, args...); err != nil {
		return err
	}
	pkgs := []string{"apt-get", "install", "--only-upgrade", "-y"}
	for _, e := range es {
		pkgs = append(pkgs, e.Name)
	}
	name, args = sudo(pkgs...)
	return a.r.Stream(ctx, name, args...)
}

func osCodename() string {
	data, err := os.ReadFile("/etc/os-release")
	if err != nil {
		return ""
	}
	for _, l := range strings.Split(string(data), "\n") {
		if v, ok := strings.CutPrefix(l, "VERSION_CODENAME="); ok {
			return strings.Trim(v, `"`)
		}
	}
	return ""
}

func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", `'\''`) + "'" }

// ---- winget ----

type winget struct{ r Runner }

func (w *winget) Name() string        { return manifest.Winget }
func (w *winget) Usable() bool        { return w.r.LookPath("winget") }
func (w *winget) Implied() bool       { return true }
func (w *winget) Key(n string) string { return lowerKey(n) }

var wingetAgree = []string{"--accept-source-agreements"}

func (w *winget) Installed(ctx context.Context) (Set, error) {
	ids, err := w.export(ctx)
	if err != nil {
		return nil, err
	}
	return setFrom(ids, w.Key), nil
}

func (w *winget) export(ctx context.Context) ([]string, error) {
	f, err := os.CreateTemp("", "install-sync-winget-*.json")
	if err != nil {
		return nil, err
	}
	name := f.Name()
	_ = f.Close()
	defer os.Remove(name)
	if _, err := captureOK(ctx, w.r, "winget", append([]string{"export", "-o", name}, wingetAgree...)...); err != nil {
		return nil, err
	}
	data, err := os.ReadFile(name)
	if err != nil {
		return nil, err
	}
	var exp struct {
		Sources []struct {
			Packages []struct {
				PackageIdentifier string `json:"PackageIdentifier"`
			} `json:"Packages"`
		} `json:"Sources"`
	}
	if err := json.Unmarshal(data, &exp); err != nil {
		return nil, fmt.Errorf("winget export: %w", err)
	}
	var ids []string
	for _, s := range exp.Sources {
		for _, p := range s.Packages {
			ids = append(ids, p.PackageIdentifier)
		}
	}
	return ids, nil
}

func (w *winget) Manual(ctx context.Context) ([]string, bool, error) {
	ids, err := w.export(ctx)
	return ids, true, err
}

func (w *winget) Probe(ctx context.Context, e manifest.Entry) (manifest.Entry, bool, error) {
	res, err := w.r.Capture(ctx, "winget", append([]string{"show", "--id", e.Name, "--exact"}, wingetAgree...)...)
	if err != nil {
		return e, false, err
	}
	return e, res.OK(), nil
}

func (w *winget) IsInstalled(_ context.Context, e manifest.Entry, s Set) (bool, error) {
	return s[w.Key(e.Name)], nil
}

func (w *winget) Install(ctx context.Context, e manifest.Entry) error {
	return w.r.Stream(ctx, "winget", "install", "--id", e.Name, "--exact", "--silent",
		"--accept-package-agreements", "--accept-source-agreements")
}

func (w *winget) Uninstall(ctx context.Context, e manifest.Entry) error {
	return w.r.Stream(ctx, "winget", "uninstall", "--id", e.Name, "--exact", "--silent")
}

// wingetNoUpgrade is APPINSTALLER_CLI_ERROR_UPDATE_NOT_APPLICABLE.
const wingetNoUpgrade = 0x8A15002B

func (w *winget) Upgrade(ctx context.Context, es []manifest.Entry) error {
	var errs []error
	for _, e := range es {
		err := w.r.Stream(ctx, "winget", "upgrade", "--id", e.Name, "--exact", "--silent",
			"--accept-package-agreements", "--accept-source-agreements")
		var ee *exec.ExitError
		if errors.As(err, &ee) && uint32(ee.ExitCode()) == wingetNoUpgrade {
			continue
		}
		errs = append(errs, err)
	}
	return errors.Join(errs...)
}

// ---- snap ----

type snap struct{ r Runner }

func (s *snap) Name() string        { return manifest.Snap }
func (s *snap) Usable() bool        { return s.r.LookPath("snap") }
func (s *snap) Implied() bool       { return true }
func (s *snap) Key(n string) string { return lowerKey(n) }

func (s *snap) list(ctx context.Context) ([]string, error) {
	res, err := captureOK(ctx, s.r, "snap", "list")
	if err != nil {
		return nil, err
	}
	var names []string
	for i, l := range lines(res.Stdout) {
		if i == 0 {
			continue // header
		}
		names = append(names, strings.Fields(l)[0])
	}
	return names, nil
}

func (s *snap) Installed(ctx context.Context) (Set, error) {
	names, err := s.list(ctx)
	if err != nil {
		return nil, err
	}
	return setFrom(names, s.Key), nil
}

func (s *snap) Manual(ctx context.Context) ([]string, bool, error) {
	names, err := s.list(ctx)
	if err != nil {
		return nil, true, err
	}
	var out []string
	for _, n := range names {
		if isSystemSnap(n) {
			continue
		}
		out = append(out, n)
	}
	return out, true, nil
}

func isSystemSnap(n string) bool {
	if n == "snapd" || n == "bare" || n == "gtk-common-themes" {
		return true
	}
	for _, p := range []string{"core", "gnome-", "kde-frameworks-", "mesa-"} {
		if strings.HasPrefix(n, p) {
			return true
		}
	}
	return false
}

func (s *snap) Probe(ctx context.Context, e manifest.Entry) (manifest.Entry, bool, error) {
	res, err := s.r.Capture(ctx, "snap", "info", e.Name)
	if err != nil {
		return e, false, err
	}
	if res.OK() && strings.Contains(res.Stdout, "classic") {
		e.Classic = true
	}
	return e, res.OK(), nil
}

func (s *snap) IsInstalled(_ context.Context, e manifest.Entry, set Set) (bool, error) {
	return set[s.Key(e.Name)], nil
}

func (s *snap) Install(ctx context.Context, e manifest.Entry) error {
	args := []string{"snap", "install", e.Name}
	if e.Classic {
		args = append(args, "--classic")
	}
	name, a := sudo(args...)
	return s.r.Stream(ctx, name, a...)
}

func (s *snap) Uninstall(ctx context.Context, e manifest.Entry) error {
	name, a := sudo("snap", "remove", e.Name)
	return s.r.Stream(ctx, name, a...)
}

func (s *snap) Upgrade(ctx context.Context, es []manifest.Entry) error {
	args := []string{"snap", "refresh"}
	for _, e := range es {
		args = append(args, e.Name)
	}
	name, a := sudo(args...)
	return s.r.Stream(ctx, name, a...)
}

// ---- npm ----

type npm struct {
	r       Runner
	windows bool
}

func (n *npm) Name() string { return manifest.Npm }
func (n *npm) bin() string {
	if n.windows {
		return "npm.cmd"
	}
	return "npm"
}
func (n *npm) Usable() bool           { return n.r.LookPath(n.bin()) }
func (n *npm) Implied() bool          { return false }
func (n *npm) Key(name string) string { return lowerKey(name) }

func (n *npm) global(ctx context.Context) ([]string, error) {
	res, err := n.r.Capture(ctx, n.bin(), "ls", "-g", "--depth=0", "--json")
	if err != nil {
		return nil, err
	}
	var out struct {
		Dependencies map[string]json.RawMessage `json:"dependencies"`
	}
	if err := json.Unmarshal([]byte(res.Stdout), &out); err != nil {
		return nil, fmt.Errorf("npm ls -g: %w", err)
	}
	names := make([]string, 0, len(out.Dependencies))
	for k := range out.Dependencies {
		names = append(names, k)
	}
	return names, nil
}

func (n *npm) Installed(ctx context.Context) (Set, error) {
	names, err := n.global(ctx)
	if err != nil {
		return nil, err
	}
	return setFrom(names, n.Key), nil
}

func (n *npm) Manual(ctx context.Context) ([]string, bool, error) {
	names, err := n.global(ctx)
	var out []string
	for _, x := range names {
		if x != "npm" && x != "corepack" {
			out = append(out, x)
		}
	}
	return out, true, err
}

func (n *npm) Probe(_ context.Context, e manifest.Entry) (manifest.Entry, bool, error) {
	return e, false, nil
}

func (n *npm) IsInstalled(_ context.Context, e manifest.Entry, s Set) (bool, error) {
	return s[n.Key(e.Name)], nil
}

func (n *npm) Install(ctx context.Context, e manifest.Entry) error {
	return n.r.Stream(ctx, n.bin(), "install", "-g", e.Name)
}

func (n *npm) Uninstall(ctx context.Context, e manifest.Entry) error {
	return n.r.Stream(ctx, n.bin(), "uninstall", "-g", e.Name)
}

func (n *npm) Upgrade(ctx context.Context, es []manifest.Entry) error {
	args := []string{"install", "-g"}
	for _, e := range es {
		args = append(args, e.Name+"@latest")
	}
	return n.r.Stream(ctx, n.bin(), args...)
}

// ---- script ----

type script struct {
	r       Runner
	windows bool
}

func (s *script) Name() string { return manifest.Script }
func (s *script) shell() (string, []string) {
	if s.windows {
		return "powershell", []string{"-NoProfile", "-NonInteractive", "-Command"}
	}
	return "sh", []string{"-c"}
}
func (s *script) Usable() bool {
	sh, _ := s.shell()
	return s.r.LookPath(sh)
}
func (s *script) Implied() bool                                  { return false }
func (s *script) Key(n string) string                            { return lowerKey(n) }
func (s *script) Installed(context.Context) (Set, error)         { return Set{}, nil }
func (s *script) Manual(context.Context) ([]string, bool, error) { return nil, false, nil }
func (s *script) Probe(_ context.Context, e manifest.Entry) (manifest.Entry, bool, error) {
	return e, false, nil
}

func (s *script) IsInstalled(ctx context.Context, e manifest.Entry, _ Set) (bool, error) {
	sh, args := s.shell()
	res, err := s.r.Capture(ctx, sh, append(args, e.Check)...)
	if err != nil {
		return false, err
	}
	return res.OK(), nil
}

func (s *script) run(ctx context.Context, cmd string) error {
	sh, args := s.shell()
	if err := s.r.Stream(ctx, sh, append(args, cmd)...); err != nil {
		var ce *CommandError
		if errors.As(err, &ce) {
			return fmt.Errorf("script failed (%w); see its output above", ce.Err)
		}
		return err
	}
	return nil
}

func (s *script) Install(ctx context.Context, e manifest.Entry) error { return s.run(ctx, e.Install) }

func (s *script) Uninstall(ctx context.Context, e manifest.Entry) error {
	if e.Uninstall == "" {
		return errors.New("this script package has no uninstall command; remove it by hand")
	}
	return s.run(ctx, e.Uninstall)
}

func (s *script) Upgrade(ctx context.Context, es []manifest.Entry) error {
	var errs []error
	for _, e := range es {
		if e.Upgrade != "" {
			errs = append(errs, s.run(ctx, e.Upgrade))
		}
	}
	return errors.Join(errs...)
}
