// Package pm implements the package managers install-sync drives.
package pm

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"os/exec"
	"strings"
)

// Result is the outcome of a captured command.
type Result struct {
	Stdout string
	Stderr string
	Code   int
}

// OK reports whether the command exited 0.
func (r Result) OK() bool { return r.Code == 0 }

// Runner runs external commands. It is an interface so tests can fake it.
type Runner interface {
	// Capture runs a command and captures its output. err is only set when
	// the command could not be started.
	Capture(ctx context.Context, name string, args ...string) (Result, error)
	// Stream runs a command with output shown to the user.
	Stream(ctx context.Context, name string, args ...string) error
	// LookPath reports whether a command exists.
	LookPath(name string) bool
}

// ExecRunner runs real commands.
type ExecRunner struct {
	Stdout io.Writer
	Stderr io.Writer
	Env    []string
}

// Capture implements Runner.
func (r ExecRunner) Capture(ctx context.Context, name string, args ...string) (Result, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Env = r.env()
	var out, errb bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errb
	err := cmd.Run()
	res := Result{Stdout: out.String(), Stderr: errb.String()}
	var ee *exec.ExitError
	if errors.As(err, &ee) {
		res.Code = ee.ExitCode()
		return res, nil
	}
	if err != nil {
		return res, err
	}
	return res, nil
}

// Stream implements Runner.
func (r ExecRunner) Stream(ctx context.Context, name string, args ...string) error {
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Env = r.env()
	cmd.Stdin = os.Stdin
	cmd.Stdout, cmd.Stderr = r.Stdout, r.Stderr
	if cmd.Stdout == nil {
		cmd.Stdout = os.Stderr
	}
	if cmd.Stderr == nil {
		cmd.Stderr = os.Stderr
	}
	if err := cmd.Run(); err != nil {
		return &CommandError{Cmd: strings.Join(append([]string{name}, args...), " "), Err: err}
	}
	return nil
}

// LookPath implements Runner.
func (r ExecRunner) LookPath(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func (r ExecRunner) env() []string {
	if r.Env == nil {
		return nil
	}
	return append(os.Environ(), r.Env...)
}

// CommandError is a failed streamed command.
type CommandError struct {
	Cmd string
	Err error
}

func (e *CommandError) Error() string {
	cmd := e.Cmd
	if i := strings.IndexByte(cmd, '\n'); i >= 0 {
		cmd = cmd[:i] + " …"
	}
	return cmd + ": " + e.Err.Error()
}
func (e *CommandError) Unwrap() error { return e.Err }

func lines(s string) []string {
	var out []string
	for _, l := range strings.Split(s, "\n") {
		if l = strings.TrimSpace(l); l != "" {
			out = append(out, l)
		}
	}
	return out
}
