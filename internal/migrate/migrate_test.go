package migrate

import (
	"strings"
	"testing"

	"github.com/jorisdejosselin/install-sync/internal/manifest"
)

const v0 = `{
  "machines": {
    "a1": {"profile_id": "a1", "machine_name": "MacBookPro.local", "os_type": "darwin", "architecture": "arm64"},
    "b2": {"profile_id": "b2", "machine_name": "gaming", "os_type": "windows", "architecture": "AMD64"}
  },
  "packages": {
    "a1": [
      {"name": "jq", "package_manager": "brew"},
      {"name": "danielfoehrkn/switch/switch", "package_manager": "brew"},
      {"name": "md-to-pdf", "package_manager": "npm"},
      {"name": "k9s", "package_manager": "script"},
      {"name": "thing", "package_manager": "pacman"}
    ],
    "b2": [
      {"name": "Git.Git", "package_manager": "winget"},
      {"name": "node", "package_manager": "winget"}
    ]
  }
}`

func TestConvertAndWrite(t *testing.T) {
	res, err := Convert([]byte(v0))
	if err != nil {
		t.Fatal(err)
	}
	mac := strings.Join(res.Profiles["macbookpro.local-darwin"], ",")
	if mac != "jq,switch,md-to-pdf,k9s" {
		t.Errorf("mac profile = %s", mac)
	}
	if got := strings.Join(res.Profiles["gaming-windows"], ","); got != "git,node" {
		t.Errorf("gaming profile = %s", got)
	}
	if res.Catalog["switch"].Entries[manifest.Brew].Name != "danielfoehrkn/switch/switch" {
		t.Error("tapped brew formula needs an entry")
	}
	if _, ok := res.Catalog["jq"]; ok {
		t.Error("plain brew names need no definition")
	}
	if res.Catalog["git"].Entries[manifest.Winget].Name != "Git.Git" {
		t.Error("winget id not kept")
	}
	notes := strings.Join(res.Notes, "\n")
	for _, want := range []string{"k9s was a script install", "unknown package manager \"pacman\"", "check winget id for node"} {
		if !strings.Contains(notes, want) {
			t.Errorf("notes missing %q:\n%s", want, notes)
		}
	}

	dir := t.TempDir()
	if err := Write(dir, res); err != nil {
		t.Fatal(err)
	}
	m, err := manifest.Load(dir)
	if err != nil {
		t.Fatalf("migrated manifest invalid: %v", err)
	}
	if len(m.Profiles) != 2 {
		t.Errorf("profiles = %v", m.ProfileNames())
	}
	if err := Write(dir, res); err == nil {
		t.Error("second write should refuse to overwrite")
	}
}

func TestConvertRejectsGarbage(t *testing.T) {
	if _, err := Convert([]byte("not json")); err == nil {
		t.Error("expected error")
	}
}
