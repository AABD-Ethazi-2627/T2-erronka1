import java.io.File;
import java.util.LinkedHashSet;
import java.util.List;
import org.apache.maven.plugins.shade.DefaultShader;
import org.apache.maven.plugins.shade.ShadeRequest;
import org.apache.maven.plugins.shade.filter.Filter;
import org.apache.maven.plugins.shade.relocation.SimpleRelocator;
import org.apache.maven.plugins.shade.resource.ServicesResourceTransformer;

/** Upstream Iceberg relocation rule, applied to complete official Guava inputs. */
public final class GuavaShade {
    public static void main(String[] args) throws Exception {
        ShadeRequest request = new ShadeRequest();
        request.setJars(new LinkedHashSet<>(List.of(new File(args[0]))));
        request.setUberJar(new File(args[1]));
        request.setShadeSourcesContent(false);
        request.setRelocators(List.of(new SimpleRelocator("com.google.common",
                "org.apache.iceberg.relocated.com.google.common", null, null)));
        request.setFilters(List.of(new Filter() {
            public boolean canFilter(File file) { return true; }
            public boolean isFiltered(String name) {
                return name.endsWith("module-info.class") || name.matches("META-INF/[^/]+\\.(SF|DSA|RSA)");
            }
            public void finished() { }
        }));
        request.setResourceTransformers(List.of(new ServicesResourceTransformer()));
        new DefaultShader().shade(request);
    }
}
