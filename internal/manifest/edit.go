package manifest

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"go.yaml.in/yaml/v3"
)

// Edits work on the YAML node tree so comments and ordering written by hand
// survive.

// ProfilePath returns the file path of a profile.
func ProfilePath(dir, profile string) string {
	return filepath.Join(dir, ProfilesDir, profile+".yaml")
}

// AddPackages appends packages to a profile file. Packages already listed are
// skipped. It returns the packages actually added.
func AddPackages(dir, profile string, pkgs ...string) ([]string, error) {
	path := ProfilePath(dir, profile)
	doc, err := readDoc(path, false)
	if err != nil {
		return nil, err
	}
	seq := ensureSeq(doc.Content[0], "packages")
	if len(seq.Content) == 0 {
		seq.Style = 0 // turn an empty `[]` into a block list
	}
	var added []string
	for _, pkg := range pkgs {
		if seqHas(seq, pkg) {
			continue
		}
		seq.Content = append(seq.Content, &yaml.Node{Kind: yaml.ScalarNode, Value: pkg})
		added = append(added, pkg)
	}
	if len(added) == 0 {
		return nil, nil
	}
	return added, writeDoc(path, doc)
}

// RemovePackage removes pkg from a profile file. It reports whether it was there.
func RemovePackage(dir, profile, pkg string) (bool, error) {
	path := ProfilePath(dir, profile)
	doc, err := readDoc(path, false)
	if err != nil {
		return false, err
	}
	seq := mapGet(doc.Content[0], "packages")
	if seq == nil || seq.Kind != yaml.SequenceNode {
		return false, nil
	}
	found := false
	kept := seq.Content[:0]
	for _, n := range seq.Content {
		if n.Value == pkg {
			found = true
			continue
		}
		kept = append(kept, n)
	}
	seq.Content = kept
	if !found {
		return false, nil
	}
	return true, writeDoc(path, doc)
}

// CreateProfile writes a new, empty profile file.
func CreateProfile(dir, name string, include []string) error {
	if !ValidProfileName(name) {
		return fmt.Errorf("invalid profile name %q", name)
	}
	path := ProfilePath(dir, name)
	if _, err := os.Stat(path); err == nil {
		return fmt.Errorf("profile %q already exists", name)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	p := Profile{Include: include, Packages: []string{}}
	var buf bytes.Buffer
	enc := yaml.NewEncoder(&buf)
	enc.SetIndent(2)
	if err := enc.Encode(p); err != nil {
		return err
	}
	return os.WriteFile(path, buf.Bytes(), 0o644)
}

// SetEntry adds or replaces one package manager entry in a package's
// definition in packages.yaml, creating the file or definition if needed.
func SetEntry(dir, pkg, manager string, e Entry) error {
	if !IsKnownManager(manager) {
		return fmt.Errorf("unknown package manager %q", manager)
	}
	path := filepath.Join(dir, CatalogFile)
	doc, err := readDoc(path, true)
	if err != nil {
		return err
	}
	pkgs := ensureMap(doc.Content[0], "packages")
	def := ensureMap(pkgs, pkg)
	var vn yaml.Node
	if err := vn.Encode(e); err != nil {
		return err
	}
	if existing := mapGet(def, manager); existing != nil {
		*existing = vn
	} else {
		def.Content = append(def.Content, &yaml.Node{Kind: yaml.ScalarNode, Value: manager}, &vn)
	}
	return writeDoc(path, doc)
}

func readDoc(path string, createIfMissing bool) (*yaml.Node, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) && createIfMissing {
		data = nil
	} else if err != nil {
		return nil, err
	}
	var doc yaml.Node
	if len(bytes.TrimSpace(data)) > 0 {
		if err := yaml.Unmarshal(data, &doc); err != nil {
			return nil, fmt.Errorf("%s: %w", path, err)
		}
	}
	if doc.Kind == 0 {
		doc = yaml.Node{Kind: yaml.DocumentNode, Content: []*yaml.Node{{Kind: yaml.MappingNode}}}
	}
	if len(doc.Content) == 0 || doc.Content[0].Kind != yaml.MappingNode {
		return nil, fmt.Errorf("%s: top level must be a mapping", path)
	}
	return &doc, nil
}

func writeDoc(path string, doc *yaml.Node) error {
	var buf bytes.Buffer
	enc := yaml.NewEncoder(&buf)
	enc.SetIndent(2)
	if err := enc.Encode(doc); err != nil {
		return err
	}
	if err := enc.Close(); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, buf.Bytes(), 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func mapGet(m *yaml.Node, key string) *yaml.Node {
	for i := 0; i+1 < len(m.Content); i += 2 {
		if m.Content[i].Value == key {
			return m.Content[i+1]
		}
	}
	return nil
}

func ensureMap(m *yaml.Node, key string) *yaml.Node {
	if v := mapGet(m, key); v != nil {
		if v.Kind != yaml.MappingNode {
			*v = yaml.Node{Kind: yaml.MappingNode}
		}
		return v
	}
	v := &yaml.Node{Kind: yaml.MappingNode}
	m.Content = append(m.Content, &yaml.Node{Kind: yaml.ScalarNode, Value: key}, v)
	return v
}

func ensureSeq(m *yaml.Node, key string) *yaml.Node {
	if v := mapGet(m, key); v != nil {
		if v.Kind != yaml.SequenceNode {
			*v = yaml.Node{Kind: yaml.SequenceNode}
		}
		return v
	}
	v := &yaml.Node{Kind: yaml.SequenceNode}
	m.Content = append(m.Content, &yaml.Node{Kind: yaml.ScalarNode, Value: key}, v)
	return v
}

func seqHas(seq *yaml.Node, v string) bool {
	for _, n := range seq.Content {
		if n.Value == v {
			return true
		}
	}
	return false
}
