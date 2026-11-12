// Package manifest loads, validates and edits the desired-state manifest:
// a catalog of definitions (packages.yaml) and a folder of profiles.
package manifest

import (
	"fmt"
	"sort"
	"strings"

	"go.yaml.in/yaml/v3"
)

// Package manager names known to install-sync.
const (
	Brew   = "brew"
	Apt    = "apt"
	Winget = "winget"
	Snap   = "snap"
	Npm    = "npm"
	Script = "script"
)

// KnownManagers lists every supported package manager.
var KnownManagers = []string{Brew, Apt, Winget, Snap, Npm, Script}

// IsKnownManager reports whether name is a supported package manager.
func IsKnownManager(name string) bool {
	for _, m := range KnownManagers {
		if m == name {
			return true
		}
	}
	return false
}

// AptRepo describes an apt repository that must be configured before the
// package can be installed. Source may use the placeholders {arch},
// {codename} and {keyring}.
type AptRepo struct {
	Key    string `yaml:"key" json:"key"`
	Source string `yaml:"source" json:"source"`
}

// Entry is how one package is installed with one package manager.
type Entry struct {
	Name string `yaml:"name,omitempty" json:"name,omitempty"`
	// Cask marks a brew cask.
	Cask bool `yaml:"cask,omitempty" json:"cask,omitempty"`
	// Classic installs a snap with --classic confinement.
	Classic bool `yaml:"classic,omitempty" json:"classic,omitempty"`
	// Repo is an apt repository to configure first.
	Repo *AptRepo `yaml:"repo,omitempty" json:"repo,omitempty"`
	// Script fields.
	Install   string `yaml:"install,omitempty" json:"install,omitempty"`
	Check     string `yaml:"check,omitempty" json:"check,omitempty"`
	Uninstall string `yaml:"uninstall,omitempty" json:"uninstall,omitempty"`
	Upgrade   string `yaml:"upgrade,omitempty" json:"upgrade,omitempty"`
}

// UnmarshalYAML accepts either a plain string (the manager-specific name) or
// a mapping.
func (e *Entry) UnmarshalYAML(n *yaml.Node) error {
	if n.Kind == yaml.ScalarNode {
		e.Name = n.Value
		return nil
	}
	type plain Entry
	var p plain
	if err := n.Decode(&p); err != nil {
		return err
	}
	*e = Entry(p)
	return nil
}

// MarshalYAML writes the short string form when only a name is set.
func (e Entry) MarshalYAML() (interface{}, error) {
	if e.Name != "" && !e.Cask && !e.Classic && e.Repo == nil &&
		e.Install == "" && e.Check == "" && e.Uninstall == "" && e.Upgrade == "" {
		return e.Name, nil
	}
	type plain Entry
	return plain(e), nil
}

// Definition describes how to install one package with each package manager.
type Definition struct {
	Description string `json:"description,omitempty"`
	// Entries maps package manager name to entry.
	Entries map[string]Entry `json:"entries"`
	// Requires maps package manager name to manager-native names that must be
	// installed first (only where that manager is usable).
	Requires map[string][]string `json:"requires,omitempty"`
}

// UnmarshalYAML decodes the flat mapping form used in packages.yaml.
func (d *Definition) UnmarshalYAML(n *yaml.Node) error {
	if n.Kind != yaml.MappingNode {
		return fmt.Errorf("line %d: definition must be a mapping", n.Line)
	}
	d.Entries = map[string]Entry{}
	for i := 0; i+1 < len(n.Content); i += 2 {
		key, val := n.Content[i].Value, n.Content[i+1]
		switch key {
		case "description":
			d.Description = val.Value
		case "requires":
			if err := val.Decode(&d.Requires); err != nil {
				return fmt.Errorf("line %d: requires: %w", val.Line, err)
			}
		default:
			if !IsKnownManager(key) {
				return fmt.Errorf("line %d: unknown package manager %q (known: %s)",
					n.Content[i].Line, key, strings.Join(KnownManagers, ", "))
			}
			var e Entry
			if err := val.Decode(&e); err != nil {
				return fmt.Errorf("line %d: %s: %w", val.Line, key, err)
			}
			d.Entries[key] = e
		}
	}
	return nil
}

