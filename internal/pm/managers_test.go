package pm

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/jorisdejosselin/install-sync/internal/manifest"
)

var ctx = context.Background()

func TestBrew(t *testing.T) {
	r := &FakeRunner{Paths: map[string]bool{"brew": true}, Responses: map[string]Result{
		"brew list --formula -1":             {Stdout: "jq\nswitch\nopenssl@3\n"},
		"brew list --cask -1":                {Stdout: "iterm2\n"},
		"brew leaves --installed-on-request": {Stdout: "jq\nswitch\n"},
		"brew info --json=v2 iterm2":         {Stdout: `{"formulae":[],"casks":[{"token":"iterm2"}]}`},
		"brew info --json=v2 jq":             {Stdout: `{"formulae":[{"name":"jq"}],"casks":[]}`},
		"brew info --json=v2 nope":           {Code: 1},
		"brew info --json=v2 kubectl":        {Stdout: `{"formulae":[{"name":"kubernetes-cli","full_name":"kubernetes-cli"}],"casks":[]}`},
	}}
	b := New(r, "darwin")[manifest.Brew]
	if !b.Usable() || !b.Implied() {
		t.Fatal("brew should be usable and implied")
	}
	set, err := b.Installed(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if ok, _ := b.IsInstalled(ctx, manifest.Entry{Name: "danielfoehrkn/switch/switch"}, set); !ok {
		t.Error("tapped formula should match by short name")
	}
	if ok, _ := b.IsInstalled(ctx, manifest.Entry{Name: "iterm2"}, set); !ok {
		t.Error("cask should be installed")
	}
	manual, ok, err := b.Manual(ctx)
	if err != nil || !ok || strings.Join(manual, ",") != "jq,switch,iterm2" {
		t.Errorf("manual = %v %v %v", manual, ok, err)
	}
	e, found, _ := b.Probe(ctx, manifest.Entry{Name: "iterm2"})
	if !found || !e.Cask {
		t.Errorf("probe iterm2 = %+v %v", e, found)
	}
	e, found, _ = b.Probe(ctx, manifest.Entry{Name: "jq"})
	if !found || e.Cask {
		t.Errorf("probe jq = %+v %v", e, found)
	}
	e, found, _ = b.Probe(ctx, manifest.Entry{Name: "kubectl"})
	if !found || e.Name != "kubernetes-cli" {
		t.Errorf("alias not resolved: %+v %v", e, found)
	}
	if _, found, _ = b.Probe(ctx, manifest.Entry{Name: "nope"}); found {
		t.Error("nope should not be found")
	}
	_ = b.Install(ctx, manifest.Entry{Name: "iterm2", Cask: true})
	_ = b.Upgrade(ctx, []manifest.Entry{{Name: "jq"}, {Name: "iterm2", Cask: true}})
	calls := strings.Join(r.Calls, "\n")
	for _, want := range []string{"brew install --cask iterm2", "brew upgrade --formula jq", "brew upgrade --cask iterm2"} {
		if !strings.Contains(calls, want) {
			t.Errorf("missing call %q in\n%s", want, calls)
		}
	}
}

func TestApt(t *testing.T) {
	const infoFmt = "dpkg-query -W -f=${Package}\t${db:Status-Abbrev}\t${Priority}\t${Essential}\t${Depends}, ${Pre-Depends}, ${Recommends}\n"
	r := &FakeRunner{Paths: map[string]bool{"apt-get": true, "dpkg-query": true}, Responses: map[string]Result{
		"dpkg-query -W -f=${Package}\t${db:Status-Abbrev}\n": {Stdout: "jq\tii \ncurl\tii \nold\trc \n"},
		infoFmt: {Stdout: "jq\tii \toptional\tno\tlibjq1 (= 1.7), libc6 (>= 2.34), , \n" +
			"libjq1\tii \toptional\tno\tlibc6, , \n" +
			"curl\tii \toptional\tno\tlibcurl4t64 | libcurl4, , \n" +
			"libc6\tii \toptional\tno\t, , \n" +
			"bash\tii \trequired\tyes\t, , \n" +
			"sudo\tii \timportant\tno\t, , \n"},
		"apt-mark showmanual": {Stdout: "jq\ncurl\nbash\nsudo\nlibc6\nlibjq1\n"},
		"apt-cache show jq":   {Stdout: "Package: jq\n"},
		"apt-cache show nope": {Code: 100},
	}}
	a := New(r, "linux")[manifest.Apt]
	set, err := a.Installed(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if !set["jq"] || set["old"] {
		t.Errorf("installed = %v", set)
	}
	manual, _, _ := a.Manual(ctx)
	if strings.Join(manual, ",") != "jq,curl" {
		t.Errorf("manual should keep only chosen leaves, got %v", manual)
	}

	// With empty package lists, a failed probe says why.
	a.(*apt).listsDir = t.TempDir()
	if _, ok, err := a.Probe(ctx, manifest.Entry{Name: "nope"}); ok || err != ErrAptListsEmpty {
		t.Errorf("probe with empty lists = %v %v", ok, err)
	}
	_ = os.WriteFile(a.(*apt).listsDir+"/x_Packages", nil, 0o644)
	if _, ok, err := a.Probe(ctx, manifest.Entry{Name: "nope"}); ok || err != nil {
		t.Errorf("probe nope = %v %v", ok, err)
	}
	if _, ok, _ := a.Probe(ctx, manifest.Entry{Name: "jq"}); !ok {
		t.Error("jq should be available")
	}

	if err := a.(Refresher).Refresh(ctx); err != nil {
		t.Fatal(err)
	}
	_ = a.Install(ctx, manifest.Entry{Name: "jq"})
	_ = a.Install(ctx, manifest.Entry{Name: "curl"})
	calls := strings.Join(r.Calls, "\n")
	if strings.Count(calls, "apt-get update") != 1 {
		t.Errorf("apt-get update should run once per session:\n%s", calls)
	}
	if !strings.Contains(calls, "apt-get install -y jq") {
		t.Errorf("no install call:\n%s", calls)
	}
}

func TestSnap(t *testing.T) {
	r := &FakeRunner{Paths: map[string]bool{"snap": true}, Responses: map[string]Result{
		"snap list":         {Stdout: "Name Version Rev Tracking Publisher Notes\ncore22 1 1 latest canonical base\nkubectl 1.31 1 latest canonical classic\nsnapd 2 1 latest canonical snapd\n"},
		"snap info kubectl": {Stdout: "name: kubectl\nchannels:\n  latest/stable: 1.31 (1) 9MB classic\n"},
	}}
	s := New(r, "linux")[manifest.Snap]
	manual, _, _ := s.Manual(ctx)
	if strings.Join(manual, ",") != "kubectl" {
		t.Errorf("manual = %v", manual)
	}
	e, ok, _ := s.Probe(ctx, manifest.Entry{Name: "kubectl"})
	if !ok || !e.Classic {
		t.Errorf("probe = %+v %v", e, ok)
	}
	_ = s.Install(ctx, e)
	if !strings.Contains(strings.Join(r.Calls, "\n"), "snap install kubectl --classic") {
		t.Errorf("calls = %v", r.Calls)
	}
}

func TestNpmAndWinget(t *testing.T) {
	r := &FakeRunner{Paths: map[string]bool{"npm": true}, Responses: map[string]Result{
		"npm ls -g --depth=0 --json": {Stdout: `{"dependencies":{"npm":{},"corepack":{},"md-to-pdf":{},"@google/gemini-cli":{}}}`},
	}}
	n := New(r, "darwin")[manifest.Npm]
	if n.Implied() {
		t.Error("npm must not be implied")
	}
	manual, _, _ := n.Manual(ctx)
	if len(manual) != 2 {
		t.Errorf("manual = %v", manual)
	}
	w := New(r, "windows")[manifest.Winget]
	if w.Usable() {
		t.Error("winget not on PATH")
	}
}

func TestScript(t *testing.T) {
	r := &FakeRunner{Paths: map[string]bool{"sh": true}, Responses: map[string]Result{
		"sh -c command -v k9s": {Code: 1},
		"sh -c command -v jq":  {Code: 0},
	}}
	s := New(r, "linux")[manifest.Script]
	if ok, _ := s.IsInstalled(ctx, manifest.Entry{Check: "command -v k9s"}, nil); ok {
		t.Error("k9s should not be installed")
	}
	if ok, _ := s.IsInstalled(ctx, manifest.Entry{Check: "command -v jq"}, nil); !ok {
		t.Error("jq should be installed")
	}
	if _, ok, _ := s.Manual(ctx); ok {
		t.Error("script cannot detect untracked")
	}
	if err := s.Uninstall(ctx, manifest.Entry{}); err == nil {
		t.Error("uninstall without command should fail")
	}
}

func TestExecRunner(t *testing.T) {
	r := ExecRunner{}
	if !r.LookPath("go") {
		t.Skip("go not on PATH")
	}
	res, err := r.Capture(ctx, "go", "version")
	if err != nil || !res.OK() || !strings.HasPrefix(res.Stdout, "go version") {
		t.Errorf("capture = %+v %v", res, err)
	}
	res, err = r.Capture(ctx, "go", "no-such-subcommand")
	if err != nil || res.OK() {
		t.Errorf("failing command = %+v %v", res, err)
	}
	if _, err := r.Capture(ctx, "definitely-not-a-binary-xyz"); err == nil {
		t.Error("missing binary should error")
	}
}
