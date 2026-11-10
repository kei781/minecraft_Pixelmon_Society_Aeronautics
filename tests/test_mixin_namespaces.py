"""Config-discovery regressions; opaque class payloads are not JVM validation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_mixin_namespaces import manifest_configs, scan


class MixinNamespaceDiscovery(unittest.TestCase):
    def test_folded_manifest_unconventional_config_and_null_plugin(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.jar"
            with zipfile.ZipFile(path, "w") as jar:
                jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\nMixinConfigs: qa-con\r\n fig.json\r\n\r\n")
                jar.writestr("qa-config.json", json.dumps({"package": "fixture.mixin", "plugin": None}))
                jar.writestr("fixture/mixin/RuntimeHelper.class", b"opaque non-annotated class payload")
            result = scan(path)
        self.assertEqual(result["parse_errors"], [])
        self.assertEqual(result["config_count"], 1)
        config = result["configs"][0]
        self.assertEqual(config["discovery"], {"manifest": True, "name_convention": False})
        self.assertEqual(config["ordinary_top_level_candidates"], ["fixture/mixin/RuntimeHelper.class"])

    def test_only_main_manifest_section_registers_configs(self):
        manifest = b"Manifest-Version: 1.0\nMixinConfigs: first.json,sec\n ond.json\n\nName: entry\nMixinConfigs: inactive.json\n\n"
        self.assertEqual(manifest_configs(manifest), {"first.json", "second.json"})


if __name__ == "__main__":
    unittest.main()
