package manifest

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func write(t *testing.T, dir, rel, content string) {
	t.Helper()
	p := filepath.Join(dir, rel)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func fixture(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	write(t, dir, CatalogFile, `# catalog comment
packages:
  jq:
    winget: jqlang.jq
  iterm2:
    brew: {cask: true}
  k9s:
    script:
      install: |
        echo one
        echo two
      check: command -v k9s
  md-to-pdf:
    npm: md-to-pdf
    requires:
      apt:
        - libnss3
`)
	write(t, dir, "profiles/base.yaml", "packages:\n  - git\n  - jq\n")
	write(t, dir, "profiles/k8s.yaml", "packages:\n  - k9s\n  - jq\n")
	write(t, dir, "profiles/work.yaml", "# work comment\ninclude: [base, k8s]\npackages:\n  - md-to-pdf # keep me\n  - git\n")
	write(t, dir, "profiles/empty.yaml", "packages: []\n")
	return dir
}

func TestLoadAndResolve(t *testing.T) {
	m, err := Load(fixture(t))
	if err != nil {
		t.Fatal(err)
	}
	if got := m.Catalog["iterm2"].Entries[Brew]; !got.Cask || got.Name != "" {
		t.Errorf("iterm2 brew entry = %+v", got)
	}
	if got := m.Catalog["jq"].Entries[Winget].Name; got != "jqlang.jq" {
		t.Errorf("jq winget = %q", got)
	}
	if got := m.Catalog["md-to-pdf"].Requires[Apt]; len(got) != 1 || got[0] != "libnss3" {
		t.Errorf("requires = %v", got)
	}
	res, err := m.Resolve("work")
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	for _, r := range res {
		names = append(names, r.Package)
	}
	if got, want := strings.Join(names, ","), "git,jq,k9s,md-to-pdf"; got != want {
		t.Errorf("resolve order = %s, want %s", got, want)
	}
	for _, r := range res {
		if r.Package == "jq" && strings.Join(r.From, ",") != "base,k8s" {
			t.Errorf("jq from = %v", r.From)
		}
		if r.Package == "git" && strings.Join(r.From, ",") != "base,work" {
			t.Errorf("git from = %v", r.From)
		}
	}
	if got := m.IncludedBy("base"); len(got) != 1 || got[0] != "work" {
		t.Errorf("included by = %v", got)
	}
	if pkg, ok := m.FindByNative(Winget, "JQLANG.JQ"); !ok || pkg != "jq" {
		t.Errorf("FindByNative = %q %v", pkg, ok)
	}
}

func TestValidationErrors(t *testing.T) {
	cases := map[string]struct{ catalog, profile, want string }{
		"unknown manager": {"packages:\n  jq:\n    pacman: jq\n", "packages: [jq]\n", `unknown package manager "pacman"`},
		"script no check": {"packages:\n  x:\n    script:\n      install: echo\n", "packages: [x]\n", "script needs both install and check"},
		"cask on apt":     {"packages:\n  x:\n    apt: {cask: true}\n", "packages: [x]\n", "cask is only valid for brew"},
		"unknown include": {"", "include: [nope]\npackages: []\n", `includes unknown profile "nope"`},
		"duplicate":       {"", "packages: [a, a]\n", "listed twice"},
		"bad name":        {"", "packages: [Git.Git]\n", "invalid package name"},
		"unknown field":   {"", "packages: []\nincludes: [x]\n", "field includes not found"},
	}
	for name, c := range cases {
		t.Run(name, func(t *testing.T) {
			dir := t.TempDir()
			write(t, dir, CatalogFile, c.catalog)
			write(t, dir, "profiles/p.yaml", c.profile)
			_, err := Load(dir)
			if err == nil || !strings.Contains(err.Error(), c.want) {
				t.Fatalf("err = %v, want %q", err, c.want)
			}
		})
	}
}

func TestIncludeCycle(t *testing.T) {
	dir := t.TempDir()
	write(t, dir, "profiles/a.yaml", "include: [b]\npackages: []\n")
	write(t, dir, "profiles/b.yaml", "include: [a]\npackages: []\n")
	if _, err := Load(dir); err == nil || !strings.Contains(err.Error(), "include cycle") {
		t.Fatalf("err = %v", err)
	}
}

func TestNotAManifest(t *testing.T) {
	if _, err := Load(t.TempDir()); err == nil || !strings.Contains(err.Error(), "no profiles/ folder") {
		t.Fatalf("err = %v", err)
	}
}

func TestEditsKeepCommentsAndScripts(t *testing.T) {
	dir := fixture(t)
	added, err := AddPackages(dir, "work", "terraform", "git")
	if err != nil {
		t.Fatal(err)
	}
	if len(added) != 1 || added[0] != "terraform" {
		t.Errorf("added = %v", added)
	}
	data, _ := os.ReadFile(ProfilePath(dir, "work"))
	for _, want := range []string{"# work comment", "# keep me", "- terraform"} {
		if !strings.Contains(string(data), want) {
			t.Errorf("work.yaml lost %q:\n%s", want, data)
		}
	}

	if ok, err := RemovePackage(dir, "work", "git"); err != nil || !ok {
		t.Fatalf("remove = %v %v", ok, err)
	}
	if ok, _ := RemovePackage(dir, "work", "git"); ok {
		t.Error("second remove reported true")
	}

	if err := SetEntry(dir, "terraform", Brew, Entry{Name: "hashicorp/tap/terraform"}); err != nil {
		t.Fatal(err)
	}
	if err := SetEntry(dir, "jq", Winget, Entry{Name: "stedolan.jq"}); err != nil {
		t.Fatal(err)
	}
	cat, _ := os.ReadFile(filepath.Join(dir, CatalogFile))
	for _, want := range []string{"# catalog comment", "install: |\n        echo one\n        echo two", "brew: hashicorp/tap/terraform", "winget: stedolan.jq"} {
		if !strings.Contains(string(cat), want) {
			t.Errorf("packages.yaml missing %q:\n%s", want, cat)
		}
	}

	if _, err := AddPackages(dir, "empty", "jq"); err != nil {
		t.Fatal(err)
	}
	data, _ = os.ReadFile(ProfilePath(dir, "empty"))
	if !strings.Contains(string(data), "- jq") {
		t.Errorf("empty profile not converted to block list:\n%s", data)
	}

	m, err := Load(dir)
	if err != nil {
		t.Fatalf("edited manifest no longer loads: %v", err)
	}
	if m.Profiles["work"].Has("git") || !m.Profiles["work"].Has("terraform") {
		t.Errorf("work packages = %v", m.Profiles["work"].Packages)
	}
}

func TestSetEntryCreatesCatalog(t *testing.T) {
	dir := t.TempDir()
	write(t, dir, "profiles/p.yaml", "packages: []\n")
	if err := SetEntry(dir, "x", Npm, Entry{Name: "@scope/x"}); err != nil {
		t.Fatal(err)
	}
	m, err := Load(dir)
	if err != nil {
		t.Fatal(err)
	}
	if m.Catalog["x"].Entries[Npm].Name != "@scope/x" {
		t.Errorf("catalog = %+v", m.Catalog)
	}
}

func TestCreateProfile(t *testing.T) {
	dir := fixture(t)
	if err := CreateProfile(dir, "new", []string{"base"}); err != nil {
		t.Fatal(err)
	}
	if err := CreateProfile(dir, "new", nil); err == nil {
		t.Error("creating twice should fail")
	}
	if err := CreateProfile(dir, "Bad Name", nil); err == nil {
		t.Error("invalid name accepted")
	}
	m, err := Load(dir)
	if err != nil {
		t.Fatal(err)
	}
	if got := m.Profiles["new"].Include; len(got) != 1 || got[0] != "base" {
		t.Errorf("include = %v", got)
	}
}
