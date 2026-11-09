import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.apache.nifi.nar.NarClassLoader;

/** Instantiates installed NAR loaders only; no NiFi server/processor scheduling. */
public class NarOtelProbe {
    static final Map<String,String> parents=new LinkedHashMap<>();
    static final Map<String,NarClassLoader> loaders=new LinkedHashMap<>();
    static Path root;
    static NarClassLoader loader(String id) throws Exception {
        if(loaders.containsKey(id))return loaders.get(id);
        String parentId=parents.get(id);
        ClassLoader parent;
        if(parentId==null || parentId.isBlank())
            parent=!id.equals("nifi-jetty-nar") && Files.isDirectory(root.resolve("nifi-jetty-nar")) ? loader("nifi-jetty-nar") : NarOtelProbe.class.getClassLoader();
        else parent=loader(parentId);
        NarClassLoader result=new NarClassLoader(root.resolve(id).toFile(),parent);
        loaders.put(id,result);return result;
    }
    static void origin(Class<?> type,String file,String expected) throws Exception {
        if (!(type.getClassLoader() instanceof NarClassLoader))
            throw new AssertionError("flat classpath contamination: "+type.getName());
        Path p=Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI());
        if(!p.getFileName().toString().equals(file) || !p.toRealPath().startsWith(root.toRealPath()))
            throw new AssertionError("unexpected code origin "+p);
        byte[] actual=MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p));
        if(!HexFormat.of().formatHex(actual).equals(expected))throw new AssertionError("loaded jar drift "+p);
        System.out.println("origin "+type.getName()+" "+p+" sha256="+expected+" loader="+type.getClassLoader());
    }
    public static void main(String[] args) throws Exception {
        root=Path.of(args[0]);
        for(String line:Files.readAllLines(Path.of(args[1]))) {
            String[] fields=line.split("\t",-1);parents.put(fields[0],fields[1]);
        }
        try {
            NarClassLoader cl=loader("nifi-gcp-nar");
            String[] types={"io.opentelemetry.api.OpenTelemetry","io.opentelemetry.context.Context",
                            "io.opentelemetry.common.ComponentLoader"};
            for(int i=0;i<types.length;i++)origin(Class.forName(types[i],false,cl),args[2+i*2],args[3+i*2]);
            Class<?> sdk=Class.forName("io.opentelemetry.sdk.OpenTelemetrySdk",false,cl);
            if(!(sdk.getClassLoader() instanceof NarClassLoader))throw new AssertionError("SDK outside NAR");
            System.out.println("SDK origin="+sdk.getProtectionDomain().getCodeSource().getLocation());
            Class<?> exercise=Class.forName("OtelExercise",true,cl);
            try {exercise.getMethod("main",String[].class).invoke(null,(Object)new String[0]);}
            catch(java.lang.reflect.InvocationTargetException e){throw new AssertionError("real NAR exercise",e.getCause());}
            for(int i=8;i<args.length;i++) {
                Class<?> consumer=Class.forName(args[i],false,cl);
                if(!(consumer.getClassLoader() instanceof NarClassLoader))throw new AssertionError("consumer outside NAR");
                System.out.println("actual consumer="+consumer.getName()+" origin="+
                    consumer.getProtectionDomain().getCodeSource().getLocation());
            }
        } finally {
            var all=new ArrayList<>(loaders.values());Collections.reverse(all);
            for(NarClassLoader cl:all)cl.close();
        }
    }
}
