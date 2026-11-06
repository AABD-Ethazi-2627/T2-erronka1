import java.nio.file.*;
import java.util.*;
import org.apache.nifi.nar.NarClassLoader;
import java.net.URLClassLoader;

/** Installed loader, explicit SPI loader, no provider attributes/server/scheduling. */
public class AlignedNarProbe {
    static String rootCause(Throwable failure) {
        Set<Throwable> seen=Collections.newSetFromMap(new IdentityHashMap<>());
        while(failure.getCause()!=null && seen.add(failure)) failure=failure.getCause();
        return failure.getClass().getName();
    }
    static void initializeConsumer(String name, ClassLoader loader, Map<String,String[]> origins) {
        try {
            Class<?> type=Class.forName(name,true,loader);
            if(!(type.getClassLoader() instanceof NarClassLoader))throw new AssertionError("flat consumer");
            String[] pin=origins.get(name);
            if(pin==null)throw new AssertionError("missing pinned consumer origin");
            NarOtelProbe.origin(type,pin[0],pin[1]);
            System.out.println("consumer-init\t"+name+"\tPASS\t-");
        } catch(Throwable failure) {
            System.out.println("consumer-init\t"+name+"\tFAIL\t"+rootCause(failure));
            failure.printStackTrace(System.err);
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
        Map<String,String[]> origins=new LinkedHashMap<>();
        for(String line:Files.readAllLines(Path.of(args[20]))) {
            String[] fields=line.split("\t",-1);origins.put(fields[0],new String[]{fields[1],fields[2]});
        }
        ClassLoader previous=Thread.currentThread().getContextClassLoader();
        URLClassLoader instance=null;
        try {
            NarClassLoader loader=NarOtelProbe.loader("nifi-gcp-nar");
            if(!NarOtelProbe.loaders.containsKey("nifi-jetty-nar"))throw new AssertionError("Jetty parent absent");
            NarClassLoader framework=NarOtelProbe.loader("nifi-framework-nar");
            Class<?> instanceType=Class.forName("org.apache.nifi.nar.InstanceClassLoader",true,framework);
            if(instanceType.getClassLoader()!=framework)throw new AssertionError("wrong InstanceClassLoader implementation origin");
            instance=(URLClassLoader)instanceType.getConstructor(String.class,String.class,Set.class,Set.class,ClassLoader.class)
                .newInstance("cnc-bounded-qualification","offline-consumer",Set.of(),Set.of(),loader);
            Thread.currentThread().setContextClassLoader(instance);
            if(instance.getParent()!=loader || Thread.currentThread().getContextClassLoader()!=instance)throw new AssertionError("TCCL/instance model");
            System.out.println("loader-model\treal-instance-pass-through-tccl-with-jetty-parent");
            System.out.println("instance-loader-origin\t"+instanceType.getProtectionDomain().getCodeSource().getLocation());
            if(args.length>21 && args[21].equals("--consumer-init-negative")) {
                initializeConsumer("com.google.cloud.bigquery.storage.v1.TelemetryMetrics",instance,origins);
                throw new AssertionError("negative missing AttributeKey consumer path completed");
            }
            for(int i=0;i<types.length;i++)
                NarOtelProbe.origin(Class.forName(types[i],false,loader),args[2+i*2],args[3+i*2]);
            // Fail for the real ConfigUtil mismatch before claiming later coverage.
            for(String exercise:new String[]{"ConfigPropertiesProbe","OtelExercise","ConsumerBehavior"}) {
                Class<?> type=Class.forName(exercise,true,instance);
                try { type.getMethod("main",String[].class).invoke(null,(Object)new String[0]); }
                catch(java.lang.reflect.InvocationTargetException e) {
                    throw new AssertionError("real NAR consumer "+exercise,e.getCause());
                }
            }
            for(String name:origins.keySet()) initializeConsumer(name,instance,origins);
            providers(loader);
        } finally {
            Thread.currentThread().setContextClassLoader(previous);
            if(instance!=null)instance.close();
            var list=new ArrayList<>(NarOtelProbe.loaders.values());Collections.reverse(list);
            for(NarClassLoader loader:list)loader.close();
        }
    }
}