// MarshalYAML writes the flat mapping form, managers in a stable order.
func (d Definition) MarshalYAML() (interface{}, error) {
	n := &yaml.Node{Kind: yaml.MappingNode}
	add := func(k string, v interface{}) error {
		var vn yaml.Node
		if err := vn.Encode(v); err != nil {
			return err
		}
		n.Content = append(n.Content, &yaml.Node{Kind: yaml.ScalarNode, Value: k}, &vn)
		return nil
	}
	if d.Description != "" {
		if err := add("description", d.Description); err != nil {
			return nil, err
		}
	}
	for _, m := range KnownManagers {
		if e, ok := d.Entries[m]; ok {
			if err := add(m, e); err != nil {
				return nil, err
			}
		}
	}
	if len(d.Requires) > 0 {
		if err := add("requires", d.Requires); err != nil {
			return nil, err
		}
	}
	return n, nil
}

// Profile is a named, reusable set of desired packages.
type Profile struct {
	Name        string   `yaml:"-" json:"name"`
	Description string   `yaml:"description,omitempty" json:"description,omitempty"`
	Include     []string `yaml:"include,omitempty" json:"include,omitempty"`
	Packages    []string `yaml:"packages" json:"packages"`
}

// Has reports whether the profile itself (not its includes) lists pkg.
func (p *Profile) Has(pkg string) bool {
	for _, x := range p.Packages {
		if x == pkg {
			return true
		}
	}
	return false
}

// Manifest is a loaded manifest folder.
type Manifest struct {
	Dir      string
	Catalog  map[string]Definition
	Profiles map[string]*Profile
}

// ProfileNames returns profile names sorted.
func (m *Manifest) ProfileNames() []string {
	names := make([]string, 0, len(m.Profiles))
	for n := range m.Profiles {
		names = append(names, n)
	}
	sort.Strings(names)
	return names
}

// Resolved is a package wanted by a profile, with the profiles that list it.
type Resolved struct {
	Package string   `json:"package"`
	From    []string `json:"from"`
}

// Resolve expands a profile and its includes into an ordered, de-duplicated
// package list (includes first, depth-first).
func (m *Manifest) Resolve(profile string) ([]Resolved, error) {
	if _, ok := m.Profiles[profile]; !ok {
		return nil, fmt.Errorf("profile %q not found (available: %s)", profile, strings.Join(m.ProfileNames(), ", "))
	}
	var order []string
	from := map[string][]string{}
	visited := map[string]bool{}
	var walk func(name string, stack []string) error
	walk = func(name string, stack []string) error {
		for _, s := range stack {
			if s == name {
				return fmt.Errorf("include cycle: %s -> %s", strings.Join(stack, " -> "), name)
			}
		}
		if visited[name] {
			return nil
		}
		p, ok := m.Profiles[name]
		if !ok {
			return fmt.Errorf("profile %q includes unknown profile %q", stack[len(stack)-1], name)
		}
		stack = append(stack, name)
		for _, inc := range p.Include {
			if err := walk(inc, stack); err != nil {
				return err
			}
		}
		visited[name] = true
		for _, pkg := range p.Packages {
			if _, seen := from[pkg]; !seen {
				order = append(order, pkg)
			}
			from[pkg] = append(from[pkg], name)
		}
		return nil
	}
	if err := walk(profile, nil); err != nil {
		return nil, err
	}
	out := make([]Resolved, 0, len(order))
	for _, pkg := range order {
		out = append(out, Resolved{Package: pkg, From: from[pkg]})
	}
	return out, nil
}

// IncludedBy returns the profiles that directly include name.
func (m *Manifest) IncludedBy(name string) []string {
	var out []string
	for _, n := range m.ProfileNames() {
		for _, inc := range m.Profiles[n].Include {
			if inc == name {
				out = append(out, n)
			}
		}
	}
	return out
}

// Definition returns the catalog definition for pkg, or an empty implied one.
func (m *Manifest) Definition(pkg string) (Definition, bool) {
	d, ok := m.Catalog[pkg]
	if !ok {
		return Definition{Entries: map[string]Entry{}}, false
	}
	return d, true
}

// FindByNative returns the package whose definition uses native as its name
// for manager, if any.
func (m *Manifest) FindByNative(manager, native string) (string, bool) {
	for _, pkg := range sortedKeys(m.Catalog) {
		if e, ok := m.Catalog[pkg].Entries[manager]; ok && strings.EqualFold(e.Name, native) {
			return pkg, true
		}
	}
	return "", false
}

func sortedKeys(c map[string]Definition) []string {
	keys := make([]string, 0, len(c))
	for k := range c {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
