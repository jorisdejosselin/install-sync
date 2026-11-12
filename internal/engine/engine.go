// Package engine compares a machine against its profile and changes it.
package engine

import (
	"context"
	"errors"
	"fmt"
	"io"
	"path"
	"regexp"
	"sort"
	"strings"

	"github.com/jorisdejosselin/install-sync/internal/manifest"
	"github.com/jorisdejosselin/install-sync/internal/pm"
)

// Package states reported by Diff.
const (
	StatusOK          = "ok"
	StatusMissing     = "missing"
	StatusUnavailable = "unavailable"
)

// Engine works on one machine applying one profile.
type Engine struct {
	M        *manifest.Manifest
	Profile  string
	Order    []string
	Managers map[string]pm.Manager
	Log      io.Writer

	usable    []pm.Manager
	installed map[string]pm.Set
	errs      map[string]error
}

// New returns an engine.
func New(m *manifest.Manifest, profile string, order []string, managers map[string]pm.Manager, log io.Writer) *Engine {
	if log == nil {
		log = io.Discard
	}
	return &Engine{M: m, Profile: profile, Order: order, Managers: managers, Log: log}
}

// Usable returns the package managers on this machine, in manager order.
func (e *Engine) Usable() []pm.Manager {
	if e.usable != nil {
		return e.usable
	}
	e.usable = []pm.Manager{}
	for _, name := range e.Order {
		if m, ok := e.Managers[name]; ok && m.Usable() {
			e.usable = append(e.usable, m)
		}
	}
	return e.usable
}

func (e *Engine) installedSet(ctx context.Context, m pm.Manager) pm.Set {
	if e.installed == nil {
		e.installed, e.errs = map[string]pm.Set{}, map[string]error{}
	}
	if s, ok := e.installed[m.Name()]; ok {
		return s
	}
	s, err := m.Installed(ctx)
	if err != nil {
		e.errs[m.Name()] = err
		s = pm.Set{}
	}
	e.installed[m.Name()] = s
	return s
}

func (e *Engine) markInstalled(m pm.Manager, native string) {
	if s, ok := e.installed[m.Name()]; ok {
		s[m.Key(native)] = true
	}
}

func (e *Engine) markRemoved(m pm.Manager, native string) {
	if s, ok := e.installed[m.Name()]; ok {
		delete(s, m.Key(native))
	}
}

// Rescan forgets which package managers exist and what is installed, so a
// package manager installed during this run (e.g. npm via nodejs) is seen.
func (e *Engine) Rescan() {
	e.usable, e.installed = nil, nil
}

// Prepare refreshes package indexes (apt-get update) so probing and installing
// see current packages. Call it before apply and add, not before diff.
func (e *Engine) Prepare(ctx context.Context) error {
	for _, m := range e.Usable() {
		if r, ok := m.(pm.Refresher); ok {
			if err := r.Refresh(ctx); err != nil {
				return fmt.Errorf("%s: %w", m.Name(), err)
			}
		}
	}
	return nil
}

func (e *Engine) recordErr(m pm.Manager, err error) {
	if e.errs == nil {
		e.errs = map[string]error{}
	}
	e.errs[m.Name()] = err
}

// Candidate is one way to install a package on this machine.
type Candidate struct {
	Manager pm.Manager
	Entry   manifest.Entry
	Implied bool
}

// Candidates returns the ways pkg could be installed here, in manager order.
// Explicit entries come from the catalog; managers without an entry are tried
// with the package's own name when they support implied definitions.
func (e *Engine) Candidates(pkg string) []Candidate {
	def, _ := e.M.Definition(pkg)
	var out []Candidate
	for _, m := range e.Usable() {
		if entry, ok := def.Entries[m.Name()]; ok {
			if entry.Name == "" {
				entry.Name = pkg
			}
			out = append(out, Candidate{Manager: m, Entry: entry})
		} else if m.Implied() {
			out = append(out, Candidate{Manager: m, Entry: manifest.Entry{Name: pkg}, Implied: true})
		}
	}
	return out
}

// PackageState is one profile package on this machine.
type PackageState struct {
	Package string   `json:"package"`
	From    []string `json:"from"`
	Status  string   `json:"status"`
	Manager string   `json:"manager,omitempty"`
	Name    string   `json:"name,omitempty"`
	Error   string   `json:"error,omitempty"`

	entry   manifest.Entry
	manager pm.Manager
}

