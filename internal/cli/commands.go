package cli

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/cobra"

	"github.com/jorisdejosselin/install-sync/internal/engine"
	"github.com/jorisdejosselin/install-sync/internal/gitrepo"
	"github.com/jorisdejosselin/install-sync/internal/machine"
	"github.com/jorisdejosselin/install-sync/internal/manifest"
	"github.com/jorisdejosselin/install-sync/internal/migrate"
)

// ---- init ----

func (a *app) initCmd() *cobra.Command {
	var repoURL, profile, dir, local string
	var include []string
	var create, force bool
	cmd := &cobra.Command{
		Use:   "init --repo <url> --profile <name>",
		Short: "Set up this machine: clone the manifest and choose its profile",
		Example: `  install-sync init --repo git@gitlab.com:me/my-software.git --profile work
  install-sync init --manifest ~/src/my-software --profile personal
  install-sync init --repo <url> --profile work-desktop --create`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			ctx := cmd.Context()
			if profile == "" {
				return errors.New("--profile is required")
			}
			if (repoURL == "") == (local == "") {
				return errors.New("give exactly one of --repo <url> or --manifest <folder>")
			}
			cfgPath, err := machine.ConfigPath()
			if err != nil {
				return err
			}
			// A config that names the same profile (e.g. written by chezmoi before
			// the first init) is reused: init then only clones the manifest.
			var existing *machine.Config
			if cfg, _, err := machine.Load(); err == nil {
				if cfg.Profile != profile && !force {
					return fmt.Errorf("this machine is already set up for profile %q (manifest %s); use --force to switch to %q",
						cfg.Profile, cfg.Manifest, profile)
				}
				existing = cfg
				if dir == "" && local == "" {
					dir = cfg.Manifest
				}
			}

			var manifestDir string
			if local != "" {
				if manifestDir, err = machine.Expand(local); err != nil {
					return err
				}
			} else {
				if dir == "" {
					if dir, err = machine.DefaultManifestDir(); err != nil {
						return err
					}
				}
				if manifestDir, err = machine.Expand(dir); err != nil {
					return err
				}
				repo := gitrepo.Repo{Dir: manifestDir, R: a.Runner}
				if _, statErr := os.Stat(manifestDir); statErr == nil {
					if !repo.IsRepo(ctx) {
						return fmt.Errorf("%s exists and is not a git repo; pick another --dir", manifestDir)
					}
					a.logf("✓ using existing clone in %s", manifestDir)
					if _, err := repo.Pull(ctx); err != nil {
						a.logf("! could not pull: %v", err)
					}
				} else {
					if err := os.MkdirAll(filepath.Dir(manifestDir), 0o755); err != nil {
						return err
					}
					a.logf("→ cloning %s into %s", repoURL, manifestDir)
					if err := gitrepo.Clone(ctx, a.Runner, repoURL, manifestDir); err != nil {
						return err
					}
				}
			}

			created := false
			if _, err := os.Stat(filepath.Join(manifestDir, manifest.ProfilesDir)); os.IsNotExist(err) {
				if !create {
					return fmt.Errorf("%s has no %s/ folder; pass --create to start a new manifest there", manifestDir, manifest.ProfilesDir)
				}
				if err := os.MkdirAll(filepath.Join(manifestDir, manifest.ProfilesDir), 0o755); err != nil {
					return err
				}
				if err := os.WriteFile(filepath.Join(manifestDir, manifest.CatalogFile), []byte("packages: {}\n"), 0o644); err != nil {
					return err
				}
				created = true
			}
			m, err := manifest.Load(manifestDir)
			if err != nil {
				return err
			}
			if _, ok := m.Profiles[profile]; !ok {
				if !create {
					return fmt.Errorf("profile %q is not in the manifest (available: %s); pass --create to make it",
						profile, strings.Join(m.ProfileNames(), ", "))
				}
				for _, inc := range include {
					if _, ok := m.Profiles[inc]; !ok {
						return fmt.Errorf("--include %q: no such profile", inc)
					}
				}
				if err := manifest.CreateProfile(manifestDir, profile, include); err != nil {
					return err
				}
				a.logf("✓ created profile %s", profile)
				created = true
			}

			cfg := &machine.Config{Profile: profile, Manifest: manifestDir}
			if existing != nil && existing.Profile == profile && existing.Manifest == manifestDir {
				a.logf("✓ keeping the existing machine config (%s)", cfgPath)
				cfg = existing
			} else if err := machine.Save(cfgPath, cfg); err != nil {
				return err
			} else {
				a.logf("✓ this machine applies profile %q (config: %s)", profile, cfgPath)
			}
			if created {
				a.commit(ctx, &session{cfg: cfg, repo: gitrepo.Repo{Dir: manifestDir, R: a.Runner}}, profile+": create profile")
			}
			a.logf("next: `install-sync diff` to see what is missing, `install-sync apply` to install it")
			return nil
		},
	}
	f := cmd.Flags()
	f.StringVar(&repoURL, "repo", "", "git URL of the manifest repo to clone")
	f.StringVar(&local, "manifest", "", "use an existing local manifest folder instead of cloning")
	f.StringVar(&dir, "dir", "", "where to clone the manifest (default ~/.local/share/install-sync/manifest)")
	f.StringVar(&profile, "profile", "", "profile this machine applies")
	f.BoolVar(&create, "create", false, "create the profile (and manifest layout) if missing")
	f.StringSliceVar(&include, "include", nil, "profiles a newly created profile includes")
	f.BoolVar(&force, "force", false, "replace an existing machine config")
	return cmd
}

