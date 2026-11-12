// Package gitrepo keeps the manifest repo in sync: pull before, commit and
// push after.
package gitrepo

import (
	"context"
	"fmt"
	"strconv"
	"strings"

	"github.com/jorisdejosselin/install-sync/internal/pm"
)

// Repo is the git repo that contains the manifest folder.
type Repo struct {
	Dir string // manifest folder (may be a subfolder of the repo)
	R   pm.Runner
}

func (g Repo) git(ctx context.Context, args ...string) (pm.Result, error) {
	res, err := g.R.Capture(ctx, "git", append([]string{"-C", g.Dir}, args...)...)
	if err != nil {
		return res, err
	}
	if !res.OK() {
		msg := strings.TrimSpace(res.Stderr)
		if msg == "" {
			msg = strings.TrimSpace(res.Stdout)
		}
		return res, fmt.Errorf("git %s: %s", strings.Join(args, " "), msg)
	}
	return res, nil
}

// Clone clones url into dir.
func Clone(ctx context.Context, r pm.Runner, url, dir string) error {
	res, err := r.Capture(ctx, "git", "clone", url, dir)
	if err != nil {
		return err
	}
	if !res.OK() {
		return fmt.Errorf("git clone %s: %s", url, strings.TrimSpace(res.Stderr))
	}
	return nil
}

// IsRepo reports whether Dir is inside a git work tree.
func (g Repo) IsRepo(ctx context.Context) bool {
	res, err := g.R.Capture(ctx, "git", "-C", g.Dir, "rev-parse", "--is-inside-work-tree")
	return err == nil && res.OK() && strings.TrimSpace(res.Stdout) == "true"
}

// Root returns the top-level folder of the repo.
func (g Repo) Root(ctx context.Context) (string, error) {
	res, err := g.git(ctx, "rev-parse", "--show-toplevel")
	return strings.TrimSpace(res.Stdout), err
}

// Remote returns the URL of origin, or "".
func (g Repo) Remote(ctx context.Context) string {
	res, err := g.git(ctx, "remote", "get-url", "origin")
	if err != nil {
		return ""
	}
	return strings.TrimSpace(res.Stdout)
}

func (g Repo) hasUpstream(ctx context.Context) bool {
	_, err := g.git(ctx, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
	return err == nil
}

// Pull rebases onto the upstream. A repo without an upstream is left alone.
// When the rebase fails it is aborted so the repo is never left mid-rebase.
func (g Repo) Pull(ctx context.Context) (bool, error) {
	if !g.hasUpstream(ctx) {
		return false, nil
	}
	if _, err := g.git(ctx, "pull", "--rebase", "--autostash", "--quiet"); err != nil {
		_, _ = g.git(ctx, "rebase", "--abort")
		return false, err
	}
	return true, nil
}

// Commit stages everything under the manifest folder and commits it. It
// reports false when there was nothing to commit.
func (g Repo) Commit(ctx context.Context, msg string) (bool, error) {
	if _, err := g.git(ctx, "add", "-A", "--", "."); err != nil {
		return false, err
	}
	res, err := g.R.Capture(ctx, "git", "-C", g.Dir, "diff", "--cached", "--quiet", "--", ".")
	if err != nil {
		return false, err
	}
	if res.OK() {
		return false, nil
	}
	if _, err := g.git(ctx, "commit", "--quiet", "-m", msg, "--", "."); err != nil {
		return false, err
	}
	return true, nil
}

// Push pushes the current branch, setting the upstream on first push.
func (g Repo) Push(ctx context.Context) error {
	if g.hasUpstream(ctx) {
		_, err := g.git(ctx, "push", "--quiet")
		return err
	}
	if g.Remote(ctx) == "" {
		return fmt.Errorf("no remote named origin to push to")
	}
	_, err := g.git(ctx, "push", "--quiet", "-u", "origin", "HEAD")
	return err
}

// Status describes the repo's sync state.
type Status struct {
	Root      string   `json:"root"`
	Remote    string   `json:"remote,omitempty"`
	Branch    string   `json:"branch"`
	Upstream  string   `json:"upstream,omitempty"`
	Ahead     int      `json:"ahead"`
	Behind    int      `json:"behind"`
	Dirty     bool     `json:"dirty"`
	Unpushed  bool     `json:"unpushed"`
	DirtyList []string `json:"dirty_files,omitempty"`
}

// Status reads branch, upstream and working-tree state (from the last fetch).
func (g Repo) Status(ctx context.Context) (Status, error) {
	var st Status
	var err error
	if st.Root, err = g.Root(ctx); err != nil {
		return st, err
	}
	st.Remote = g.Remote(ctx)
	res, err := g.git(ctx, "status", "--porcelain=v2", "--branch")
	if err != nil {
		return st, err
	}
	for _, l := range strings.Split(res.Stdout, "\n") {
		switch {
		case strings.HasPrefix(l, "# branch.head "):
			st.Branch = strings.TrimPrefix(l, "# branch.head ")
		case strings.HasPrefix(l, "# branch.upstream "):
			st.Upstream = strings.TrimPrefix(l, "# branch.upstream ")
		case strings.HasPrefix(l, "# branch.ab "):
			f := strings.Fields(strings.TrimPrefix(l, "# branch.ab "))
			if len(f) == 2 {
				st.Ahead, _ = strconv.Atoi(strings.TrimPrefix(f[0], "+"))
				st.Behind, _ = strconv.Atoi(strings.TrimPrefix(f[1], "-"))
			}
		case l != "" && !strings.HasPrefix(l, "#"):
			st.Dirty = true
			f := strings.Fields(l)
			st.DirtyList = append(st.DirtyList, f[len(f)-1])
		}
	}
	st.Unpushed = st.Ahead > 0 || (st.Upstream == "" && st.Remote != "")
	return st, nil
}
