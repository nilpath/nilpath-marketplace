# Plan: Hello World Utility

## Goal

Add a `hello_world()` function to `src/utils.py` that returns the string `"Hello, World!"`.

## Architecture

Single pure function in `src/utils.py`. Covered by one unit test in `tests/test_utils.py`.

## Tech Stack

- **Language**: Python 3.11
- **Test runner**: `python -m pytest`

## Tasks

### Task 001: Implement hello_world function

**Files**:

- Create: `src/utils.py`
- Test: `tests/test_utils.py`

- [ ] **Step 1**: Write failing test in `tests/test_utils.py`

  ```python
  def test_hello_world():
      from src.utils import hello_world
      assert hello_world() == "Hello, World!"
  ```

- [ ] **Step 2**: Run `python -m pytest tests/test_utils.py` — confirm it fails

  Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3**: Write minimal implementation in `src/utils.py`

  ```python
  def hello_world() -> str:
      return "Hello, World!"
  ```

- [ ] **Step 4**: Run `python -m pytest tests/test_utils.py` — confirm it passes

  Expected: `1 passed`

- [ ] **Step 5**: Commit using the `git-commits` skill

  `git commit -m "feat(utils): add hello_world function"`
