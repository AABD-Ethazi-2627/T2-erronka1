import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import org.apache.nifi.nar.NarClassLoader;

/** Uses installed NiFi NarClassLoader; never starts a processor or server. */
public class NarProbe {
    static final Map<String,String> parents=new HashMap<>();
    static final Map<String,NarClassLoader> loaders=new HashMap<>();
    static final Set<String> loading=new HashSet<>();
    static Path root;
    static NarClassLoader loader(String id) throws Exception {
        if(loaders.containsKey(id))return loaders.get(id);
        if(!parents.containsKey(id))throw new AssertionError("missing NAR parent record: "+id);
        if(!loading.add(id))throw new AssertionError("NAR parent cycle: "+id);
        try {
            String p=parents.get(id);
            // Root NARs delegate to Jetty; Jetty itself uses the system loader.
            ClassLoader parent=(p==null||p.isBlank())
                ?(id.equals("nifi-jetty-nar")?NarProbe.class.getClassLoader():loader("nifi-jetty-nar"))
                :loader(p);
            NarClassLoader cl=new NarClassLoader(root.resolve(id).toFile(),parent);
            if(cl.getParent()!=parent)throw new AssertionError("NAR parent mismatch: "+id);
            loaders.put(id,cl);return cl;
        } finally {loading.remove(id);}
    }
    static Path assertOrigin(Class<?> type,NarClassLoader expectedLoader,String id,String artifact,String version) throws Exception {
        if(type.getClassLoader()!=expectedLoader)throw new AssertionError("unexpected defining NAR: "+type.getName());
        var source=type.getProtectionDomain().getCodeSource();
        if(source==null)throw new AssertionError("missing code source: "+type.getName());
        Path actual=Path.of(source.getLocation().toURI()).toRealPath();
        Path expected=root.resolve(id).resolve("NAR-INF/bundled-dependencies")
            .resolve(artifact+"-"+version+".jar").toRealPath();
        if(!actual.equals(expected))throw new AssertionError("code source mismatch: "+actual+" expected "+expected);
        return actual;
    }
    public static void main(String[] args) throws Exception {
        if(args[0].equals("jdk")) {
            Path base=FileSystems.getFileSystem(URI.create("jrt:/")).getPath("/modules/java.base");
            Path out=Path.of(args[1]);int count=0;
            try(var paths=Files.walk(base)) {
                for(Path p:paths.filter(x->x.toString().endsWith(".class")).toList()) {
                    Path dest=out.resolve(base.relativize(p).toString());Files.createDirectories(dest.getParent());Files.copy(p,dest);count++;
                }
            }
            System.out.println("actual-image-jdk-classes="+count+" java="+Runtime.version()+" javaHome="+System.getProperty("java.home"));return;
        }
        root=Path.of(args[0]);
        for(String line:Files.readAllLines(Path.of(args[1]))) {
            String[] p=line.split("\t",-1);parents.put(p[0],p[1]);
        }
        String id=args[2],family=args[3],expected=args[4];boolean fixed=Boolean.parseBoolean(args[5]);
        NarClassLoader cl=loader(id);
        String ns=family.equals("2")?"com.fasterxml.jackson":"tools.jackson";
        Class<?> mapper=Class.forName(ns+".databind.ObjectMapper",false,cl);
        Class<?> core=Class.forName(ns+".core.json.PackageVersion",true,cl);
        Class<?> databind=Class.forName(ns+".databind.cfg.PackageVersion",true,cl);
        String cv=core.getField("VERSION").get(null).toString(),dv=databind.getField("VERSION").get(null).toString();
        if(!cv.equals(expected)||!dv.equals(expected))throw new AssertionError("shadowed version "+cv+"/"+dv+" expected "+expected);
        if(!(mapper.getClassLoader() instanceof NarClassLoader))throw new AssertionError("flat classpath contamination");
        Path mapperOrigin=assertOrigin(mapper,cl,id,"jackson-databind",expected);
        assertOrigin(core,cl,id,"jackson-core",expected);
        assertOrigin(databind,cl,id,"jackson-databind",expected);
        System.out.println("context="+id+" family="+family+" core="+cv+" databind="+dv+" mapperLoader="+mapper.getClassLoader()+" assertedOrigin="+mapperOrigin+" parent="+cl.getParent());
        Class<?> probe=Class.forName("Jackson"+family+"Probe",true,cl);
        try {probe.getMethod("main",String[].class).invoke(null,(Object)new String[]{String.valueOf(fixed),String.valueOf(family.equals("3")&&id.equals("nifi-jolt-nar")),"true"});}
        catch(java.lang.reflect.InvocationTargetException e) {throw new AssertionError("actual NAR probe failed",e.getCause());}
        for(int i=6;i<args.length;i++) {
            Class<?> consumer=Class.forName(args[i],false,cl);
            if(!(consumer.getClassLoader() instanceof NarClassLoader))throw new AssertionError("consumer outside NAR");
            System.out.println("actual-consumer-loaded="+consumer.getName()+" loader="+consumer.getClassLoader());
        }
        for(NarClassLoader c:loaders.values())c.close();
    }
}
