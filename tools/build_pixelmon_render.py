"""Build an authored-only, opt-in client renderer candidate from local pinned inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'compat/pixelmon-render'
PINS = {
    'Pixelmon-1.20.1-9.2.3-universal.jar': '8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a',
    'oculus-mc1.20.1-1.8.0.jar': '0945df0cba0f62b3901dd80c3268e5311b770ece78c78037a45db12ac0425fef',
    'embeddium-0.3.31+mc1.20.1.jar': 'eed3d1325f2acc2fd4e69bb495e5ccb91d962126ac5330f0582ebc2a3daf47fb',
}
CLIENT = 'net/minecraft/client/1.20.1-20230612.114412/client-1.20.1-20230612.114412-srg.jar'
CLIENT_SHA256 = 'e2e940fe7ca0a9fba5a5c11ad2cf3e2f7df91bbf51d12af22cdde7af18adc344'


def verify_inputs(folder, pins):
    paths = []
    for name, digest in pins.items():
        path = Path(folder) / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Pinned input differs: ' + name)
        paths.append(path)
    return paths


def fresh_output(path):
    path = Path(path)
    if (path.exists() or path.is_symlink() or path.suffix.lower() != '.jar'
            or 'mods' in (part.casefold() for part in path.resolve().parts)):
        raise ValueError('Fresh output JAR outside installed mods required')
    return path


def package_jar(classes, resources, output, prefix='dev/psa/pixelmonrender/', config='psa-pixelmon-render.mixins.json'):
    output = fresh_output(output)
    files = {'META-INF/MANIFEST.MF': ('Manifest-Version: 1.0\r\nFMLModType: MOD\r\n'
             + ('MixinConfigs: ' + config + '\r\n' if config else '') + '\r\n').encode()}
    class_count = 0
    for root, is_class in ((Path(classes), True), (Path(resources), False)):
        if root.is_symlink() or not root.is_dir():
            raise ValueError('Regular authored source directories required')
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink in authored tree')
            if not path.is_file():
                continue
            name = path.relative_to(root).as_posix()
            if is_class:
                if not name.startswith(prefix) or not name.endswith('.class'):
                    raise ValueError('Non-authored compiled entry: ' + name)
                class_count += 1
            if name in files:
                raise ValueError('Duplicate authored entry: ' + name)
            files[name] = path.read_bytes()
    if not class_count:
        raise ValueError('Compiled authored classes required')
    output.parent.mkdir(parents=True, exist_ok=True)
    # A hard link publishes the completed sibling file exclusively, without replacing a race winner.
    with tempfile.TemporaryDirectory(prefix='psa-render-', dir=output.parent) as directory:
        temporary = Path(directory)/'complete.jar'
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, (1980,1,1,0,0,0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
        os.link(temporary, output)
    return {'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'entries': sorted(files)}


def compile_java(javac, sources, classpath, destination, directory):
    args = ['-proc:none', '--release', '17', '-encoding', 'UTF-8', '-cp', classpath,
            '-d', str(destination), *(str(path) for path in sources)]
    argfile = Path(directory)/'javac.args'
    argfile.write_text('\n'.join('"' + arg.replace('\\','/').replace('"','\\"') + '"' for arg in args), encoding='utf-8')
    subprocess.run([str(javac), '@' + str(argfile)], check=True)


def build(libraries, mods, java_home, output, run_tests=False):
    output = fresh_output(output)
    libraries, java_home = Path(libraries), Path(java_home)
    mod_paths = verify_inputs(mods, PINS)
    client = verify_inputs(libraries, {CLIENT: CLIENT_SHA256})[0]
    executable = '.exe' if os.name == 'nt' else ''
    javac, java = java_home/('bin/javac'+executable), java_home/('bin/java'+executable)
    version = subprocess.check_output([str(javac), '-version'], text=True).strip()
    if not version.startswith('javac 17.'):
        raise ValueError('Java 17 compiler required')
    classpath = os.pathsep.join(str(path) for path in [client, *sorted(libraries.rglob('*.jar')), *mod_paths])
    with tempfile.TemporaryDirectory(prefix='psa-render-build-') as directory:
        classes = Path(directory)/'classes'
        compile_java(javac, sorted(SOURCE.rglob('*.java')), classpath, classes, directory)
        if run_tests:
            tests = Path(directory)/'tests'
            compile_java(javac, [ROOT/'tests/PixelmonVertexEncodingTest.java'],
                         str(classes)+os.pathsep+classpath, tests, directory)
            subprocess.run([str(java), '-cp', os.pathsep.join((str(tests),str(classes),classpath)),
                            'dev.psa.pixelmonrender.PixelmonVertexEncodingTest'], check=True)
        receipt = package_jar(classes, SOURCE/'resources', output)
    return dict(receipt, compiler=version, inputs=PINS, minecraft_client_sha256=hashlib.sha256(client.read_bytes()).hexdigest(),
                opt_in='-Dpsa.pixelmon.fastVertices=true', tests_run=run_tests)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('libraries','mods','java-home','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--test', action='store_true', help='Compare native stores to real original Minecraft consumer')
    args = parser.parse_args()
    print(json.dumps(build(args.libraries,args.mods,args.java_home,args.output,args.test), indent=2))