// ---- diff ----

func (a *app) diffCmd() *cobra.Command {
	var asJSON, noUntracked bool
	cmd := &cobra.Command{
		Use:   "diff",
		Short: "Compare this machine with its profile (missing / untracked / unavailable)",
		Long:  "Exits 2 when anything is missing or untracked, so scripts and agents can detect drift.",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			s, err := a.open(cmd.Context(), true)
			if err != nil {
				return err
			}
			rep, err := s.eng.Diff(cmd.Context(), !noUntracked)
			if err != nil {
				return err
			}
			if asJSON {
				if err := a.printJSON(rep); err != nil {
					return err
				}
			} else {
				a.printReport(rep)
			}
			if rep.Drift() {
				return silent(ExitDrift)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&asJSON, "json", false, "print JSON")
	cmd.Flags().BoolVar(&noUntracked, "no-untracked", false, "skip untracked detection")
	return cmd
}

func (a *app) printReport(rep *engine.Report) {
	w := a.Stdout
	fmt.Fprintf(w, "profile %s · package managers: %s\n", rep.Profile, strings.Join(rep.Managers, ", "))
	groups := []struct{ status, title string }{
		{engine.StatusMissing, "Missing (in profile, not installed)"},
		{engine.StatusUnavailable, "Unavailable (no package manager on this machine can install it)"},
	}
	for _, g := range groups {
		var items []string
		for _, p := range rep.Packages {
			if p.Status == g.status {
				item := p.Package
				if p.Status == engine.StatusMissing {
					item += fmt.Sprintf("  (%s: %s)", p.Manager, p.Name)
				}
				items = append(items, item)
			}
		}
		if len(items) > 0 {
			fmt.Fprintf(w, "\n%s:\n", g.title)
			for _, it := range items {
				fmt.Fprintf(w, "  %s\n", it)
			}
		}
	}
	if len(rep.Untracked) > 0 {
		fmt.Fprintf(w, "\nUntracked (installed, not in profile) — add with `install-sync adopt <name>`:\n")
		for _, u := range rep.Untracked {
			fmt.Fprintf(w, "  %-8s %s\n", u.Manager, u.Name)
		}
	}
	for mgr, e := range rep.Errors {
		fmt.Fprintf(w, "\n! %s: %s\n", mgr, e)
	}
	fmt.Fprintf(w, "\n%d ok, %d missing, %d unavailable, %d untracked\n",
		rep.Count(engine.StatusOK), rep.Count(engine.StatusMissing), rep.Count(engine.StatusUnavailable), len(rep.Untracked))
}

// ---- apply ----

func (a *app) applyCmd() *cobra.Command {
	var yes, dryRun bool
	cmd := &cobra.Command{
		Use:   "apply",
		Short: "Install everything in this machine's profile that is missing",
		Long:  "Apply never uninstalls anything. Script installs are shown and confirmed first unless --yes is given; without a terminal they are skipped and the exit code is 3.",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			ctx := cmd.Context()
			s, err := a.open(ctx, true)
			if err != nil {
				return err
			}
			if !dryRun {
				if err := s.eng.Prepare(ctx); err != nil {
					return err
				}
			}
			first, err := s.eng.Diff(ctx, false)
			if err != nil {
				return err
			}
			var failed, confirm []string
			installed := 0
			install := func(pkgs []engine.PackageState) {
				for _, p := range pkgs {
					if p.Status != engine.StatusMissing {
						continue
					}
					err := s.eng.Install(ctx, p, engine.InstallOpts{Yes: yes, Confirm: a.confirmer(), DryRun: dryRun})
					switch {
					case errors.Is(err, engine.ErrNeedsConfirmation):
						confirm = append(confirm, p.Package)
					case err != nil:
						a.logf("✗ %s: %v", p.Package, err)
						failed = append(failed, p.Package)
					default:
						installed++
					}
				}
			}
			install(first.Packages)
			unavailable := first.Count(engine.StatusUnavailable)

			// Installing a package can bring a new package manager (nodejs
			// brings npm) and make an unavailable package installable: retry
			// those once.
			if !dryRun && installed > 0 && unavailable > 0 {
				s.eng.Rescan()
				was := map[string]bool{}
				for _, p := range first.Packages {
					if p.Status == engine.StatusUnavailable {
						was[p.Package] = true
					}
				}
				var retry []engine.PackageState
				for pkg := range was {
					if st := s.eng.State(ctx, pkg); st.Status == engine.StatusMissing {
						retry = append(retry, st)
					}
				}
				unavailable -= len(retry)
				install(retry)
			}

			verb := "installed"
			if dryRun {
				verb = "would install"
			}
			fmt.Fprintf(a.Stdout, "%s %d, already ok %d, unavailable here %d, failed %d, need confirmation %d\n",
				verb, installed, first.Count(engine.StatusOK), unavailable, len(failed), len(confirm))
			if len(failed) > 0 {
				return &ExitError{Code: ExitFailure, Err: fmt.Errorf("failed: %s", strings.Join(failed, ", "))}
			}
			if len(confirm) > 0 {
				return &ExitError{Code: ExitNeedsConfirm, Err: fmt.Errorf("script installs need confirmation (rerun with --yes): %s", strings.Join(confirm, ", "))}
			}
			return nil
		},
	}
	cmd.Flags().BoolVarP(&yes, "yes", "y", false, "run script installs without asking")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "show what would be installed")
	return cmd
}

