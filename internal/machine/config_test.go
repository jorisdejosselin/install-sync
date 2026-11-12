package machine

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSaveLoad(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sub", "config.yaml")
	t.Setenv("INSTALL_SYNC_CONFIG", path)

	if _, _, err := Load(); !errors.Is(err, ErrNotInitialised) {
		t.Fatalf("missing config: %v", err)
	}
	no := false
	if err := Save(path, &Config{Profile: "work", Manifest: dir, Git: GitOpts{Push: &no}}); err != nil {
		t.Fatal(err)
	}
	c, got, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if got != path || c.Profile != "work" || c.Manifest != dir || c.PushEnabled() {
		t.Errorf("loaded %+v from %s", c, got)
	}

	_ = os.WriteFile(path, []byte("profile: work\nmanifest: x\nbogus: 1\n"), 0o644)
	if _, _, err := Load(); err == nil || !strings.Contains(err.Error(), "bogus") {
		t.Errorf("unknown field: %v", err)
	}
	_ = os.WriteFile(path, []byte("profile: work\n"), 0o644)
	if _, _, err := Load(); err == nil {
		t.Error("missing manifest should fail")
	}
}

func TestOrder(t *testing.T) {
	c := &Config{}
	if got := strings.Join(c.Order("linux"), ","); got != "apt,snap,script,npm" {
		t.Errorf("linux = %s", got)
	}
	if got := strings.Join(c.Order("darwin"), ","); got != "brew,npm" {
		t.Errorf("darwin = %s", got)
	}
	c.Managers = []string{"npm", "apt"}
	if got := strings.Join(c.Order("linux"), ","); got != "npm,apt" {
		t.Errorf("override = %s", got)
	}
	if !(&Config{}).PushEnabled() {
		t.Error("push defaults to on")
	}
}

func TestExpand(t *testing.T) {
	home, _ := os.UserHomeDir()
	got, err := Expand("~/x")
	if err != nil || got != filepath.Join(home, "x") {
		t.Errorf("expand = %s %v", got, err)
	}
}
