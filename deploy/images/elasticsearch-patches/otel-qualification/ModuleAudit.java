/* Reads installed artifacts only. Does not create loaders, initialize consumers,
 * start Elasticsearch, attach the agent, or send exporter traffic. */
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.lang.module.*;
import java.util.*;
import java.util.jar.*;

public class ModuleAudit {
    static String digest(byte[] data) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
    }
    static String digest(Path path) throws Exception {
        var md = MessageDigest.getInstance("SHA-256");
        try (var in = Files.newInputStream(path)) {
            byte[] bytes = new byte[65536]; int n;
            while ((n = in.read(bytes)) != -1) md.update(bytes, 0, n);
        }
        return HexFormat.of().formatHex(md.digest());
    }
    static void emit(String kind, Object... values) {
        var result = new StringJoiner("\t"); result.add(kind);
        for (var value : values) {
            String text = String.valueOf(value);
            if (text.contains("\t") || text.contains("\n") || text.contains("\r"))
                throw new IllegalArgumentException("unsafe TSV value");
            result.add(text);
        }
        System.out.println(result);
    }
    static List<Path> jars(Path dir) throws Exception {
        try (var files = Files.list(dir)) {
            return files.filter(p -> p.toString().endsWith(".jar")).sorted().toList();
        }
    }
    static Properties properties(Path path) throws Exception {
        var props = new Properties();
        try (var input = Files.newInputStream(path)) { props.load(input); }
        return props;
    }
    static void auditJar(String realm, Path jar) throws Exception {
        if (Files.isSymbolicLink(jar)) throw new IllegalStateException("linked JAR");
        emit("JAR", realm, jar.getFileName(), Files.size(jar), digest(jar));
        Set<String> entries = new HashSet<>(); int classes=0, otel=0, nested=0;
        try (var zip = new JarFile(jar.toFile(), false, JarFile.OPEN_READ, Runtime.version())) {
            var enumeration = zip.entries();
            while (enumeration.hasMoreElements()) {
                var entry = enumeration.nextElement(); String name = entry.getName();
                if (!entries.add(name)) throw new IllegalStateException("duplicate ZIP entry");
                if (entries.size() > 100000 || name.startsWith("/") || name.contains("\\")
                    || Arrays.asList(name.split("/")).contains(".."))
                    throw new IllegalStateException("unsafe or oversized ZIP");
                if (name.endsWith(".class")) { classes++; if (name.contains("io/opentelemetry/")) otel++; }
                if (name.endsWith(".jar")) nested++;
                if (name.startsWith("META-INF/services/") && !entry.isDirectory()) {
                    if (entry.getSize() > 65536) throw new IllegalStateException("service metadata budget");
                    emit("SERVICE", realm, jar.getFileName(), name, digest(zip.getInputStream(entry).readAllBytes()));
                }
            }
            var manifest = zip.getManifest();
            if (manifest != null) emit("MANIFEST", realm, jar.getFileName(),
                Objects.toString(manifest.getMainAttributes().getValue("Automatic-Module-Name"), ""),
                Objects.toString(manifest.getMainAttributes().getValue("Multi-Release"), ""));
        }
        emit("ENTRIES", realm, jar.getFileName(), classes, otel, nested);
        // ModuleFinder is used individually so silent duplicate-name masking cannot hide a JAR.
        var refs = ModuleFinder.of(jar).findAll();
        if (refs.size() != 1) throw new IllegalStateException("not one module descriptor");
        var descriptor = refs.iterator().next().descriptor();
        emit("MODULE", realm, jar.getFileName(), descriptor.name(), descriptor.isAutomatic(),
            descriptor.rawVersion().orElse(""));
        for (var requirement : descriptor.requires().stream().sorted(Comparator.comparing(ModuleDescriptor.Requires::name)).toList())
            emit("REQUIRES", realm, jar.getFileName(), requirement.name(), requirement.modifiers().toString());
        for (var exported : descriptor.exports().stream().sorted(Comparator.comparing(ModuleDescriptor.Exports::source)).toList())
            emit("EXPORTS", realm, jar.getFileName(), exported.source(), String.join(",", new TreeSet<>(exported.targets())));
        for (var use : new TreeSet<>(descriptor.uses())) emit("USES", realm, jar.getFileName(), use);
        for (var provision : descriptor.provides().stream().sorted(Comparator.comparing(ModuleDescriptor.Provides::service)).toList())
            emit("PROVIDES", realm, jar.getFileName(), provision.service(), String.join(",", provision.providers()));
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("expected Elasticsearch home");
        Path home = Path.of(args[0]);
        emit("JAVA", System.getProperty("java.version"), Runtime.version().feature());
        for (String realm : List.of("apm", "repository-gcs", "esql-datasource-gcs")) {
            Path dir = home.resolve("modules").resolve(realm);
            Path descriptor = dir.resolve("plugin-descriptor.properties");
            var props = properties(descriptor);
            if (!props.getProperty("name").equals(realm)) throw new IllegalStateException("descriptor identity");
            emit("REALM", realm, props.getProperty("classname", ""), props.getProperty("modulename", ""),
                props.getProperty("extended.plugins", ""), digest(descriptor));
            Path policy = dir.resolve("entitlement-policy.yaml");
            emit("POLICY", realm, digest(policy));
            for (var jar : jars(dir)) auditJar(realm, jar);
        }
        // Capture extension descriptors and SPI URL boundaries without pretending they are qualified.
        try (var dirs = Files.list(home.resolve("modules"))) {
            for (var dir : dirs.sorted().toList()) {
                Path descriptor = dir.resolve("plugin-descriptor.properties");
                if (!Files.isRegularFile(descriptor)) continue;
                var props = properties(descriptor);
                emit("GRAPH", dir.getFileName(), props.getProperty("modulename", ""),
                    props.getProperty("extended.plugins", ""), Files.isDirectory(dir.resolve("spi")), digest(descriptor));
            }
        }
        // Hash actual installed loader implementation; upstream source pin alone is not byte equivalence.
        for (var jar : jars(home.resolve("lib"))) {
            try (var zip = new JarFile(jar.toFile(), false)) {
                var entry = zip.getJarEntry("org/elasticsearch/plugins/PluginsLoader.class");
                if (entry != null) emit("LOADER", jar.getFileName(), digest(jar), digest(zip.getInputStream(entry).readAllBytes()));
            }
        }
        emit("STATUS", "inventory-only", "replacement=null", "runtime_approved=false");
    }
}