// ---- add ----

func (a *app) addCmd() *cobra.Command {
	var to, mgr, name string
	var cask, classic, noInstall, yes bool
	cmd := &cobra.Command{
		Use:   "add <package>...",
		Short: "Add packages to a profile and install them here",
		Long: `Adds packages to this machine's profile (or --to another profile), installs
them on this machine, then commits and pushes the manifest.

A package without a catalog definition is installed under its own name with the
first package manager (in manager order) that has it. Use --manager and --name
to record a definition, e.g. for winget ids or brew taps.`,
		Example: `  install-sync add jq gh
  install-sync add jq --to base-cli
  install-sync add jq --manager winget --name jqlang.jq
  install-sync add iterm2 --manager brew --cask`,
		Args: cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, pkgs []string) error {
			ctx := cmd.Context()
			if (mgr != "" || name != "") && len(pkgs) > 1 {
				return errors.New("--manager/--name apply to a single package")
			}
			if (name != "" || cask || classic) && mgr == "" {
				return errors.New("--name, --cask and --classic need --manager")
			}
			if mgr != "" && !manifest.IsKnownManager(mgr) {
				return fmt.Errorf("unknown package manager %q (known: %s)", mgr, strings.Join(manifest.KnownManagers, ", "))
			}
			if mgr == manifest.Script {
				return errors.New("script definitions need install and check commands: add them to packages.yaml by hand, then run `install-sync add <package>`")
			}
			s, err := a.open(ctx, true)
			if err != nil {
				return err
			}
			target := to
			if target == "" {
				target = s.cfg.Profile
			}
			if _, ok := s.m.Profiles[target]; !ok {
				return fmt.Errorf("profile %q not found (available: %s)", target, strings.Join(s.m.ProfileNames(), ", "))
			}
			chain, err := s.m.Resolve(s.cfg.Profile)
			if err != nil {
				return err
			}
			inChain := false
			for _, prof := range profileChain(s.m, s.cfg.Profile) {
				if prof == target {
					inChain = true
				}
			}
			install := !noInstall && inChain
			if !noInstall && !inChain {
				a.logf("! %s is not part of this machine's profile (%s); adding without installing", target, s.cfg.Profile)
			}
			if install {
				if err := s.eng.Prepare(ctx); err != nil {
					return err
				}
			}

			var added, failed []string
			for _, pkg := range pkgs {
				if err := checkPkgName(pkg); err != nil {
					a.logf("✗ %v", err)
					failed = append(failed, pkg)
					continue
				}
				var entry *manifest.Entry
				if mgr != "" {
					e := manifest.Entry{Name: name, Cask: cask, Classic: classic}
					if e.Name == pkg {
						e.Name = ""
					}
					entry = &e
					def, _ := s.m.Definition(pkg)
					entries := map[string]manifest.Entry{}
					for k, v := range def.Entries {
						entries[k] = v
					}
					entries[mgr] = e
					def.Entries = entries
					s.m.Catalog[pkg] = def
				}
				if install {
					st := s.eng.State(ctx, pkg)
					switch st.Status {
					case engine.StatusUnavailable:
						a.logf("✗ %s: no package manager on this machine has it (%s).", pkg, strings.Join(usableNames(s.eng), ", "))
						if st.Error != "" {
							a.logf("  (%s)", st.Error)
						}
						a.logf("  record how to install it, e.g. `install-sync add %s --manager %s --name <id>`", pkg, firstOr(usableNames(s.eng), "brew"))
						failed = append(failed, pkg)
						continue
					case engine.StatusMissing:
						if err := s.eng.Install(ctx, st, engine.InstallOpts{Yes: yes, Confirm: a.confirmer()}); err != nil {
							if errors.Is(err, engine.ErrNeedsConfirmation) {
								return &ExitError{Code: ExitNeedsConfirm, Err: fmt.Errorf("%s is a script install; rerun with --yes to run it", pkg)}
							}
							a.logf("✗ %s: %v", pkg, err)
							failed = append(failed, pkg)
							continue
						}
					case engine.StatusOK:
						a.logf("✓ %s is already installed (%s)", pkg, st.Manager)
					}
				}
				if entry != nil {
					if err := manifest.SetEntry(s.m.Dir, pkg, mgr, *entry); err != nil {
						return err
					}
				}
				if wantedVia := wantedThrough(chain, pkg); to == "" && len(wantedVia) > 0 {
					a.logf("✓ %s is already in this machine's profile (via %s)", pkg, strings.Join(wantedVia, ", "))
					if entry != nil {
						added = append(added, pkg)
					}
					continue
				}
				if s.m.Profiles[target].Has(pkg) {
					a.logf("✓ %s is already listed in %s", pkg, target)
					if entry != nil {
						added = append(added, pkg)
					}
					continue
				}
				if _, err := manifest.AddPackages(s.m.Dir, target, pkg); err != nil {
					return err
				}
				s.m.Profiles[target].Packages = append(s.m.Profiles[target].Packages, pkg)
				added = append(added, pkg)
			}
			if len(added) > 0 {
				a.commit(ctx, s, fmt.Sprintf("%s: add %s", target, strings.Join(added, ", ")))
				fmt.Fprintf(a.Stdout, "added to %s: %s\n", target, strings.Join(added, ", "))
			}
			if len(failed) > 0 {
				return &ExitError{Code: ExitFailure, Err: fmt.Errorf("not added: %s", strings.Join(failed, ", "))}
			}
			return nil
		},
	}
	f := cmd.Flags()
	f.StringVar(&to, "to", "", "profile to add to (default: this machine's profile)")
	f.StringVar(&mgr, "manager", "", "record a definition entry for this package manager")
	f.StringVar(&name, "name", "", "the package's name in that package manager (default: the package name)")
	f.BoolVar(&cask, "cask", false, "brew: the package is a cask")
	f.BoolVar(&classic, "classic", false, "snap: install with --classic")
	f.BoolVar(&noInstall, "no-install", false, "only change the manifest")
	f.BoolVarP(&yes, "yes", "y", false, "run script installs without asking")
	return cmd
}

