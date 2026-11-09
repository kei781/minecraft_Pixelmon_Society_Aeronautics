import java.nio.charset.StandardCharsets;
import java.util.jar.JarFile;
import java.util.regex.Pattern;
import org.apache.maven.artifact.versioning.DefaultArtifactVersion;
import org.apache.maven.artifact.versioning.VersionRange;

/** Validate the exact compiled observer dependency with Forge's Maven version semantics. */
public final class JadeObserverMetadataTest {
    public static void main(String[] args) throws Exception {
        try (JarFile jade = new JarFile(args[0]); JarFile observer = new JarFile(args[1])) {
            String actual = jade.getManifest().getMainAttributes().getValue("Implementation-Version");
            if (!"11.13.2+forge".equals(actual)) throw new AssertionError("Unexpected pinned Jade version: " + actual);
            String metadata = new String(observer.getInputStream(observer.getJarEntry("META-INF/mods.toml")).readAllBytes(),
                    StandardCharsets.UTF_8);
            var matcher = Pattern.compile("versionRange=\"([^\"]+)\"").matcher(metadata);
            if (!matcher.find()) throw new AssertionError("Missing compiled dependency range");
            String range = matcher.group(1);
            if (!"[11.13.2+forge]".equals(range)) throw new AssertionError("Dependency is not exact: " + range);
            var version = new DefaultArtifactVersion(actual);
            if (!VersionRange.createFromVersionSpec(range).containsVersion(version))
                throw new AssertionError("Compiled observer cannot load with pinned Jade");
            if (VersionRange.createFromVersionSpec("[11.13.2]").containsVersion(version))
                throw new AssertionError("Negative control did not reproduce0.1 rejection");
            System.out.println("Jade observer metadata: exact0.2 dependency accepted; original0.1 dependency rejected");
        }
    }
}
