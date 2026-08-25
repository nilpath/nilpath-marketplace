# Plan: Three String Utilities

## Goal

Add three small string-utility functions to `src/strings.py`, each covered by its own unit test. The three tasks deliberately follow the same pattern to test that the executing-plan skill does **not** bundle them.

## Architecture

Three pure functions in `src/strings.py`. One unit test per function in `tests/test_strings.py`.

## Tech Stack

- **Language**: Python 3.11
- **Test runner**: `python -m pytest`

## Tasks

### Task 001: Implement reverse_string

**Files**:

- Create: `src/strings.py`
- Test: `tests/test_strings.py`

- [ ] **Step 1**: Write failing test in `tests/test_strings.py`

  ```python
  def test_reverse_string():
      from src.strings import reverse_string
      assert reverse_string("abc") == "cba"
  ```

- [ ] **Step 2**: Run `python -m pytest tests/test_strings.py::test_reverse_string` — confirm it fails

- [ ] **Step 3**: Implement `reverse_string(s: str) -> str` in `src/strings.py`

- [ ] **Step 4**: Run the test — confirm it passes

- [ ] **Step 5**: Commit using the `git-commits` skill

  `git commit -m "feat(strings): add reverse_string"`

---

### Task 002: Implement upper_string

**Files**:

- Modify: `src/strings.py`
- Test: `tests/test_strings.py`

- [ ] **Step 1**: Write failing test

  ```python
  def test_upper_string():
      from src.strings import upper_string
      assert upper_string("abc") == "ABC"
  ```

- [ ] **Step 2**: Run `python -m pytest tests/test_strings.py::test_upper_string` — confirm it fails

- [ ] **Step 3**: Implement `upper_string(s: str) -> str` in `src/strings.py`

- [ ] **Step 4**: Run the test — confirm it passes

- [ ] **Step 5**: Commit using the `git-commits` skill

  `git commit -m "feat(strings): add upper_string"`

---

### Task 003: Implement strip_string

**Files**:

- Modify: `src/strings.py`
- Test: `tests/test_strings.py`

- [ ] **Step 1**: Write failing test

  ```python
  def test_strip_string():
      from src.strings import strip_string
      assert strip_string("  abc  ") == "abc"
  ```

- [ ] **Step 2**: Run `python -m pytest tests/test_strings.py::test_strip_string` — confirm it fails

- [ ] **Step 3**: Implement `strip_string(s: str) -> str` in `src/strings.py`

- [ ] **Step 4**: Run the test — confirm it passes

- [ ] **Step 5**: Commit using the `git-commits` skill

  `git commit -m "feat(strings): add strip_string"`
