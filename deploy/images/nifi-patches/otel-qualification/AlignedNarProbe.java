import java.nio.file.*;
import java.util.*;
import org.apache.nifi.nar.NarClassLoader;

/** Uses the installed actual loader; no NiFi server, scheduling or exporter. */
public class AlignedNarProbe {
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
            // This path discriminates the real 1.62 SDK -> API internal ABI break.
            for(String exercise:new String[]{"ConfigPropertiesProbe","OtelExercise"}) {
                Class<?> type=Class.forName(exercise,true,loader);
                try { type.getMethod("main",String[].class).invoke(null,(Object)new String[0]); }
                catch(java.lang.reflect.InvocationTargetException e) {
                    throw new AssertionError("real NAR consumer "+exercise,e.getCause());
                }
            }
            for(int i=20;i<args.length;i++) {
                Class<?> type=Class.forName(args[i],false,loader);
                if(!(type.getClassLoader() instanceof NarClassLoader))throw new AssertionError("flat consumer");
                System.out.println("actual-consumer="+type.getName()+" origin="+type.getProtectionDomain().getCodeSource().getLocation());
            }
        } finally {
            var list=new ArrayList<>(NarOtelProbe.loaders.values());Collections.reverse(list);
            for(NarClassLoader loader:list)loader.close();
        }
    }
}
