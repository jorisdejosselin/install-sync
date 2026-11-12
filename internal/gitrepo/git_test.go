package gitrepo

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/jorisdejosselin/install-sync/internal/pm"
)

var ctx = context.Background()

func gitEnv(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git not installed")
	}
	for k, v := range map[string]string{
		"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
		"GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
		"GIT_CONFIG_GLOBAL": os.DevNull, "GIT_CONFIG_NOSYSTEM": "1",
	} {
		t.Setenv(k, v)
	}
}

func run(t *testing.T, dir string, args ...string) {
	t.Helper()
	cmd := exec.Command("git", args...)
	cmd.Dir = dir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("git %v: %v\n%s", args, err, out)
	}
}

// NewTestRemote creates a bare repo with one commit and returns its path.
func newRemote(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	bare := filepath.Join(root, "remote.git")
	run(t, root, "init", "-q", "--bare", "-b", "main", bare)
	seed := filepath.Join(root, "seed")
	run(t, root, "clone", "-q", bare, seed)
	_ = os.MkdirAll(filepath.Join(seed, "profiles"), 0o755)
	_ = os.WriteFile(filepath.Join(seed, "profiles", "a.yaml"), []byte("packages: []\n"), 0o644)
	run(t, seed, "add", "-A")
	run(t, seed, "commit", "-qm", "seed")
	run(t, seed, "push", "-q", "origin", "HEAD:main")
	return bare
}

func TestCloneCommitPushPull(t *testing.T) {
	gitEnv(t)
	r := pm.ExecRunner{}
	bare := newRemote(t)
	a := filepath.Join(t.TempDir(), "a")
	b := filepath.Join(t.TempDir(), "b")
	for _, d := range []string{a, b} {
		if err := Clone(ctx, r, bare, d); err != nil {
			t.Fatal(err)
		}
	}
	ra, rb := Repo{Dir: a, R: r}, Repo{Dir: b, R: r}
	if !ra.IsRepo(ctx) {
		t.Fatal("clone is not a repo")
	}
	if ok, err := ra.Commit(ctx, "nothing"); err != nil || ok {
		t.Fatalf("empty commit = %v %v", ok, err)
	}
	_ = os.WriteFile(filepath.Join(a, "profiles", "a.yaml"), []byte("packages: [jq]\n"), 0o644)
	if ok, err := ra.Commit(ctx, "a: add jq"); err != nil || !ok {
		t.Fatalf("commit = %v %v", ok, err)
	}
	st, err := ra.Status(ctx)
	if err != nil || st.Ahead != 1 || !st.Unpushed || st.Dirty {
		t.Fatalf("status before push = %+v %v", st, err)
	}
	if err := ra.Push(ctx); err != nil {
		t.Fatal(err)
	}
	// b has a local, uncommitted change; pull must still bring in a's commit.
	_ = os.WriteFile(filepath.Join(b, "notes.txt"), []byte("x"), 0o644)
	if pulled, err := rb.Pull(ctx); err != nil || !pulled {
		t.Fatalf("pull = %v %v", pulled, err)
	}
	data, _ := os.ReadFile(filepath.Join(b, "profiles", "a.yaml"))
	if string(data) != "packages: [jq]\n" {
		t.Errorf("b did not get a's change: %q", data)
	}
	st, _ = rb.Status(ctx)
	if !st.Dirty || st.Branch != "main" || st.Upstream != "origin/main" {
		t.Errorf("status b = %+v", st)
	}
}

func TestSubfolderManifestOnlyCommitsItsFolder(t *testing.T) {
	gitEnv(t)
	r := pm.ExecRunner{}
	root := t.TempDir()
	run(t, root, "init", "-q", "-b", "main")
	sub := filepath.Join(root, "install-sync")
	_ = os.MkdirAll(sub, 0o755)
	_ = os.WriteFile(filepath.Join(sub, "packages.yaml"), []byte("packages: {}\n"), 0o644)
	_ = os.WriteFile(filepath.Join(root, "other.txt"), []byte("not mine"), 0o644)
	repo := Repo{Dir: sub, R: r}
	if ok, err := repo.Commit(ctx, "manifest"); err != nil || !ok {
		t.Fatalf("commit = %v %v", ok, err)
	}
	st, _ := Repo{Dir: root, R: r}.Status(ctx)
	if !st.Dirty || len(st.DirtyList) != 1 || st.DirtyList[0] != "other.txt" {
		t.Errorf("other.txt should stay uncommitted: %+v", st)
	}
	if pulled, err := repo.Pull(ctx); err != nil || pulled {
		t.Errorf("pull without upstream = %v %v", pulled, err)
	}
	if err := repo.Push(ctx); err == nil {
		t.Error("push without origin should fail")
	}
}
