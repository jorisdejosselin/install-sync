package pm

import (
	"context"
	"fmt"
	"strings"
	"sync"
)

// FakeRunner is a Runner for tests. Responses are keyed by the full command
// line ("brew list --formula -1"); unknown commands exit 127.
type FakeRunner struct {
	mu        sync.Mutex
	Responses map[string]Result
	Paths     map[string]bool
	Calls     []string
	// StreamErr makes streamed commands with this prefix fail.
	StreamErr map[string]error
}

func (f *FakeRunner) key(name string, args []string) string {
	if len(args) == 0 {
		return name
	}
	return name + " " + strings.Join(args, " ")
}

// Capture implements Runner.
func (f *FakeRunner) Capture(_ context.Context, name string, args ...string) (Result, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	k := f.key(name, args)
	f.Calls = append(f.Calls, k)
	if r, ok := f.Responses[k]; ok {
		return r, nil
	}
	return Result{Code: 127, Stderr: fmt.Sprintf("fake: no response for %q", k)}, nil
}

// Stream implements Runner.
func (f *FakeRunner) Stream(_ context.Context, name string, args ...string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	k := f.key(name, args)
	f.Calls = append(f.Calls, k)
	for prefix, err := range f.StreamErr {
		if strings.HasPrefix(k, prefix) {
			return err
		}
	}
	return nil
}

// LookPath implements Runner.
func (f *FakeRunner) LookPath(name string) bool { return f.Paths[name] }
