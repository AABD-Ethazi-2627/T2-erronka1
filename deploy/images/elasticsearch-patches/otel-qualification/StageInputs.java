/* VM-only source-image copy into a new private proof tree. No service or loader
 * initialization. Only measured module closure and boot library input files. */
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

public class StageInputs {
    static final Set<String> EXPECTED = Set.of("apm", "esql-datasource-gcs", "repository-gcs",
        "lang-painless", "workload-identity", "x-pack-autoscaling", "x-pack-core",
        "x-pack-encryption", "x-pack-esql", "x-pack-esql-core", "x-pack-ml");
    static Path source, target;
    static long total=0; static int count=0;
    static Properties props(Path path) throws Exception {
        var p=new Properties(); try(var stream=Files.newInputStream(path)){p.load(stream);}return p;
    }
    static void visit(String realm, Set<String> active, Set<String> found) throws Exception {
        if(active.contains(realm))throw new IllegalStateException("extension cycle");
        if(found.contains(realm))return;
        if(!EXPECTED.contains(realm))throw new IllegalStateException("unmeasured extension");
        active.add(realm);
        var p=props(source.resolve("modules").resolve(realm).resolve("plugin-descriptor.properties"));
        if(!p.getProperty("name").equals(realm))throw new IllegalStateException("descriptor identity");
        var extensions=p.getProperty("extended.plugins", "");
        if(!extensions.isEmpty())for(var e:extensions.split(","))visit(e,active,found);
        active.remove(realm);found.add(realm);
    }
    static void copy(Path path) throws Exception {
        if(Files.isSymbolicLink(path))throw new IllegalStateException("linked source");
        var relative=source.relativize(path);
        if(relative.toString().contains("\t")||relative.toString().contains("\n"))
            throw new IllegalStateException("unsafe TSV path");
        if(!Files.isRegularFile(path))throw new IllegalStateException("not regular input");
        long size=Files.size(path);total+=size;count++;
        if(count>3000||total>2L*1024*1024*1024||size>512L*1024*1024)
            throw new IllegalStateException("input copy budget");
        var output=target.resolve(relative);Files.createDirectories(output.getParent());
        var before=MessageDigest.getInstance("SHA-256");
        try(var in=Files.newInputStream(path);var out=Files.newOutputStream(output, StandardOpenOption.CREATE_NEW)){
            byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){before.update(b,0,n);out.write(b,0,n);}
        }
        var after=MessageDigest.getInstance("SHA-256");
        try(var in=Files.newInputStream(path)){byte[] b=new byte[65536];int n;
            while((n=in.read(b))!=-1)after.update(b,0,n);}
        var first=HexFormat.of().formatHex(before.digest());
        if(!first.equals(HexFormat.of().formatHex(after.digest())))throw new IllegalStateException("original drift");
        System.out.println("COPY\t"+relative+"\t"+size+"\t"+first);
    }
    static void directory(Path dir) throws Exception {
        if(Files.isSymbolicLink(dir))throw new IllegalStateException("linked directory");
        try(var files=Files.list(dir)){
            for(var file:files.sorted().toList()){
                if(Files.isSymbolicLink(file))throw new IllegalStateException("linked member");
                if(Files.isDirectory(file)){
                    // PluginBundle exposes root JARs and optional spi/ only.
                    if(file.getFileName().toString().equals("spi"))directory(file);
                    continue;
                }
                String name=file.getFileName().toString();
                if(name.endsWith(".jar")||name.endsWith("plugin-descriptor.properties")
                    ||name.equals("entitlement-policy.yaml"))copy(file);
            }
        }
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=2)throw new IllegalArgumentException("source home and fresh private output required");
        source=Path.of(args[0]);target=Path.of(args[1]);
        if(Files.exists(target))throw new IllegalStateException("refusing existing proof tree");
        var found=new TreeSet<String>();
        for(var root:List.of("apm","repository-gcs","esql-datasource-gcs"))visit(root,new HashSet<>(),found);
        if(!found.equals(EXPECTED))throw new IllegalStateException("measured extension graph drift");
        Files.createDirectory(target);
        directory(source.resolve("lib"));
        for(var realm:found)directory(source.resolve("modules").resolve(realm));
        System.out.println("STATUS\tstage-only\t"+count+"\t"+total+"\treplacement=null\truntime_approved=false");
    }
}
