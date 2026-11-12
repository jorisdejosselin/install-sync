// Package migrate converts a v0 config.json (per-machine install log) into a
// v1 manifest: a catalog plus one profile per old machine.
package migrate

import (
	"encoding/json"
	"fmt"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/jorisdejosselin/install-sync/internal/manifest"
)

type v0Config struct {
	Machines map[string]struct {
		MachineName string `json:"machine_name"`
		OSType      string `json:"os_type"`
	} `json:"machines"`
	Packages map[string][]struct {
		Name           string `json:"name"`
		PackageManager string `json:"package_manager"`
	} `json:"packages"`
	// v0.11 additions.
	AptRepos map[string]struct {
		GPGKeyURL    string `json:"gpg_key_url"`
		RepoURL      string `json:"repo_url"`
		Distribution string `json:"distribution"`
		Components   string `json:"components"`
		Architecture string `json:"architecture"`
	} `json:"apt_repos"`
	ScriptPackages map[string]struct {
		Install   string `json:"install_cmd"`
		Uninstall string `json:"uninstall_cmd"`
		Check     string `json:"check_cmd"`
	} `json:"script_packages"`
}

// Result describes what Run produced.
type Result struct {
	Profiles map[string][]string // profile -> packages
	Catalog  map[string]manifest.Definition
	Notes    []string
}

var invalid = regexp.MustCompile(`[^a-z0-9._+-]+`)

func slug(s string) string {
	return strings.Trim(invalid.ReplaceAllString(strings.ToLower(s), "-"), "-.")
}

// Convert turns v0 data into profiles and a catalog without touching disk.
func Convert(data []byte) (*Result, error) {
	var old v0Config
	if err := json.Unmarshal(data, &old); err != nil {
		return nil, fmt.Errorf("not a v0 config.json: %w", err)
	}
	res := &Result{Profiles: map[string][]string{}, Catalog: map[string]manifest.Definition{}}
	ids := make([]string, 0, len(old.Packages))
	for id := range old.Packages {
		ids = append(ids, id)
	}
	sort.Strings(ids)

	for _, id := range ids {
		mach := old.Machines[id]
		profile := slug(mach.MachineName + "-" + mach.OSType)
		if mach.MachineName == "" {
			profile = slug("machine-" + id)
		}
		seen := map[string]bool{}
		for _, p := range old.Packages[id] {
			pkg, entry, note := convertOne(p.Name, p.PackageManager)
			if pkg == "" {
				res.Notes = append(res.Notes, note)
				continue
			}
			if note != "" {
				res.Notes = append(res.Notes, note)
			}
			if entry != nil {
				def := res.Catalog[pkg]
				if def.Entries == nil {
					def.Entries = map[string]manifest.Entry{}
				}
				def.Entries[p.PackageManager] = *entry
				res.Catalog[pkg] = def
			}
			if !seen[pkg] {
				res.Profiles[profile] = append(res.Profiles[profile], pkg)
				seen[pkg] = true
			}
		}
	}
	applyV011(&old, res)
	return res, nil
}

// applyV011 carries over apt repos and script definitions stored by v0.11.
func applyV011(old *v0Config, res *Result) {
	setEntry := func(pkg, mgr string, e manifest.Entry) {
		def := res.Catalog[pkg]
		if def.Entries == nil {
			def.Entries = map[string]manifest.Entry{}
		}
		def.Entries[mgr] = e
		res.Catalog[pkg] = def
	}
	for name, r := range old.AptRepos {
		pkg := slug(name)
		dist := r.Distribution
		if dist == "" {
			dist = "{codename}"
		}
		comps := r.Components
		if comps == "" {
			comps = "main"
		}
		arch := r.Architecture
		if arch == "" {
			arch = "{arch}"
		}
		e := res.Catalog[pkg].Entries[manifest.Apt]
		if pkg != name {
			e.Name = name
		}
		e.Repo = &manifest.AptRepo{
			Key:    r.GPGKeyURL,
			Source: fmt.Sprintf("deb [arch=%s signed-by={keyring}] %s %s %s", arch, r.RepoURL, dist, comps),
		}
		setEntry(pkg, manifest.Apt, e)
	}
	for name, sp := range old.ScriptPackages {
		pkg := slug(name)
		e := manifest.Entry{Install: sp.Install, Check: sp.Check, Uninstall: sp.Uninstall}
		if e.Install == "" {
			e.Install = fmt.Sprintf("echo 'TODO: write the install script for %s' >&2; exit 1", pkg)
		}
		if e.Check == "" {
			e.Check = "command -v " + pkg
			res.Notes = append(res.Notes, fmt.Sprintf("%s had no check command; using `command -v %s`", pkg, pkg))
		}
		setEntry(pkg, manifest.Script, e)
		// The placeholder note for this script install no longer applies.
		kept := res.Notes[:0]
		for _, n := range res.Notes {
			if !strings.HasPrefix(n, pkg+" was a script install") {
				kept = append(kept, n)
			}
		}
		res.Notes = kept
	}
}

