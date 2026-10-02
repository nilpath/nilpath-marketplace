# Plan: [Feature Title]

## Goal

[One sentence: what this implementation achieves]

## Architecture

[2-3 sentences: key components, how they relate, and the main architectural decisions from design.md]

## Tech Stack

- **[Language/Runtime]**: [version]
- **Test runner**: `<test-command>`
- **[Key library]**: [purpose]

## Tasks

### Task 001: [Title]

**Files**:

- Create: `path/to/new_file.py`
- Modify: `path/to/existing_file.py`
- Test: `path/to/test_file.py`

- [ ] **Step 1**: Write failing test in `path/to/test_file.py`

  ```python
  def test_[behavior]():
      # arrange
      # act
      result = [function_under_test](...)
      # assert
      assert result == [expected]
  ```

- [ ] **Step 2**: Run `<test-command>` — confirm it fails

  Expected: `[failure message or assertion error]`

- [ ] **Step 3**: Write minimal implementation in `path/to/new_file.py`

  ```python
  def [name]([params]):
      # minimal implementation
      pass
  ```

- [ ] **Step 4**: Run `<test-command>` — confirm it passes

  Expected: `✓ [test name]`

- [ ] **Step 5**: Commit using the `git-commits` skill

  `git commit -m "<type>(<scope>): <message>"`

---

### Task 002: [Title]

**Files**:

- Create: `path/to/new_file.py`
- Test: `path/to/test_file.py`

- [ ] **Step 1**: Write failing test in `path/to/test_file.py`

  ```python
  def test_[behavior]():
      # arrange
      # act
      result = [function_under_test](...)
      # assert
      assert result == [expected]
  ```

- [ ] **Step 2**: Run `<test-command>` — confirm it fails

  Expected: `[failure message or assertion error]`

- [ ] **Step 3**: Write minimal implementation in `path/to/new_file.py`

  ```python
  def [name]([params]):
      # minimal implementation
      pass
  ```

- [ ] **Step 4**: Run `<test-command>` — confirm it passes

  Expected: `✓ [test name]`

- [ ] **Step 5**: Commit using the `git-commits` skill

  `git commit -m "<type>(<scope>): <message>"`