// ---- remove ----

func (a *app) removeCmd() *cobra.Command {
	var from string
	var keep bool
	cmd := &cobra.Command{
		Use:   "remove <package>...",
		Short: "Remove packages from a profile and uninstall them here",
		Long: `Removes packages from the profile that lists them and uninstalls them on this
machine (unless --keep). Other machines are not touched: they will report the
package as untracked. A package that comes from an included profile needs
--from <profile>, so a shared profile is never changed by accident.`,
		Args: cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, pkgs []string) error {
			ctx := cmd.Context()
			s, err := a.open(ctx, true)
			if err != nil {
				return err
			}
			own := s.m.Profiles[s.cfg.Profile]
			type change struct{ pkg, profile string }
			var changes []change
			for _, pkg := range pkgs {
				chain, err := s.m.Resolve(s.cfg.Profile)
				if err != nil {
					return err
				}
				var fromProfiles []string
				for _, r := range chain {
					if r.Package == pkg {
						fromProfiles = r.From
					}
				}
				target := from
				switch {
				case target != "":
					p, ok := s.m.Profiles[target]
					if !ok {
						return fmt.Errorf("profile %q not found", target)
					}
					if !p.Has(pkg) {
						return fmt.Errorf("%s is not listed in profile %s", pkg, target)
					}
				case own.Has(pkg):
					target = own.Name
				case len(fromProfiles) > 0:
					src := fromProfiles[0]
					users := s.m.IncludedBy(src)
					return fmt.Errorf("%s comes from %s (included by %s); to change that shared profile, rerun with --from %s",
						pkg, src, strings.Join(users, ", "), src)
				default:
					return fmt.Errorf("%s is not in profile %s or its includes", pkg, s.cfg.Profile)
				}
				st := s.eng.State(ctx, pkg)
				if _, err := manifest.RemovePackage(s.m.Dir, target, pkg); err != nil {
					return err
				}
				p := s.m.Profiles[target]
				kept := p.Packages[:0]
				for _, x := range p.Packages {
					if x != pkg {
						kept = append(kept, x)
					}
				}
				p.Packages = kept
				changes = append(changes, change{pkg, target})

				still, _ := s.m.Resolve(s.cfg.Profile)
				stillWanted := false
				for _, r := range still {
					if r.Package == pkg {
						stillWanted = true
						a.logf("! %s is still wanted through %s, so it stays installed", pkg, strings.Join(r.From, ", "))
					}
				}
				if !keep && !stillWanted && st.Status == engine.StatusOK {
					if err := s.eng.Uninstall(ctx, st); err != nil {
						a.logf("✗ could not uninstall %s: %v (it was still removed from %s)", pkg, err, target)
					}
				}
			}
			byProfile := map[string][]string{}
			var order []string
			for _, c := range changes {
				if _, ok := byProfile[c.profile]; !ok {
					order = append(order, c.profile)
				}
				byProfile[c.profile] = append(byProfile[c.profile], c.pkg)
			}
			var parts []string
			for _, p := range order {
				parts = append(parts, fmt.Sprintf("%s: remove %s", p, strings.Join(byProfile[p], ", ")))
			}
			if len(parts) > 0 {
				a.commit(ctx, s, strings.Join(parts, "; "))
				fmt.Fprintln(a.Stdout, strings.Join(parts, "\n"))
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&from, "from", "", "profile to remove from (required for packages from included profiles)")
	cmd.Flags().BoolVar(&keep, "keep", false, "only change the manifest; keep it installed")
	return cmd
}

// ---- adopt ----

func (a *app) adoptCmd() *cobra.Command {
	var all bool
	var to, onlyMgr string
	cmd := &cobra.Command{
		Use:   "adopt [<name>...]",
		Short: "Move untracked packages into a profile without reinstalling them",
		Long:  "Without arguments, lists untracked packages. Names are as `install-sync diff` shows them.",
		RunE: func(cmd *cobra.Command, names []string) error {
			ctx := cmd.Context()
			s, err := a.open(ctx, true)
			if err != nil {
				return err
			}
			rep, err := s.eng.Diff(ctx, true)
			if err != nil {
				return err
			}
			var pool []engine.Untracked
			for _, u := range rep.Untracked {
				if onlyMgr == "" || u.Manager == onlyMgr {
					pool = append(pool, u)
				}
			}
			var pick []engine.Untracked
			switch {
			case all:
				pick = pool
			case len(names) == 0:
				if len(pool) == 0 {
					fmt.Fprintln(a.Stdout, "nothing untracked")
					return nil
				}
				fmt.Fprintln(a.Stdout, "Untracked packages (adopt with `install-sync adopt <name>...` or `--all`):")
				for _, u := range pool {
					fmt.Fprintf(a.Stdout, "  %-8s %s\n", u.Manager, u.Name)
				}
				return nil
			default:
				for _, n := range names {
					found := false
					for _, u := range pool {
						if strings.EqualFold(u.Name, n) {
							pick = append(pick, u)
							found = true
							break
						}
					}
					if !found {
						return fmt.Errorf("%s is not untracked here (see `install-sync adopt`)", n)
					}
				}
			}
			if len(pick) == 0 {
				fmt.Fprintln(a.Stdout, "nothing to adopt")
				return nil
			}
			target := to
			if target == "" {
				target = s.cfg.Profile
			}
			if _, ok := s.m.Profiles[target]; !ok {
				return fmt.Errorf("profile %q not found", target)
			}
			var pkgs []string
			for _, u := range pick {
				pkg, entry := s.eng.AdoptName(u.Manager, u.Name)
				if entry != nil {
					if err := manifest.SetEntry(s.m.Dir, pkg, u.Manager, *entry); err != nil {
						return err
					}
					def, _ := s.m.Definition(pkg)
					entries := map[string]manifest.Entry{}
					for k, v := range def.Entries {
						entries[k] = v
					}
					entries[u.Manager] = *entry
					def.Entries = entries
					s.m.Catalog[pkg] = def
				}
				pkgs = append(pkgs, pkg)
				a.logf("+ %s (%s: %s)", pkg, u.Manager, u.Name)
			}
			added, err := manifest.AddPackages(s.m.Dir, target, pkgs...)
			if err != nil {
				return err
			}
			if _, err := manifest.Load(s.m.Dir); err != nil {
				return fmt.Errorf("adopting produced an invalid manifest (nothing committed): %w", err)
			}
			a.commit(ctx, s, fmt.Sprintf("%s: adopt %d package(s)", target, len(added)))
			fmt.Fprintf(a.Stdout, "adopted %d package(s) into %s\n", len(added), target)
			return nil
		},
	}
	cmd.Flags().BoolVar(&all, "all", false, "adopt every untracked package")
	cmd.Flags().StringVar(&to, "to", "", "profile to adopt into (default: this machine's profile)")
	cmd.Flags().StringVar(&onlyMgr, "manager", "", "only consider this package manager")
	return cmd
}

// ---- upgrade ----

func (a *app) upgradeCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "upgrade [<package>...]",
		Short: "Upgrade installed profile packages to the newest version",
		RunE: func(cmd *cobra.Command, pkgs []string) error {
			ctx := cmd.Context()
			s, err := a.open(ctx, true)
			if err != nil {
				return err
			}
			rep, err := s.eng.Diff(ctx, false)
			if err != nil {
				return err
			}
			only := map[string]bool{}
			for _, p := range pkgs {
				only[p] = true
			}
			if err := s.eng.Upgrade(ctx, rep, only); err != nil {
				return err
			}
			fmt.Fprintln(a.Stdout, "upgrade done")
			return nil
		},
	}
	return cmd
}