func convertOne(name, mgr string) (string, *manifest.Entry, string) {
	if !manifest.IsKnownManager(mgr) {
		return "", nil, fmt.Sprintf("skipped %s: unknown package manager %q", name, mgr)
	}
	switch mgr {
	case manifest.Brew:
		pkg := slug(path.Base(name))
		if pkg != name {
			return pkg, &manifest.Entry{Name: name}, ""
		}
		return pkg, nil, ""
	case manifest.Winget:
		parts := strings.Split(name, ".")
		pkg := slug(parts[len(parts)-1])
		if len(parts) == 1 {
			// v0 sometimes stored a plain name for winget; keep it as an id.
			return pkg, &manifest.Entry{Name: name}, fmt.Sprintf("check winget id for %s: %q is not Publisher.Name", pkg, name)
		}
		return pkg, &manifest.Entry{Name: name}, ""
	case manifest.Npm:
		return slug(path.Base(name)), &manifest.Entry{Name: name}, ""
	case manifest.Script:
		pkg := slug(name)
		return pkg, &manifest.Entry{
				Install: fmt.Sprintf("echo 'TODO: write the install script for %s' >&2; exit 1", pkg),
				Check:   "command -v " + pkg,
			},
			fmt.Sprintf("%s was a script install: fill in its install command in %s", pkg, manifest.CatalogFile)
	default:
		pkg := slug(name)
		// apt and snap: the implied definition finds them by name (and
		// detects classic snaps), so no entry is needed.
		if pkg != name {
			return pkg, &manifest.Entry{Name: name}, ""
		}
		return pkg, nil, ""
	}
}

// Write creates the manifest folder. It refuses to overwrite existing files.
func Write(dir string, r *Result) error {
	if err := os.MkdirAll(filepath.Join(dir, manifest.ProfilesDir), 0o755); err != nil {
		return err
	}
	for name := range r.Profiles {
		if _, err := os.Stat(manifest.ProfilePath(dir, name)); err == nil {
			return fmt.Errorf("%s already exists", manifest.ProfilePath(dir, name))
		}
	}
	if _, err := os.Stat(filepath.Join(dir, manifest.CatalogFile)); err == nil {
		return fmt.Errorf("%s already exists", filepath.Join(dir, manifest.CatalogFile))
	}
	for name, pkgs := range r.Profiles {
		if err := manifest.CreateProfile(dir, name, nil); err != nil {
			return err
		}
		if _, err := manifest.AddPackages(dir, name, pkgs...); err != nil {
			return err
		}
	}
	pkgNames := make([]string, 0, len(r.Catalog))
	for k := range r.Catalog {
		pkgNames = append(pkgNames, k)
	}
	sort.Strings(pkgNames)
	for _, pkg := range pkgNames {
		def := r.Catalog[pkg]
		for _, mgr := range manifest.KnownManagers {
			if e, ok := def.Entries[mgr]; ok {
				if err := manifest.SetEntry(dir, pkg, mgr, e); err != nil {
					return err
				}
			}
		}
	}
	if len(pkgNames) == 0 {
		return os.WriteFile(filepath.Join(dir, manifest.CatalogFile), []byte("packages: {}\n"), 0o644)
	}
	return nil
}
