import java.lang.reflect.InvocationTargetException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import org.apache.nifi.nar.NarClassLoader;

/** Exercises bounded component probes through installed NiFi loaders. No scheduling. */
public final class InstalledFamilyProbe {
    private static final Map<String, String> parents = new LinkedHashMap<>();
    private static final Map<String, NarClassLoader> loaders = new LinkedHashMap<>();
    private static Path root;

    private static NarClassLoader loader(String id) throws Exception {
        if (!loaders.containsKey(id)) {
            Path folder = root.resolve(id);
            if (!Files.isDirectory(folder.resolve("NAR-INF/bundled-dependencies"))) {
                throw new AssertionError("missing installed NAR: " + folder);
            }
            String parent = parents.get(id);
            ClassLoader upstream = parent == null || parent.isBlank()
                    ? (id.equals("nifi-jetty-nar") ? InstalledFamilyProbe.class.getClassLoader()
                            : loader("nifi-jetty-nar")) : loader(parent);
            loaders.put(id, new NarClassLoader(folder.toFile(), upstream));
        }
        return loaders.get(id);
    }

    public static void main(String[] args) throws Exception {
        root = Path.of(args[0]);
        for (String line : Files.readAllLines(Path.of(args[1]))) {
            String[] row = line.split("\t", -1);
            parents.put(row[0], row[1]);
        }
        try {
            NarClassLoader selected = loader(args[2]);
            Thread.currentThread().setContextClassLoader(selected);
            for (String line : Files.readAllLines(Path.of(args[3]))) {
                String[] row = line.split("\t", -1);
                Class<?> type = Class.forName(row[0], false, selected);
                if (!(type.getClassLoader() instanceof NarClassLoader)) {
                    throw new AssertionError("flat classpath: " + row[0]);
                }
                Path actual = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
                if (!actual.equals(Path.of(row[1]).toRealPath()) || !HexFormat.of().formatHex(
                        MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(actual))).equals(row[2])) {
                    throw new AssertionError("wrong installed origin: " + row[0] + " " + actual);
                }
                System.out.println("ORIGIN " + row[0] + " " + actual + " sha256=" + row[2]);
            }
            for (int i = 4; i < args.length; i++) {
                try {
                    Class.forName(args[i], true, selected).getMethod("main", String[].class)
                            .invoke(null, (Object) new String[0]);
                } catch (InvocationTargetException failure) {
                    throw new AssertionError("installed consumer failed: " + args[i], failure.getCause());
                }
            }
        } finally {
            Thread.currentThread().setContextClassLoader(InstalledFamilyProbe.class.getClassLoader());
            var reverse = new ArrayList<>(loaders.values());
            Collections.reverse(reverse);
            for (NarClassLoader current : reverse) current.close();
        }
    }
}