// ---- status ----

type statusOut struct {
	Config   string          `json:"config"`
	Profile  string          `json:"profile"`
	Manifest string          `json:"manifest"`
	Order    []string        `json:"manager_order"`
	Usable   []string        `json:"managers_on_this_machine"`
	Git      *gitrepo.Status `json:"git,omitempty"`
	GitError string          `json:"git_error,omitempty"`
}

func (a *app) statusCmd() *cobra.Command {
	var asJSON bool
	cmd := &cobra.Command{
		Use:   "status",
		Short: "Show this machine's profile, manifest location and git state",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			ctx := cmd.Context()
			cfg, cfgPath, err := machine.Load()
			if err != nil {
				return err
			}
			out := statusOut{Config: cfgPath, Profile: cfg.Profile, Manifest: cfg.Manifest, Order: cfg.Order(a.GOOS)}
			mgrs := a.Managers(a.Runner, a.GOOS)
			for _, n := range out.Order {
				if m, ok := mgrs[n]; ok && m.Usable() {
					out.Usable = append(out.Usable, n)
				}
			}
			repo := gitrepo.Repo{Dir: cfg.Manifest, R: a.Runner}
			if st, err := repo.Status(ctx); err == nil {
				out.Git = &st
			} else {
				out.GitError = err.Error()
			}
			if asJSON {
				return a.printJSON(out)
			}
			w := a.Stdout
			fmt.Fprintf(w, "profile:   %s\nmanifest:  %s\nconfig:    %s\nmanagers:  %s (order: %s)\n",
				out.Profile, out.Manifest, out.Config, strings.Join(out.Usable, ", "), strings.Join(out.Order, ", "))
			if out.Git == nil {
				fmt.Fprintf(w, "git:       %s\n", out.GitError)
				return nil
			}
			g := out.Git
			fmt.Fprintf(w, "git:       %s on %s", g.Remote, g.Branch)
			if g.Upstream != "" {
				fmt.Fprintf(w, " (ahead %d, behind %d of %s, as of last fetch)", g.Ahead, g.Behind, g.Upstream)
			}
			fmt.Fprintln(w)
			if g.Dirty {
				fmt.Fprintf(w, "           uncommitted changes: %s\n", strings.Join(g.DirtyList, ", "))
			}
			if g.Unpushed {
				fmt.Fprintf(w, "           unpushed commits: run `git -C %s push`\n", g.Root)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&asJSON, "json", false, "print JSON")
	return cmd
}

// ---- profiles ----

type profileOut struct {
	Name        string   `json:"name"`
	Description string   `json:"description,omitempty"`
	Include     []string `json:"include"`
	IncludedBy  []string `json:"included_by"`
	Own         int      `json:"own_packages"`
	Total       int      `json:"total_packages"`
	Current     bool     `json:"current"`
}

func (a *app) profilesCmd() *cobra.Command {
	var asJSON bool
	cmd := &cobra.Command{
		Use:   "profiles",
		Short: "List profiles and what they include",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			s, err := a.open(cmd.Context(), true)
			if err != nil {
				return err
			}
			var out []profileOut
			for _, n := range s.m.ProfileNames() {
				p := s.m.Profiles[n]
				res, _ := s.m.Resolve(n)
				out = append(out, profileOut{
					Name: n, Description: p.Description, Include: nonNil(p.Include), IncludedBy: nonNil(s.m.IncludedBy(n)),
					Own: len(p.Packages), Total: len(res), Current: n == s.cfg.Profile,
				})
			}
			if asJSON {
				return a.printJSON(out)
			}
			for _, p := range out {
				mark := " "
				if p.Current {
					mark = "*"
				}
				line := fmt.Sprintf("%s %-16s %3d packages (%d own)", mark, p.Name, p.Total, p.Own)
				if len(p.Include) > 0 {
					line += "  includes " + strings.Join(p.Include, ", ")
				}
				fmt.Fprintln(a.Stdout, line)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&asJSON, "json", false, "print JSON")
	return cmd
}

// ---- validate ----

func (a *app) validateCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "validate [<manifest folder>]",
		Short: "Check a manifest for errors (default: this machine's manifest)",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir := ""
			if len(args) == 1 {
				dir = args[0]
			} else {
				cfg, _, err := machine.Load()
				if err != nil {
					return err
				}
				dir = cfg.Manifest
			}
			m, err := manifest.Load(dir)
			if err != nil {
				return err
			}
			fmt.Fprintf(a.Stdout, "✓ %s: %d profiles, %d definitions\n", dir, len(m.Profiles), len(m.Catalog))
			return nil
		},
	}
}

