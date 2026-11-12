package engine

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jorisdejosselin/install-sync/internal/manifest"
	"github.com/jorisdejosselin/install-sync/internal/pm"
)

var ctx = context.Background()

// fakeMgr is an in-memory package manager.
type fakeMgr struct {
	name      string
	usable    bool
	implied   bool
	installed map[string]bool
	manual    []string
	repo      map[string]bool // what Probe finds
	noManual  bool
	log       *[]string
	failOn    string
	aliases   map[string]string
}

func (f *fakeMgr) Name() string        { return f.name }
func (f *fakeMgr) Usable() bool        { return f.usable }
func (f *fakeMgr) Implied() bool       { return f.implied }
func (f *fakeMgr) Key(n string) string { return strings.ToLower(n) }
func (f *fakeMgr) Installed(context.Context) (pm.Set, error) {
	s := pm.Set{}
	for k := range f.installed {
		s[f.Key(k)] = true
	}
	return s, nil
}
func (f *fakeMgr) Manual(context.Context) ([]string, bool, error) {
	if f.noManual {
		return nil, false, nil
	}
	return f.manual, true, nil
}
func (f *fakeMgr) Probe(_ context.Context, e manifest.Entry) (manifest.Entry, bool, error) {
	if alias, ok := f.aliases[e.Name]; ok {
		e.Name = alias
		return e, true, nil
	}
	return e, f.repo[e.Name], nil
}
func (f *fakeMgr) IsInstalled(_ context.Context, e manifest.Entry, s pm.Set) (bool, error) {
	if f.name == manifest.Script {
		return f.installed[e.Check], nil
	}
	return s[f.Key(e.Name)], nil
}
func (f *fakeMgr) Install(_ context.Context, e manifest.Entry) error {
	*f.log = append(*f.log, f.name+" install "+e.Name)
	if e.Name == f.failOn {
		return errors.New("boom")
	}
	f.installed[e.Name] = true
	return nil
}
func (f *fakeMgr) Uninstall(_ context.Context, e manifest.Entry) error {
	*f.log = append(*f.log, f.name+" uninstall "+e.Name)
	delete(f.installed, e.Name)
	return nil
}
func (f *fakeMgr) Upgrade(_ context.Context, es []manifest.Entry) error {
	for _, e := range es {
		*f.log = append(*f.log, f.name+" upgrade "+e.Name)
	}
	return nil
}