// State works out whether pkg is installed, missing (and how it would be
// installed) or unavailable.
func (e *Engine) State(ctx context.Context, pkg string) PackageState {
	st := PackageState{Package: pkg}
	cands := e.Candidates(pkg)
	for _, c := range cands {
		ok, err := c.Manager.IsInstalled(ctx, c.Entry, e.installedSet(ctx, c.Manager))
		if err != nil {
			st.Error = err.Error()
			continue
		}
		if ok {
			st.Status, st.Manager, st.Name, st.entry, st.manager = StatusOK, c.Manager.Name(), c.Entry.Name, c.Entry, c.Manager
			return st
		}
	}
	for _, c := range cands {
		entry := c.Entry
		if c.Implied {
			probed, ok, err := c.Manager.Probe(ctx, entry)
			if err != nil {
				st.Error = err.Error()
				e.recordErr(c.Manager, err)
			}
			if !ok {
				continue
			}
			entry = probed
		}
		st.Status, st.Manager, st.Name, st.entry, st.manager = StatusMissing, c.Manager.Name(), entry.Name, entry, c.Manager
		return st
	}
	st.Status = StatusUnavailable
	return st
}

// Untracked is something installed on purpose that the profile does not list.
type Untracked struct {
	Manager string `json:"manager"`
	Name    string `json:"name"`
}

// Report is the result of Diff.
type Report struct {
	Profile   string         `json:"profile"`
	Managers  []string       `json:"managers"`
	Packages  []PackageState `json:"packages"`
	Untracked []Untracked    `json:"untracked"`
	// NoUntracked lists usable managers that cannot report untracked packages.
	NoUntracked []string          `json:"no_untracked_detection,omitempty"`
	Errors      map[string]string `json:"errors,omitempty"`
}

// Count returns how many packages have the given status.
func (r *Report) Count(status string) int {
	n := 0
	for _, p := range r.Packages {
		if p.Status == status {
			n++
		}
	}
	return n
}

// Drift reports whether anything is missing or untracked.
func (r *Report) Drift() bool { return r.Count(StatusMissing) > 0 || len(r.Untracked) > 0 }

// Diff compares the profile against this machine.
func (e *Engine) Diff(ctx context.Context, withUntracked bool) (*Report, error) {
	resolved, err := e.M.Resolve(e.Profile)
	if err != nil {
		return nil, err
	}
	rep := &Report{Profile: e.Profile, Untracked: []Untracked{}}
	for _, m := range e.Usable() {
		rep.Managers = append(rep.Managers, m.Name())
	}
	for _, r := range resolved {
		st := e.State(ctx, r.Package)
		st.From = r.From
		rep.Packages = append(rep.Packages, st)
	}
	if withUntracked {
		rep.Untracked, rep.NoUntracked, err = e.untracked(ctx, resolved)
		if err != nil {
			return nil, err
		}
	}
	if len(e.errs) > 0 {
		rep.Errors = map[string]string{}
		for k, v := range e.errs {
			rep.Errors[k] = v.Error()
		}
	}
	return rep, nil
}

func (e *Engine) untracked(ctx context.Context, resolved []manifest.Resolved) ([]Untracked, []string, error) {
	out := []Untracked{}
	var unsupported []string
	for _, m := range e.Usable() {
		names, ok, err := m.Manual(ctx)
		if !ok {
			unsupported = append(unsupported, m.Name())
			continue
		}
		if err != nil {
			e.recordErr(m, err)
			continue
		}
		tracked := map[string]bool{}
		for _, r := range resolved {
			for _, c := range e.Candidates(r.Package) {
				if c.Manager == m {
					tracked[m.Key(c.Entry.Name)] = true
				}
			}
			def, _ := e.M.Definition(r.Package)
			for _, req := range def.Requires[m.Name()] {
				tracked[m.Key(req)] = true
			}
		}
		for _, n := range names {
			if !tracked[m.Key(n)] {
				out = append(out, Untracked{Manager: m.Name(), Name: n})
			}
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Manager != out[j].Manager {
			return out[i].Manager < out[j].Manager
		}
		return out[i].Name < out[j].Name
	})
	return out, unsupported, nil
}

// ErrNeedsConfirmation means a script install was skipped because nobody
// confirmed it.
var ErrNeedsConfirmation = errors.New("needs confirmation")

// InstallOpts controls installs.
type InstallOpts struct {
	// Yes confirms script commands without asking.
	Yes bool
	// Confirm asks the user; nil means nobody can be asked.
	Confirm func(prompt string) bool
	DryRun  bool
}

