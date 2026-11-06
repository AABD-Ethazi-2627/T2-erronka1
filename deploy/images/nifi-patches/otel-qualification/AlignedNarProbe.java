import java.nio.file.*;
import java.util.*;
import org.apache.nifi.nar.NarClassLoader;

/** Installed loader, explicit SPI loader, no provider attributes/server/scheduling. */
public class AlignedNarProbe {
    static String rootCause(Throwable failure) {
        Set<Throwable> seen=Collections.newSetFromMap(new IdentityHashMap<>());
        while(failure.getCause()!=null && seen.add(failure)) failure=failure.getCause();
        return failure.getClass().getName();
    }
    static void initializeConsumer(String name, NarClassLoader loader) {
        try {
            Class<?> type=Class.forName(name,true,loader);
            if(!(type.getClassLoader() instanceof NarClassLoader))throw new AssertionError("flat consumer");
            System.out.println("consumer-init\t"+name+"\tPASS\t-");
        } catch(Throwable failure) {
            System.out.println("consumer-init\t"+name+"\tFAIL\t"+rootCause(failure));
        }
    }
    @SuppressWarnings({"unchecked", "rawtypes"})
    static void providers(NarClassLoader loader) throws Exception {
        Class<?> service=Class.forName("io.opentelemetry.sdk.autoconfigure.spi.ResourceProvider",true,loader);
        Iterator<?> iterator=ServiceLoader.load((Class)service,loader).iterator();
        int count=0;
        while(iterator.hasNext()) {
            if(++count>16)throw new AssertionError("provider budget");
            Object provider=iterator.next(); // Instantiate, never invoke getAttributes.
            Class<?> type=provider.getClass();
            if(!(type.getClassLoader() instanceof NarClassLoader))throw new AssertionError("flat provider");
            System.out.println("service-provider\t"+type.getName()+"\tPASS\t-");
        }
        if(count==0)throw new AssertionError("vacuous ResourceProvider traversal");
        System.out.println("service-result\tPASS\t"+count);
    }
    public static void main(String[] args) throws Exception {
        NarOtelProbe.root=Path.of(args[0]);
        for(String line:Files.readAllLines(Path.of(args[1]))) {
            String[] fields=line.split("\t",-1);NarOtelProbe.parents.put(fields[0],fields[1]);
        }
        String[] types={"io.opentelemetry.api.OpenTelemetry","io.opentelemetry.context.Context",
            "io.opentelemetry.common.ComponentLoader","io.opentelemetry.sdk.OpenTelemetrySdk",
            "io.opentelemetry.sdk.common.CompletableResultCode","io.opentelemetry.sdk.trace.SdkTracerProvider",
            "io.opentelemetry.sdk.metrics.SdkMeterProvider","io.opentelemetry.sdk.logs.SdkLoggerProvider",
            "io.opentelemetry.sdk.autoconfigure.spi.ConfigProperties"};
        try {
            NarClassLoader loader=NarOtelProbe.loader("nifi-gcp-nar");
            for(int i=0;i<types.length;i++)
                NarOtelProbe.origin(Class.forName(types[i],false,loader),args[2+i*2],args[3+i*2]);
            // Fail for the real ConfigUtil mismatch before claiming later coverage.
            for(String exercise:new String[]{"ConfigPropertiesProbe","OtelExercise"}) {
                Class<?> type=Class.forName(exercise,true,loader);
                try { type.getMethod("main",String[].class).invoke(null,(Object)new String[0]); }
                catch(java.lang.reflect.InvocationTargetException e) {
                    throw new AssertionError("real NAR consumer "+exercise,e.getCause());
                }
            }
            for(int i=20;i<args.length;i++) initializeConsumer(args[i],loader);
            providers(loader);
        } finally {
            var list=new ArrayList<>(NarOtelProbe.loaders.values());Collections.reverse(list);
            for(NarClassLoader loader:list)loader.close();
        }
    }
}
