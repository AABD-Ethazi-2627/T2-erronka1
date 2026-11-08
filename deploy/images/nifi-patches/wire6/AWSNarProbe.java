import java.lang.reflect.InvocationTargetException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import org.apache.nifi.nar.NarClassLoader;

/** Installed NiFi NarClassLoader, original manifest parents, explicit class origins. */
public final class AWSNarProbe {
    private static final Map<String, String> parents = new HashMap<>();
    private static final Map<String, NarClassLoader> loaders = new HashMap<>();
    private static Path root;

    private static NarClassLoader loader(String id) throws Exception {
        if (!loaders.containsKey(id)) {
            String parent = parents.get(id);
            ClassLoader upstream = parent == null || parent.isEmpty()
                    ? (id.equals("nifi-jetty-nar") ? AWSNarProbe.class.getClassLoader() : loader("nifi-jetty-nar"))
                    : loader(parent);
            loaders.put(id, new NarClassLoader(root.resolve(id).toFile(), upstream));
        }
        return loaders.get(id);
    }

    public static void main(String[] args) throws Exception {
        root = Path.of(args[0]);
        for (String row : Files.readAllLines(Path.of(args[1]))) {
            String[] fields = row.split("\t", -1);
            parents.put(fields[0], fields[1]);
        }
        try {
            NarClassLoader aws = loader("nifi-aws-nar");
            String[] origins = {"wire-runtime-jvm-" + args[2] + ".jar",
                    "wire-schema-jvm-" + args[2] + ".jar", "schema-registry-serde-" + args[3] + ".jar"};
            int origin = 0;
            for (String type : new String[] {"com.squareup.wire.ProtoReader",
                    "com.squareup.wire.schema.internal.parser.ProtoFileElement",
                    "com.amazonaws.services.schemaregistry.utils.apicurio.FileDescriptorUtils"}) {
                Class<?> loaded = Class.forName(type, true, aws);
                if (loaded.getClassLoader() != aws) {
                    throw new AssertionError("class escaped AWS NAR loader: " + type);
                }
                Path actual = Path.of(loaded.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
                Path expected = root.resolve("nifi-aws-nar/NAR-INF/bundled-dependencies").resolve(origins[origin++]).toRealPath();
                if (!actual.equals(expected)) {
                    throw new AssertionError("class origin mismatch: " + type + " " + actual);
                }
                System.out.println("ORIGIN " + type + " " + loaded.getProtectionDomain().getCodeSource().getLocation());
            }
            for (int i = 4; i < args.length; i++) {
                try {
                    Class.forName(args[i], true, aws).getMethod("main", String[].class)
                            .invoke(null, (Object) new String[0]);
                } catch (InvocationTargetException error) {
                    throw new AssertionError("real NAR consumer failed", error.getCause());
                }
            }
        } finally {
            for (NarClassLoader current : loaders.values()) {
                current.close();
            }
        }
    }
}
