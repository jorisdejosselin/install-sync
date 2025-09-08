# CHANGELOG


## v0.10.4 (2025-09-08)

### Bug Fixes

* fix: use correct machine ID correlation in bulk install

- Fix --all flag to only show packages for current machine ID
- Remove incorrect cross-machine package aggregation
- Use direct JSON lookup with current machine's profile_id
- Preserve original package manager from JSON for current machine

This fixes the issue where bulk install was showing packages from
all machines instead of just the current machine's tracked packages.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com> ([`7846484`](https://github.com/jorisdejosselin/install-sync/commit/784648401bb70e9db4657f0e1e98fc3318785795))


## v0.10.3 (2025-09-08)

### Bug Fixes

* fix: use current machine's package manager in bulk install

- Fix bulk install to use appropriate package manager for current machine
- Replace source machine's package manager with current machine's default
- Ensure packages show correct manager (brew on macOS, apt on Linux, etc)
- Skip packages that don't have suitable manager for current platform

This fixes the issue where bulk install showed wrong package managers
(apt/winget packages on macOS instead of brew equivalents).

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com> ([`5233f7f`](https://github.com/jorisdejosselin/install-sync/commit/5233f7fdd085fd8f3dfee1b4d58ee9b635b4421f))


## v0.10.2 (2025-09-08)

### Bug Fixes

* fix: resolve AttributeError in bulk install by adding defensive list handling

- Fix critical bug where defaultdict was returning None instead of empty list
- Add defensive coding to ensure by_manager always contains proper lists
- Remove debug output that was causing confusion
- Move defaultdict import to top level for reliability

The bulk install feature now works correctly without AttributeError crashes.
Resolves the 'NoneType' object has no attribute 'append' error.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com> ([`5518923`](https://github.com/jorisdejosselin/install-sync/commit/551892392717d589614dd269b8a8d244975b6e89))


## v0.10.1 (2025-09-08)

### Bug Fixes

* fix: replace simulation code with real package installation in bulk install

- Remove simulation logic that was causing AttributeError
- Implement real package manager installation calls
- Fix display to show clean package list without source machine info
- Add proper configuration saving and git operations
- Remove confusing 'Would install' test artifacts
- Fix linting issues (unused import, line length, spacing)

This fixes the critical bug where bulk install was not actually
installing packages and was showing wrong information.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com> ([`5622eb0`](https://github.com/jorisdejosselin/install-sync/commit/5622eb088f09c3ed97f45d436834c4c3ea314514))


## v0.10.0 (2025-09-08)

### Bug Fixes

* fix: update semantic-release action to v9.12.0

Update python-semantic-release action from v9.1.1 to v9.12.0 to fix
Docker build issues with obsolete Debian bullseye-backports repository.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com> ([`d41128d`](https://github.com/jorisdejosselin/install-sync/commit/d41128d66e9c78c98ea5e12cd5b02229d39b8468))

### Features

* feat: add bulk install functionality with --all flag

- Add --all flag to install command for bulk package installation
- Add --from-machine option to install from specific machines
- Implement package discovery and deduplication across machines
- Add interactive confirmation and progress tracking
- Support manager override and force reinstall for bulk operations
- Maintain backward compatibility with single package installs

This enables the core use case of easily restoring all packages
on a new machine with 'install-sync install --all'.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com> ([`a8bc386`](https://github.com/jorisdejosselin/install-sync/commit/a8bc38688df0416bbdf557bb2161100050ebe407))

### Unknown

* Merge branch 'develop' ([`21fcb7d`](https://github.com/jorisdejosselin/install-sync/commit/21fcb7dee38d19d2c182e6f8a28174943159aafd))


## v0.9.0 (2025-07-07)

### Bug

* bug: Test pipeline ([`a3f3e2d`](https://github.com/jorisdejosselin/install-sync/commit/a3f3e2ddb81749fc1eca444b694dabcc0e42418c))

* bug: Test pipeline ([`7cc8f2c`](https://github.com/jorisdejosselin/install-sync/commit/7cc8f2cca3b1b108da2828a777d56ab94f7765d0))

* bug: Fix testing suite ([`f5e0457`](https://github.com/jorisdejosselin/install-sync/commit/f5e0457ee56ab73307459e1a4f395bb9ad17dcaa))

* bug: Fix testing suite ([`b344890`](https://github.com/jorisdejosselin/install-sync/commit/b3448902f9dd2f17218079f67f2b22b164a4aa32))

* bug: Fix testing suite ([`be41d25`](https://github.com/jorisdejosselin/install-sync/commit/be41d25ca84b1052b01ba73e02a1ef3127d171ad))

* bug: Fix tracking git commit and push ([`dea9247`](https://github.com/jorisdejosselin/install-sync/commit/dea924737647ff650164c49d70c55d17506b5fae))

* bug: Fix tracking git commit and push ([`4d980de`](https://github.com/jorisdejosselin/install-sync/commit/4d980de0842e0b24c291c88171826ab4928cb7e0))

* bug: fix dir tracking and formatting on windows ([`0deb105`](https://github.com/jorisdejosselin/install-sync/commit/0deb105672a3f7571366df99fcc24afcb5301f46))

### Feature

* feature: add track existing packages without installing ([`5e8fe7c`](https://github.com/jorisdejosselin/install-sync/commit/5e8fe7c96913124ec6a3bca84cc49712bf578ad1))

### Unknown

* Merge pull request #5 from jorisdejosselin/develop

Feature: tracking already installed packages ([`29ee2bb`](https://github.com/jorisdejosselin/install-sync/commit/29ee2bb6bacdfee7781784e3454d5b8e68e1f9f7))


## v0.8.0 (2025-07-07)

### Features

* feat: add initial release workflow ([`f20c82b`](https://github.com/jorisdejosselin/install-sync/commit/f20c82be0ec2c9a48febf40453f7aeaa015afdbe))


## v0.7.0 (2025-07-07)

### Features

* feat: add initial release workflow ([`a7e4efa`](https://github.com/jorisdejosselin/install-sync/commit/a7e4efae9885b3a89bcdd134ee8a62f9e1804143))

* feat: add initial release workflow ([`5e7a049`](https://github.com/jorisdejosselin/install-sync/commit/5e7a04966848c4b2d850ca76cf3d76a97d8ba596))

### Unknown

* Merge pull request #4 from jorisdejosselin/develop

feat: add initial release workflow ([`787a216`](https://github.com/jorisdejosselin/install-sync/commit/787a216599521a8c8940b0b4ffb410e5d6562d94))


## v0.6.0 (2025-07-07)

### Features

* feat: add initial release workflow ([`47c083b`](https://github.com/jorisdejosselin/install-sync/commit/47c083bb9fb4c4334e028293aea65b423b0f04d8))


## v0.5.0 (2025-07-07)

### Features

* feat: add initial release workflow ([`ad872b5`](https://github.com/jorisdejosselin/install-sync/commit/ad872b5768705bde13c5ea38a21ebf7c49a9f9b4))


## v0.4.0 (2025-07-07)

### Features

* feat: add initial release workflow ([`3d3b9be`](https://github.com/jorisdejosselin/install-sync/commit/3d3b9be56b1d064680c608c8b191aaa9acd8601a))


## v0.3.0 (2025-07-07)

### Features

* feat: add initial release workflow ([`ea11b9e`](https://github.com/jorisdejosselin/install-sync/commit/ea11b9e209a234418e61ba4b143191614394de9b))


## v0.2.0 (2025-07-07)

### Features

* feat: add initial release workflow ([`51b2e9d`](https://github.com/jorisdejosselin/install-sync/commit/51b2e9d545eb47953f50278b75d7d81978d21694))

* feat: add initial release workflow ([`b6e9aed`](https://github.com/jorisdejosselin/install-sync/commit/b6e9aedd2d7002ec31fbe9b4522fdd55bea1be67))


## v0.1.0 (2025-07-06)

### Features

* feat: add initial release workflow ([`e7b5ab5`](https://github.com/jorisdejosselin/install-sync/commit/e7b5ab5bfc8205d59a7c5d8d1d5922abe4d6a3eb))


## v0.0.0 (2025-07-06)

### Unknown

* Fix CI stuff ([`4790e65`](https://github.com/jorisdejosselin/install-sync/commit/4790e65b89010b0783d619beee2025b07eb756f7))

* Fix CI stuff ([`189cdf4`](https://github.com/jorisdejosselin/install-sync/commit/189cdf447178b661ae438e8168c33912c8aeadca))

* Merge pull request #3 from jorisdejosselin/develop

Fix CI stuff ([`43a9d04`](https://github.com/jorisdejosselin/install-sync/commit/43a9d048305491be00e077039180e60c6892a929))

* Fix CI stuff ([`f8eb61c`](https://github.com/jorisdejosselin/install-sync/commit/f8eb61cfdf4e9b7400d2feaed0e0f0b13f0cc141))

* Fix CI stuff ([`0c33e3e`](https://github.com/jorisdejosselin/install-sync/commit/0c33e3ed4cd71c02da6da4ef5a8223896f742493))

* Fix CI stuff ([`697f74b`](https://github.com/jorisdejosselin/install-sync/commit/697f74b214794a96595af4936b9c80b0da87ea5d))

* Add pre-commit fixes ([`1edd2cf`](https://github.com/jorisdejosselin/install-sync/commit/1edd2cfcc4991fb1691637cb96774131fc27aaa7))

* Fix CI stuff ([`9c6b520`](https://github.com/jorisdejosselin/install-sync/commit/9c6b520935dca433e24b5b9949a41318250539aa))

* Merge pull request #2 from jorisdejosselin/develop

Add comprehensive auto-sync, improved error handling, and multi-architecture support ([`3da8b64`](https://github.com/jorisdejosselin/install-sync/commit/3da8b646e69b5d9278b7031765ade8c0bd6c85d1))

* even more fixes ([`6ad6c29`](https://github.com/jorisdejosselin/install-sync/commit/6ad6c29f845e747d85f9407bd51a09f77ef7180a))

* even more fixes ([`5de4b9a`](https://github.com/jorisdejosselin/install-sync/commit/5de4b9a636241e9b522ec212a687d4147e7bd4da))

* even more fixes ([`1aa3bf2`](https://github.com/jorisdejosselin/install-sync/commit/1aa3bf289eb35be1d7288d66096eb3fcb4df11b0))

* even more fixes ([`760f4c1`](https://github.com/jorisdejosselin/install-sync/commit/760f4c1353b52e65c64252c3bb3ee74da1203c34))

* even more fixes ([`7a0e02d`](https://github.com/jorisdejosselin/install-sync/commit/7a0e02d5139de01242a329b5969d77b7e1082e7a))

* even more fixes ([`7268bd3`](https://github.com/jorisdejosselin/install-sync/commit/7268bd3647b1949f50f129e8add8f426c017f06d))

* even more fixes ([`c67a7c0`](https://github.com/jorisdejosselin/install-sync/commit/c67a7c01f82e83d38eb925fa642bbffd346c8458))

* even more fixes ([`e77dce8`](https://github.com/jorisdejosselin/install-sync/commit/e77dce8fdaf6b7a82c8036761f35dbbd40e7f878))

* even more fixes ([`284f1c8`](https://github.com/jorisdejosselin/install-sync/commit/284f1c8bf6565352c39607d8c425500ac262f9ff))

* even more fixes ([`c323ce5`](https://github.com/jorisdejosselin/install-sync/commit/c323ce50b580c9da33955c0edc3a492a50d25fa0))

* even more fixes ([`91b5a28`](https://github.com/jorisdejosselin/install-sync/commit/91b5a28943ad162e012be69e80456c906a926119))

* even more fixes ([`b36103a`](https://github.com/jorisdejosselin/install-sync/commit/b36103ab89be2a51f930bbac34ec29438b130c22))

* even more fixes ([`b0133a8`](https://github.com/jorisdejosselin/install-sync/commit/b0133a8a7df46331c6520b0029b25f7b59b93598))

* even more fixes ([`4d06bb9`](https://github.com/jorisdejosselin/install-sync/commit/4d06bb97d15501617d36146678a9069681d328a1))

* even more fixes ([`5345f67`](https://github.com/jorisdejosselin/install-sync/commit/5345f67fbb780b73c04eb0edd69f40ad6668afe8))

* even more fixes ([`e4d7a5e`](https://github.com/jorisdejosselin/install-sync/commit/e4d7a5e41e0e6f1151be28ae0e6b3b9f5583e9ec))

* even more fixes ([`6d2d01e`](https://github.com/jorisdejosselin/install-sync/commit/6d2d01ecd1166c56fd7ce190081ccb98dcb9d2b6))

* Pre-commit fixes ([`ee10062`](https://github.com/jorisdejosselin/install-sync/commit/ee10062883a4b78b16e81adb041276722f2502d1))

* Fix CI ([`5ce5e8d`](https://github.com/jorisdejosselin/install-sync/commit/5ce5e8db1226963b9e49d50cc90bd92db6de000d))

* First version of install-sync tool ([`23d52a5`](https://github.com/jorisdejosselin/install-sync/commit/23d52a5c4575922bb82bab1f50578d974772ab03))
