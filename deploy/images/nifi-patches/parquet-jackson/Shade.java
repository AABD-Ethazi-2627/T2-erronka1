/* Audited direct Apache Shade API. No Maven lifecycle or plugin discovery. */
import java.io.File;
import java.util.*;
import org.apache.maven.plugins.shade.*;
import org.apache.maven.plugins.shade.relocation.*;
import org.apache.maven.plugins.shade.resource.ServicesResourceTransformer;
public final class Shade {
  public static void main(String[] args) throws Exception {
    ShadeRequest request = new ShadeRequest();
    LinkedHashSet<File> jars = new LinkedHashSet<>();
    for (int i=1; i<args.length; i++) jars.add(new File(args[i]));
    request.setJars(jars);
    request.setUberJar(new File(args[0]));
    request.setShadeSourcesContent(false);
    List<Relocator> relocators = new ArrayList<>();
    relocators.add(new SimpleRelocator("com.fasterxml.jackson", "shaded.parquet.com.fasterxml.jackson", null, null));
    for (int v : new int[]{9,11,17,19,21,22}) {
      String prefix = "META-INF.versions."+v+".";
      relocators.add(new SimpleRelocator(prefix+"com.fasterxml.jackson", prefix+"shaded.parquet.com.fasterxml.jackson", null, null));
    }
    request.setRelocators(relocators);
    request.setFilters(List.of());
    request.setResourceTransformers(List.of(new ServicesResourceTransformer()));
    new DefaultShader().shade(request);
  }
}