func setup(t *testing.T, profile string) (*Engine, map[string]*fakeMgr, *[]string) {
	t.Helper()
	dir := t.TempDir()
	files := map[string]string{
		manifest.CatalogFile: `packages:
  jq:
    winget: jqlang.jq
  kubectl:
    snap: {classic: true}
  k9s:
    script:
      install: install-k9s
      check: check-k9s
  md-to-pdf:
    npm: md-to-pdf
    requires:
      apt: [libnss3, libgbm1]
  iterm2:
    brew: {cask: true}
`,
		"profiles/base.yaml": "packages: [jq, curl, iterm2]\n",
		"profiles/work.yaml": "include: [base]\npackages: [kubectl, k9s, md-to-pdf, nothing-has-this]\n",
	}
	for rel, c := range files {
		p := filepath.Join(dir, rel)
		_ = os.MkdirAll(filepath.Dir(p), 0o755)
		if err := os.WriteFile(p, []byte(c), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	m, err := manifest.Load(dir)
	if err != nil {
		t.Fatal(err)
	}
	var log []string
	mgrs := map[string]*fakeMgr{
		"apt":    {name: "apt", usable: true, implied: true, installed: map[string]bool{"curl": true, "libnss3": true, "bash": true}, manual: []string{"curl", "bash", "libnss3"}, repo: map[string]bool{"jq": true}, log: &log},
		"snap":   {name: "snap", usable: true, implied: true, installed: map[string]bool{}, repo: map[string]bool{"kubectl": true}, log: &log},
		"script": {name: "script", usable: true, installed: map[string]bool{}, noManual: true, log: &log},
		"npm":    {name: "npm", usable: true, installed: map[string]bool{}, log: &log},
		"brew":   {name: "brew", usable: false, implied: true, installed: map[string]bool{}, log: &log},
		"winget": {name: "winget", usable: false, implied: true, installed: map[string]bool{}, log: &log},
	}
	all := map[string]pm.Manager{}
	for k, v := range mgrs {
		all[k] = v
	}
	return New(m, profile, []string{"apt", "snap", "script", "npm"}, all, nil), mgrs, &log
}

func byPkg(rep *Report) map[string]PackageState {
	out := map[string]PackageState{}
	for _, p := range rep.Packages {
		out[p.Package] = p
	}
	return out
}

func TestDiff(t *testing.T) {
	e, _, _ := setup(t, "work")
	rep, err := e.Diff(ctx, true)
	if err != nil {
		t.Fatal(err)
	}
	got := byPkg(rep)
	checks := map[string]string{
		"jq":               "missing apt jq", // implied apt found by probe; winget not usable
		"curl":             "ok apt curl",
		"iterm2":           "unavailable  ", // brew only, brew not usable
		"kubectl":          "missing snap kubectl",
		"k9s":              "missing script k9s",
		"md-to-pdf":        "missing npm md-to-pdf",
		"nothing-has-this": "unavailable  ",
	}
	for pkg, want := range checks {
		p := got[pkg]
		if s := p.Status + " " + p.Manager + " " + p.Name; s != want {
			t.Errorf("%s = %q, want %q", pkg, s, want)
		}
	}
	if !got["kubectl"].entry.Classic {
		t.Error("kubectl entry should keep classic from the catalog")
	}
	// bash is untracked; curl is in the profile; libnss3 is a requirement.
	if len(rep.Untracked) != 1 || rep.Untracked[0].Name != "bash" {
		t.Errorf("untracked = %+v", rep.Untracked)
	}
	if strings.Join(rep.NoUntracked, ",") != "script" {
		t.Errorf("no-untracked = %v", rep.NoUntracked)
	}
	if !rep.Drift() {
		t.Error("expected drift")
	}
}

func TestInstallRequiresAndScripts(t *testing.T) {
	e, _, log := setup(t, "work")
	rep, _ := e.Diff(ctx, false)
	got := byPkg(rep)

	if err := e.Install(ctx, got["md-to-pdf"], InstallOpts{}); err != nil {
		t.Fatal(err)
	}
	if strings.Join(*log, ";") != "apt install libgbm1;npm install md-to-pdf" {
		t.Errorf("log = %v (libnss3 is already installed)", *log)
	}

	*log = nil
	if err := e.Install(ctx, got["k9s"], InstallOpts{}); !errors.Is(err, ErrNeedsConfirmation) {
		t.Errorf("script without confirmation: err = %v", err)
	}
	if err := e.Install(ctx, got["k9s"], InstallOpts{Confirm: func(string) bool { return false }}); !errors.Is(err, ErrNeedsConfirmation) {
		t.Errorf("declined script: err = %v", err)
	}
	if len(*log) != 0 {
		t.Errorf("script ran without confirmation: %v", *log)
	}
	asked := ""
	if err := e.Install(ctx, got["k9s"], InstallOpts{Confirm: func(p string) bool { asked = p; return true }}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(asked, "install-k9s") {
		t.Errorf("prompt should show the command, got %q", asked)
	}
	if err := e.Install(ctx, got["kubectl"], InstallOpts{DryRun: true}); err != nil {
		t.Fatal(err)
	}
	if strings.Join(*log, ";") != "script install k9s" {
		t.Errorf("log = %v (dry run must not install)", *log)
	}
}

func TestUninstallAndUpgrade(t *testing.T) {
	e, mgrs, log := setup(t, "work")
	mgrs["snap"].installed["kubectl"] = true
	rep, _ := e.Diff(ctx, false)
	got := byPkg(rep)
	if err := e.Uninstall(ctx, got["kubectl"]); err != nil {
		t.Fatal(err)
	}
	if err := e.Upgrade(ctx, rep, map[string]bool{"curl": true}); err != nil {
		t.Fatal(err)
	}
	if strings.Join(*log, ";") != "snap uninstall kubectl;apt upgrade curl" {
		t.Errorf("log = %v", *log)
	}
}

func TestManagerOrder(t *testing.T) {
	e, mgrs, _ := setup(t, "base")
	mgrs["snap"].repo["jq"] = true
	e.Order = []string{"snap", "apt"}
	if st := e.State(ctx, "jq"); st.Manager != "snap" {
		t.Errorf("jq with snap first = %+v", st)
	}
	mgrs["apt"].installed["jq"] = true
	e.installed = nil
	if st := e.State(ctx, "jq"); st.Status != StatusOK || st.Manager != "apt" {
		t.Errorf("installed via a later manager should still be ok: %+v", st)
	}
}

func TestAdoptName(t *testing.T) {
	e, _, _ := setup(t, "base")
	cases := []struct {
		mgr, native, pkg, entry string
	}{
		{"brew", "chezmoi", "chezmoi", ""},
		{"brew", "hashicorp/tap/terraform", "terraform", "hashicorp/tap/terraform"},
		{"brew", "openjdk@17", "openjdk-17", "openjdk@17"},
		{"winget", "jqlang.jq", "jq", ""}, // known in the catalog
		{"winget", "Microsoft.PowerToys", "powertoys", "Microsoft.PowerToys"},
		{"npm", "@google/gemini-cli", "gemini-cli", "@google/gemini-cli"},
		{"apt", "libnss3", "libnss3", ""},
	}
	for _, c := range cases {
		pkg, entry := e.AdoptName(c.mgr, c.native)
		gotEntry := ""
		if entry != nil {
			gotEntry = entry.Name
		}
		if pkg != c.pkg || gotEntry != c.entry {
			t.Errorf("AdoptName(%s, %s) = %s %q, want %s %q", c.mgr, c.native, pkg, gotEntry, c.pkg, c.entry)
		}
	}
}

func TestAliasResolvedToInstalled(t *testing.T) {
	e, mgrs, _ := setup(t, "work")
	mgrs["snap"].usable = false
	mgrs["apt"].aliases = map[string]string{"kubectl": "kubernetes-cli"}
	mgrs["apt"].installed["kubernetes-cli"] = true
	if st := e.State(ctx, "kubectl"); st.Status != StatusOK || st.Name != "kubernetes-cli" {
		t.Errorf("kubectl via alias = %+v", st)
	}
}