// ---- migrate ----

func (a *app) migrateCmd() *cobra.Command {
	var out string
	cmd := &cobra.Command{
		Use:   "migrate <v0 config.json> --out <folder>",
		Short: "Convert a v0 config.json into a v1 manifest (one profile per old machine)",
		Long: `Writes packages.yaml and profiles/ into --out, one profile per old machine.
Reorganise the profiles by purpose afterwards (e.g. base-cli, work, personal),
then commit the folder to a new manifest repo and run init on each machine.`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if out == "" {
				return errors.New("--out is required")
			}
			data, err := os.ReadFile(args[0])
			if err != nil {
				return err
			}
			res, err := migrate.Convert(data)
			if err != nil {
				return err
			}
			if err := migrate.Write(out, res); err != nil {
				return err
			}
			if _, err := manifest.Load(out); err != nil {
				return fmt.Errorf("migrated manifest does not validate: %w", err)
			}
			for name, pkgs := range res.Profiles {
				fmt.Fprintf(a.Stdout, "profile %s: %d packages\n", name, len(pkgs))
			}
			fmt.Fprintf(a.Stdout, "catalog: %d definitions\n", len(res.Catalog))
			for _, n := range res.Notes {
				fmt.Fprintf(a.Stdout, "note: %s\n", n)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&out, "out", "", "folder to write the new manifest into")
	return cmd
}

// ---- helpers ----

func profileChain(m *manifest.Manifest, profile string) []string {
	seen := map[string]bool{}
	var out []string
	var walk func(string)
	walk = func(n string) {
		if seen[n] {
			return
		}
		seen[n] = true
		out = append(out, n)
		if p, ok := m.Profiles[n]; ok {
			for _, inc := range p.Include {
				walk(inc)
			}
		}
	}
	walk(profile)
	return out
}

// wantedThrough returns the profiles in a resolved chain that list pkg.
func wantedThrough(chain []manifest.Resolved, pkg string) []string {
	for _, r := range chain {
		if r.Package == pkg {
			return r.From
		}
	}
	return nil
}

func usableNames(e *engine.Engine) []string {
	var out []string
	for _, m := range e.Usable() {
		out = append(out, m.Name())
	}
	return out
}

func firstOr(xs []string, def string) string {
	if len(xs) > 0 {
		return xs[0]
	}
	return def
}

func nonNil(xs []string) []string {
	if xs == nil {
		return []string{}
	}
	return xs
}

func checkPkgName(pkg string) error {
	if !manifest.ValidProfileName(pkg) {
		return fmt.Errorf("%q is not a valid package name (lowercase letters, digits and . _ + -); for winget ids or brew taps use --manager and --name", pkg)
	}
	return nil
}
