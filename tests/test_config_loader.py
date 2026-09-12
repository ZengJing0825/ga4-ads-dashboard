import unittest

import _paths  # noqa: F401
from config_loader import ConfigError, parse_yaml

DOC = """
# comment
name: demo   # trailing comment
count: 3
ratio: 0.5
flag: true
nothing: null
quoted: 'it''s # not a comment'
dq: "a\\"b"
regex: '\\busecase\\b'
tags: [a, 'b c', 3]
rule: {metric: cpa, above: 12, min_spend: 400}
items:
  - id: 1
    name: first
    params: []
  - id: 2
    name: second
nested:
  inner:
    - x
    - y
"""


class ParserTest(unittest.TestCase):
    def test_subset(self):
        d = parse_yaml(DOC)
        self.assertEqual(d["name"], "demo")
        self.assertEqual(d["count"], 3)
        self.assertEqual(d["ratio"], 0.5)
        self.assertIs(d["flag"], True)
        self.assertIsNone(d["nothing"])
        self.assertEqual(d["quoted"], "it's # not a comment")
        self.assertEqual(d["dq"], 'a"b')
        self.assertEqual(d["regex"], r"\busecase\b")
        self.assertEqual(d["tags"], ["a", "b c", 3])
        self.assertEqual(d["rule"], {"metric": "cpa", "above": 12, "min_spend": 400})
        self.assertEqual(d["items"], [{"id": 1, "name": "first", "params": []}, {"id": 2, "name": "second"}])
        self.assertEqual(d["nested"], {"inner": ["x", "y"]})

    def test_bad_indent_raises(self):
        with self.assertRaises(ConfigError):
            parse_yaml("a: 1\n   b: 2\n")

    def test_matches_pyyaml_on_shipped_configs(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        import datetime
        import glob
        import os

        def norm(x):
            if isinstance(x, dict):
                return {k: norm(v) for k, v in x.items()}
            if isinstance(x, list):
                return [norm(v) for v in x]
            if isinstance(x, datetime.date):
                return x.isoformat()
            return x

        for path in glob.glob(os.path.join(_paths.ROOT_DIR, "config", "*.yaml")):
            with open(path) as f:
                text = f.read()
            self.assertEqual(parse_yaml(text), norm(yaml.safe_load(text)), path)


if __name__ == "__main__":
    unittest.main()