// Install installs a missing package (and what it requires).
func (e *Engine) Install(ctx context.Context, st PackageState, o InstallOpts) error {
	if st.Status != StatusMissing {
		return fmt.Errorf("%s is %s", st.Package, st.Status)
	}
	m, entry := st.manager, st.entry
	if o.DryRun {
		if m.Name() == manifest.Script {
			fmt.Fprintf(e.Log, "would run the install script for %s:\n    %s\n", st.Package, strings.ReplaceAll(strings.TrimSpace(entry.Install), "\n", "\n    "))
		} else {
			fmt.Fprintf(e.Log, "would install %s with %s (%s)\n", st.Package, m.Name(), entry.Name)
		}
		return nil
	}
	if m.Name() == manifest.Script && !o.Yes {
		prompt := fmt.Sprintf("Run install script for %s?\n    %s\n", st.Package, entry.Install)
		if o.Confirm == nil {
			fmt.Fprintf(e.Log, "! %s needs confirmation to run:\n    %s\n", st.Package, entry.Install)
			return ErrNeedsConfirmation
		}
		if !o.Confirm(prompt) {
			return ErrNeedsConfirmation
		}
	}
	def, _ := e.M.Definition(st.Package)
	for _, mgrName := range sortedKeys(def.Requires) {
		rm, ok := e.Managers[mgrName]
		if !ok || !rm.Usable() {
			continue
		}
		set := e.installedSet(ctx, rm)
		for _, req := range def.Requires[mgrName] {
			if set[rm.Key(req)] {
				continue
			}
			fmt.Fprintf(e.Log, "→ installing %s (required by %s) with %s\n", req, st.Package, mgrName)
			if err := rm.Install(ctx, manifest.Entry{Name: req}); err != nil {
				return fmt.Errorf("%s requires %s: %w", st.Package, req, err)
			}
			e.markInstalled(rm, req)
		}
	}
	fmt.Fprintf(e.Log, "→ installing %s with %s\n", st.Package, m.Name())
	if err := m.Install(ctx, entry); err != nil {
		return err
	}
	e.markInstalled(m, entry.Name)
	return nil
}

// Uninstall removes an installed package from this machine.
func (e *Engine) Uninstall(ctx context.Context, st PackageState) error {
	if st.Status != StatusOK {
		return nil
	}
	fmt.Fprintf(e.Log, "→ uninstalling %s with %s\n", st.Package, st.Manager)
	if err := st.manager.Uninstall(ctx, st.entry); err != nil {
		return err
	}
	e.markRemoved(st.manager, st.entry.Name)
	return nil
}

// Upgrade upgrades every installed profile package, grouped by manager.
func (e *Engine) Upgrade(ctx context.Context, rep *Report, only map[string]bool) error {
	groups := map[string][]manifest.Entry{}
	for _, p := range rep.Packages {
		if p.Status != StatusOK || (len(only) > 0 && !only[p.Package]) {
			continue
		}
		groups[p.Manager] = append(groups[p.Manager], p.entry)
	}
	var errs []error
	for _, m := range e.Usable() {
		if es := groups[m.Name()]; len(es) > 0 {
			fmt.Fprintf(e.Log, "→ upgrading %d package(s) with %s\n", len(es), m.Name())
			if err := m.Upgrade(ctx, es); err != nil {
				errs = append(errs, fmt.Errorf("%s: %w", m.Name(), err))
			}
		}
	}
	return errors.Join(errs...)
}

var invalidChars = regexp.MustCompile(`[^a-z0-9._+-]+`)

// AdoptName maps a manager-native name to a package name, plus the catalog
// entry that must be written for it (nil when the implied definition works).
func (e *Engine) AdoptName(manager, native string) (string, *manifest.Entry) {
	if pkg, ok := e.M.FindByNative(manager, native); ok {
		return pkg, nil
	}
	slug := func(s string) string {
		s = invalidChars.ReplaceAllString(strings.ToLower(s), "-")
		return strings.Trim(s, "-.")
	}
	switch manager {
	case manifest.Brew:
		pkg := slug(path.Base(native))
		if strings.Contains(native, "/") || pkg != native {
			return pkg, &manifest.Entry{Name: native}
		}
		return pkg, nil
	case manifest.Winget:
		parts := strings.Split(native, ".")
		pkg := slug(parts[len(parts)-1])
		if d, ok := e.M.Catalog[pkg]; ok {
			if _, has := d.Entries[manifest.Winget]; has {
				pkg = slug(native)
			}
		}
		return pkg, &manifest.Entry{Name: native}
	case manifest.Npm:
		return slug(path.Base(native)), &manifest.Entry{Name: native}
	default:
		pkg := slug(native)
		if pkg != native {
			return pkg, &manifest.Entry{Name: native}
		}
		return pkg, nil
	}
}

func sortedKeys(m map[string][]string) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
