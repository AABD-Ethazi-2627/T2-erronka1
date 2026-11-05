/* Local audited driver. Invokes only Apache Shade's API, never Maven lifecycle. */
import java.io.File;
import java.util.*;
import org.apache.maven.plugins.shade.*;
import org.apache.maven.plugins.shade.filter.Filter;
import org.apache.maven.plugins.shade.relocation.*;
import org.apache.maven.plugins.shade.resource.*;
public final class Shade {
  public static void main(String[] args) throws Exception {
    ShadeRequest r = new ShadeRequest();
    r.setJars(new LinkedHashSet<>(List.of(new File(args[0]))));
    r.setUberJar(new File(args[1]));
    r.setShadeSourcesContent(false);
    r.setRelocators(List.of(
      new SimpleRelocator("com.zaxxer.hikari", "com.hazelcast.shaded.com.zaxxer.hikari", null, null),
      new SimpleRelocator("tools.jackson", "com.hazelcast.shaded.tools.jackson", null, null),
      new SimpleRelocator("com.fasterxml.jackson", "com.hazelcast.shaded.com.fasterxml.jackson", null,
        List.of("com.fasterxml.jackson.annotation.*")),
      new SimpleRelocator("(?<=META-INF/versions/\\d{1,2}/)com/fasterxml/jackson(?!/annotation)",
        "com/hazelcast/shaded/com/fasterxml/jackson", null, null, true),
      new SimpleRelocator("(?<=META-INF/versions/\\d{1,2}/)tools/jackson(?!/annotation)",
        "com/hazelcast/shaded/tools/jackson", null, null, true)));
    r.setFilters(List.of(new Filter() {
      public boolean canFilter(File f) { return true; }
      public boolean isFiltered(String n) {
        return n.endsWith("module-info.class") || n.startsWith("META-INF/versions/9/")
          || n.startsWith("META-INF/versions/11/") || Set.of("LICENSE", "NOTICE",
          "META-INF/LICENSE", "META-INF/MANIFEST.MF", "META-INF/THIRD-PARTY.txt",
          "META-INF/DEPENDENCIES", "overview.html").contains(n)
          || n.matches("META-INF/[^/]+\\.(SF|DSA|RSA)");
      }
      public void finished() {}
    }));
    r.setResourceTransformers(List.of(new ServicesResourceTransformer(), new ApacheNoticeResourceTransformer()));
    new DefaultShader().shade(r);
  }
}
