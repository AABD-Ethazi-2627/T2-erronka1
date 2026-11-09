/* Uses installed PluginsLoader on the boot
 * module path; does not instantiate plugins, start a node or attach an agent.
 * Entitlement instrumentation is not enabled: this is loader/component evidence. */
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.elasticsearch.plugins.PluginsLoader;
import org.elasticsearch.plugins.PluginBundle;

public class EsLoaderProbe {
    static final Set<String> CLOSURE=Set.of("apm", "esql-datasource-gcs", "repository-gcs",
        "lang-painless", "workload-identity", "x-pack-autoscaling", "x-pack-core",
        "x-pack-encryption", "x-pack-esql", "x-pack-esql-core", "x-pack-ml");
    static final Properties PINS=new Properties();
    static final Map<String,String> CORE=Map.of(
        "api", "io.opentelemetry.api.OpenTelemetry",
        "context", "io.opentelemetry.context.Context",
        "common", "io.opentelemetry.common.ComponentLoader",
        "sdk", "io.opentelemetry.sdk.OpenTelemetrySdk",
        "sdk-common", "io.opentelemetry.sdk.common.Clock",
        "sdk-trace", "io.opentelemetry.sdk.trace.SdkTracerProvider",
        "sdk-metrics", "io.opentelemetry.sdk.metrics.SdkMeterProvider",
        "sdk-logs", "io.opentelemetry.sdk.logs.SdkLoggerProvider",
        "sdk-extension-autoconfigure-spi", "io.opentelemetry.sdk.autoconfigure.spi.ConfigProperties");
    static String sha(Path path)throws Exception{
        var d=MessageDigest.getInstance("SHA-256");
        try(var in=Files.newInputStream(path)){byte[] b=new byte[65536];int n;
            while((n=in.read(b))!=-1)d.update(b,0,n);}
        return HexFormat.of().formatHex(d.digest());
    }
    static Object call(ClassLoader loader,String type,Object receiver,String method,Class<?>[] parameters,Object...args)throws Exception{
        return Class.forName(type,true,loader).getMethod(method,parameters).invoke(receiver,args);
    }
    static void components(ClassLoader loader)throws Exception{
        var none=new Class<?>[0];
        for(var signal:List.of("trace", "metrics", "logs")){
            String provider=switch(signal){case "trace" -> "SdkTracerProvider";case "metrics" -> "SdkMeterProvider";default -> "SdkLoggerProvider";};
            String type="io.opentelemetry.sdk."+signal+"."+provider;
            Object builder=call(loader,type,null,"builder",none);
            Object instance=call(loader,type+"Builder",builder,"build",none);
            Object instrument=call(loader,type,instance,"get",new Class<?>[]{String.class},"cnc.synthetic");
            if(signal.equals("trace")){
                Object spanBuilder=call(loader,"io.opentelemetry.api.trace.Tracer",instrument,"spanBuilder",new Class<?>[]{String.class},"synthetic");
                Object span=call(loader,"io.opentelemetry.api.trace.SpanBuilder",spanBuilder,"startSpan",none);
                Object scope=call(loader,"io.opentelemetry.api.trace.Span",span,"makeCurrent",none);
                call(loader,"io.opentelemetry.context.Scope",scope,"close",none);
                call(loader,"io.opentelemetry.api.trace.Span",span,"end",none);
            }else if(signal.equals("metrics")){
                Object cb=call(loader,"io.opentelemetry.api.metrics.Meter",instrument,"counterBuilder",new Class<?>[]{String.class},"cnc.synthetic");
                Object counter=call(loader,"io.opentelemetry.api.metrics.LongCounterBuilder",cb,"build",none);
                call(loader,"io.opentelemetry.api.metrics.LongCounter",counter,"add",new Class<?>[]{long.class},7L);
            }else{
                Object record=call(loader,"io.opentelemetry.api.logs.Logger",instrument,"logRecordBuilder",none);
                call(loader,"io.opentelemetry.api.logs.LogRecordBuilder",record,"setBody",new Class<?>[]{String.class},"synthetic");
                call(loader,"io.opentelemetry.api.logs.LogRecordBuilder",record,"emit",none);
            }
            call(loader,type,instance,"close",none);
            System.out.println("COMPONENT\t"+signal+"\tpass");
        }
        // Build and close exporters without exporting a payload or opening an endpoint.
        for(var signal:List.of("trace.OtlpHttpSpanExporter", "metrics.OtlpHttpMetricExporter", "logs.OtlpHttpLogRecordExporter")){
            String type="io.opentelemetry.exporter.otlp.http."+signal;
            Object builder=call(loader,type,null,"builder",none);
            Object exporter=call(loader,type+"Builder",builder,"build",none);
            call(loader,type,exporter,"close",none);
            System.out.println("EXPORTER-BUILD-CLOSE\t"+signal+"\tpass");
        }
        // ES uses gRPC with LATEST exporter self-metrics. Default HTTP builders
        // do not exercise this internal SDK/exporter ABI (SemConvAttributes).
        var telemetryType=Class.forName("io.opentelemetry.sdk.common.InternalTelemetryVersion",true,loader);
        Object latest=telemetryType.getField("LATEST").get(null);
        for(var signal:List.of("metrics.OtlpGrpcMetricExporter", "trace.OtlpGrpcSpanExporter", "logs.OtlpGrpcLogRecordExporter")){
            String type="io.opentelemetry.exporter.otlp."+signal;
            // getMethod enumerates optional ManagedChannel overloads, although
            // ES's OkHttp sender needs no grpc-java ManagedChannel. Resolve only
            // the exact public descriptors used by ES, without adding grpc-java.
            var lookup=java.lang.invoke.MethodHandles.publicLookup();
            var exporterType=Class.forName(type,true,loader);
            var builderType=Class.forName(type+"Builder",true,loader);
            try{
                Object builder=lookup.findStatic(exporterType,"builder",java.lang.invoke.MethodType.methodType(builderType)).invoke();
                lookup.findVirtual(builderType,"setInternalTelemetryVersion",java.lang.invoke.MethodType.methodType(builderType,telemetryType)).invoke(builder,latest);
                Object exporter=lookup.findVirtual(builderType,"build",java.lang.invoke.MethodType.methodType(exporterType)).invoke(builder);
                lookup.findVirtual(exporterType,"close",java.lang.invoke.MethodType.methodType(void.class)).invoke(exporter);
            }catch(Throwable error){throw new IllegalStateException("gRPC LATEST probe",error);}
            System.out.println("GRPC-LATEST-BUILD-CLOSE\t"+signal+"\tpass");
        }
    }
    static void origin(String realm,String name,ClassLoader loader,String expected)throws Exception{
        var type=Class.forName(name,false,loader);
        var path=Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI());
        if(!path.getFileName().toString().equals(expected))throw new AssertionError("wrong loaded JAR: "+name);
        boolean moduleOk=realm.equals("apm")
            ? Objects.equals(type.getModule().getName(),PINS.getProperty("module."+expected))
            : !type.getModule().isNamed();
        if(!sha(path).equals(PINS.getProperty("sha."+expected)) || !moduleOk)
            throw new AssertionError("loaded hash/module identity mismatch: "+name);
        System.out.println("ORIGIN\t"+realm+"\t"+name+"\t"+type.getModule().getName()+"\t"+path+"\t"+sha(path));
    }
    public static void main(String[] args)throws Exception{
        if(args.length!=3||!Set.of("current","sdk-six","aligned").contains(args[1]))
            throw new IllegalArgumentException("home + current/sdk-six/aligned + origin pins required");
        try(var in=Files.newInputStream(Path.of(args[2]))){PINS.load(in);}
        Path home=Path.of(args[0]);String variant=args[1];
        // Same public logging initialization used by the server bootstrap.
        // PluginsLoader initializes ModuleQualifiedExportsService, which logs
        // through ES LoggerFactory rather than Log4j's independent provider.
        org.elasticsearch.common.logging.LogConfigurator.configureESLogging();
        var all=PluginsLoader.loadModulesBundles(home.resolve("modules"),false);
        Set<PluginBundle> selected=new LinkedHashSet<>();
        for(var b:all)if(CLOSURE.contains(b.pluginDescriptor().getName()))selected.add(b);
        if(selected.size()!=CLOSURE.size())throw new AssertionError("missing measured loader closure");
        // Calls the installed implementation, including normal jar-hell checks,
        // qualified export handling, SPI boundaries and one-loader JPMS layers.
        var actual=PluginsLoader.createPluginsLoader(selected,Set.of(),Map.of());
        var layers=actual.pluginLayers().toList();
        for(var realm:List.of("apm","repository-gcs","esql-datasource-gcs")){
            var layer=layers.stream().filter(l->l.pluginBundle().pluginDescriptor().getName().equals(realm)).findFirst().orElseThrow();
            var loader=layer.pluginClassLoader();
            String classname=layer.pluginBundle().pluginDescriptor().getClassname();
            var consumer=Class.forName(classname,false,loader);
            System.out.println("CONSUMER-LOAD\t"+realm+"\t"+classname+"\t"+consumer.getModule().getName());
            for(var a:List.of("api","context","common"))origin(realm,CORE.get(a),loader,"opentelemetry-"+a+"-1.67.0.jar");
            if(!realm.equals("apm"))continue;
            if(!consumer.getModule().isNamed()||!consumer.getModule().getName().equals("org.elasticsearch.telemetry.apm"))
                throw new AssertionError("APM escaped named module");
            for(var entry:CORE.entrySet())if(!List.of("api","context","common").contains(entry.getKey()))
                origin(realm,entry.getValue(),loader,"opentelemetry-"+entry.getKey()+"-"+(variant.equals("current")?"1.62.0":"1.67.0")+".jar");
            var config=Class.forName("io.opentelemetry.sdk.autoconfigure.spi.internal.DefaultConfigProperties",true,loader);
            try{
                var properties=config.getMethod("createFromMap",Map.class).invoke(null,Map.of("cnc.count","7"));
                var iface=Class.forName(CORE.get("sdk-extension-autoconfigure-spi"),false,loader);
                Object value=iface.getMethod("getInt",String.class).invoke(properties,"cnc.count");
                if(!Integer.valueOf(7).equals(value))throw new AssertionError("SDK configuration conversion");
                System.out.println("SDK-CONFIG\tpass");
            }catch(java.lang.reflect.InvocationTargetException error){
                Throwable cause=error.getCause();
                if(!variant.equals("current")||!(cause instanceof NoClassDefFoundError)
                    ||!String.valueOf(cause.getMessage()).contains("io/opentelemetry/api/internal/ConfigUtil"))throw error;
                System.out.println("SDK-CONFIG\tobserved-current-ConfigUtil-failure");
            }
            // Loading controls only; initialization/exporter operations remain separate.
            for(var name:List.of("io.opentelemetry.exporter.otlp.http.trace.OtlpHttpSpanExporter",
                "io.opentelemetry.exporter.otlp.http.metrics.OtlpHttpMetricExporter",
                "io.opentelemetry.exporter.otlp.http.logs.OtlpHttpLogRecordExporter")){
                Class.forName(name,false,loader);System.out.println("EXPORTER-LOAD\t"+name);
            }
            components(loader);
        }
        System.out.println("STATUS\tloader-components-only\treplacement=null\truntime_approved=false");
    }
}
