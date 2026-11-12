package manifest

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"go.yaml.in/yaml/v3"
)

// File and folder names inside a manifest.
const (
	CatalogFile = "packages.yaml"
	ProfilesDir = "profiles"
)

var nameRe = regexp.MustCompile(`^[a-z0-9][a-z0-9._+-]*$`)

// ValidProfileName reports whether name can be used as a profile name.
func ValidProfileName(name string) bool { return nameRe.MatchString(name) }

type catalogFile struct {
	Packages map[string]Definition `yaml:"packages"`
}

// Load reads and validates the manifest in dir.
func Load(dir string) (*Manifest, error) {
	m := &Manifest{Dir: dir, Catalog: map[string]Definition{}, Profiles: map[string]*Profile{}}

	data, err := os.ReadFile(filepath.Join(dir, CatalogFile))
	switch {
	case errors.Is(err, os.ErrNotExist):
		// An empty catalog is fine: every package then uses its implied definition.
	case err != nil:
		return nil, err
	default:
		var cf catalogFile
		if err := strictUnmarshal(data, &cf); err != nil {
			return nil, fmt.Errorf("%s: %w", CatalogFile, err)
		}
		if cf.Packages != nil {
			m.Catalog = cf.Packages
		}
	}

	entries, err := os.ReadDir(filepath.Join(dir, ProfilesDir))
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, fmt.Errorf("%s is not a manifest: no %s/ folder", dir, ProfilesDir)
		}
		return nil, err
	}
	for _, e := range entries {
		name := e.Name()
		if e.IsDir() || !(strings.HasSuffix(name, ".yaml") || strings.HasSuffix(name, ".yml")) {
			continue
		}
		pname := strings.TrimSuffix(strings.TrimSuffix(name, ".yaml"), ".yml")
		data, err := os.ReadFile(filepath.Join(dir, ProfilesDir, name))
		if err != nil {
			return nil, err
		}
		p := &Profile{}
		if err := strictUnmarshal(data, p); err != nil {
			return nil, fmt.Errorf("%s/%s: %w", ProfilesDir, name, err)
		}
		p.Name = pname
		if _, dup := m.Profiles[pname]; dup {
			return nil, fmt.Errorf("profile %q is defined twice", pname)
		}
		m.Profiles[pname] = p
	}

	if err := m.Validate(); err != nil {
		return nil, err
	}
	return m, nil
}

func strictUnmarshal(data []byte, v interface{}) error {
	if len(bytes.TrimSpace(data)) == 0 {
		return nil
	}
	dec := yaml.NewDecoder(bytes.NewReader(data))
	dec.KnownFields(true)
	return dec.Decode(v)
}

// Validate checks the whole manifest and returns all problems at once.
func (m *Manifest) Validate() error {
	var problems []string
	add := func(format string, a ...interface{}) { problems = append(problems, fmt.Sprintf(format, a...)) }

	for _, pkg := range sortedKeys(m.Catalog) {
		d := m.Catalog[pkg]
		if !nameRe.MatchString(pkg) {
			add("package %q: names must be lowercase letters, digits and . _ + -", pkg)
		}
		if len(d.Entries) == 0 {
			add("package %q: definition lists no package manager", pkg)
		}
		for mgr, e := range d.Entries {
			if e.Cask && mgr != Brew {
				add("package %q: cask is only valid for brew", pkg)
			}
			if e.Classic && mgr != Snap {
				add("package %q: classic is only valid for snap", pkg)
			}
			if e.Repo != nil {
				if mgr != Apt {
					add("package %q: repo is only valid for apt", pkg)
				} else if e.Repo.Key == "" || e.Repo.Source == "" {
					add("package %q: apt repo needs both key and source", pkg)
				}
			}
			isScript := e.Install != "" || e.Check != "" || e.Uninstall != "" || e.Upgrade != ""
			if mgr == Script {
				if e.Install == "" || e.Check == "" {
					add("package %q: script needs both install and check", pkg)
				}
			} else if isScript {
				add("package %q: install/check/uninstall/upgrade are only valid for script", pkg)
			}
		}
		for mgr, names := range d.Requires {
			if !IsKnownManager(mgr) || mgr == Script {
				add("package %q: requires: unsupported package manager %q", pkg, mgr)
			}
			if len(names) == 0 {
				add("package %q: requires.%s is empty", pkg, mgr)
			}
		}
	}

	for _, name := range m.ProfileNames() {
		p := m.Profiles[name]
		if !ValidProfileName(name) {
			add("profile %q: names must be lowercase letters, digits and . _ + -", name)
		}
		seen := map[string]bool{}
		for _, pkg := range p.Packages {
			if !nameRe.MatchString(pkg) {
				add("profile %q: invalid package name %q", name, pkg)
			}
			if seen[pkg] {
				add("profile %q: %q is listed twice", name, pkg)
			}
			seen[pkg] = true
		}
		for _, inc := range p.Include {
			if _, ok := m.Profiles[inc]; !ok {
				add("profile %q: includes unknown profile %q", name, inc)
			}
		}
	}
	if len(problems) == 0 {
		for _, name := range m.ProfileNames() {
			if _, err := m.Resolve(name); err != nil {
				add("%v", err)
			}
		}
	}
	if len(problems) > 0 {
		sort.Strings(problems)
		return fmt.Errorf("invalid manifest in %s:\n  - %s", m.Dir, strings.Join(problems, "\n  - "))
	}
	return nil
}
