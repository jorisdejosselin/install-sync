# Desired-state manifest instead of a per-machine install log

install-sync used to record an install log per machine, keyed by a hash of hostname/OS/arch, which broke when hostnames changed and could not share tools between machines or show drift. We replace it with a desired-state manifest: named profiles (with includes) list OS-independent packages, a catalog of definitions maps each package to package managers, and machines apply one profile. This is a breaking change to the data model, accepted because it is the only way to reuse a profile across a yearly stream of new laptops.
