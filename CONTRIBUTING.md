# Contributing

Contributions to `graph-pes` via pull requests are very welcome! Here's how to get started.

---

**Getting started**

First fork the library on GitHub.

Then clone and install the library in development mode:

```bash
git clone https://github.com/<your-username-here>/graph-pes.git
cd graph-pes
pip install -e ".[dev]"
```

Then install the pre-commit hooks:

```bash
pre-commit install
```

These hooks use ruff to format and lint the code.

---

**If you're making changes to the code:**

Now make your changes. Make sure to include additional tests if necessary.

Next verify the tests all pass:

```bash
pip install pytest
pytest
```

Then push your changes back to your fork of the repository:

```bash
git push
```

Finally, open a pull request on GitHub!

---

**If you're making changes to the documentation:**

Make your changes. You can then build the documentation by doing

```bash
pip install -e ".[docs]"
sphinx-autobuild docs/source docs/build
```

You can then see your local copy of the documentation by navigating to `localhost:8000` in a web browser.
Any time you save changes to the documentation, these will shortly be reflected in the browser!