// Package machine handles the machine-local, untracked machine config.
package machine

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"go.yaml.in/yaml/v3"
)

// Config is the machine config: which profile this machine applies and where
// the manifest lives.
type Config struct {
	Profile  string `yaml:"profile" json:"profile"`
	Manifest string `yaml:"manifest" json:"manifest"`
	// Managers overrides the default manager order for this machine.
	Managers []string `yaml:"managers,omitempty" json:"managers,omitempty"`
	Git      GitOpts  `yaml:"git,omitempty" json:"git"`
}

// GitOpts controls git behaviour for the manifest repo.
type GitOpts struct {
	// Push after commits. Defaults to true when unset.
	Push *bool `yaml:"push,omitempty" json:"push,omitempty"`
}

// PushEnabled reports whether changes should be pushed.
func (c *Config) PushEnabled() bool { return c.Git.Push == nil || *c.Git.Push }

// ErrNotInitialised is returned when no machine config exists.
var ErrNotInitialised = errors.New("this machine has no install-sync config; run `install-sync init --repo <url> --profile <name>`")

// ConfigPath returns where the machine config lives.
func ConfigPath() (string, error) {
	if p := os.Getenv("INSTALL_SYNC_CONFIG"); p != "" {
		return Expand(p)
	}
	if x := os.Getenv("XDG_CONFIG_HOME"); x != "" {
		return filepath.Join(x, "install-sync", "config.yaml"), nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".config", "install-sync", "config.yaml"), nil
}

// DefaultManifestDir is where `init --repo` clones the manifest.
func DefaultManifestDir() (string, error) {
	if x := os.Getenv("XDG_DATA_HOME"); x != "" {
		return filepath.Join(x, "install-sync", "manifest"), nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".local", "share", "install-sync", "manifest"), nil
}

// Expand resolves a leading ~ and makes the path absolute.
func Expand(p string) (string, error) {
	if p == "~" || strings.HasPrefix(p, "~/") || strings.HasPrefix(p, `~\`) {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		p = filepath.Join(home, p[1:])
	}
	return filepath.Abs(p)
}

// Load reads the machine config.
func Load() (*Config, string, error) {
	path, err := ConfigPath()
	if err != nil {
		return nil, "", err
	}
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, path, ErrNotInitialised
	}
	if err != nil {
		return nil, path, err
	}
	var c Config
	dec := yaml.NewDecoder(bytes.NewReader(data))
	dec.KnownFields(true)
	if err := dec.Decode(&c); err != nil {
		return nil, path, fmt.Errorf("%s: %w", path, err)
	}
	if c.Profile == "" || c.Manifest == "" {
		return nil, path, fmt.Errorf("%s: both profile and manifest must be set", path)
	}
	if c.Manifest, err = Expand(c.Manifest); err != nil {
		return nil, path, err
	}
	return &c, path, nil
}

// Save writes the machine config to path.
func Save(path string, c *Config) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	var buf bytes.Buffer
	buf.WriteString("# install-sync machine config (machine-local, not tracked in the manifest)\n")
	enc := yaml.NewEncoder(&buf)
	enc.SetIndent(2)
	if err := enc.Encode(c); err != nil {
		return err
	}
	return os.WriteFile(path, buf.Bytes(), 0o644)
}

// DefaultOrder is the built-in manager order for an OS.
func DefaultOrder(goos string) []string {
	switch goos {
	case "darwin":
		return []string{"brew"}
	case "windows":
		return []string{"winget"}
	default:
		return []string{"apt", "snap", "script"}
	}
}

// Order returns the effective manager order for this machine. npm is always
// considered last unless the machine config places it explicitly.
func (c *Config) Order(goos string) []string {
	order := c.Managers
	if len(order) == 0 {
		order = DefaultOrder(goos)
	}
	out := append([]string(nil), order...)
	for _, m := range out {
		if m == "npm" {
			return out
		}
	}
	return append(out, "npm")
}
