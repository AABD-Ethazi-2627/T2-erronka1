import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Exact installed Jetty WebInfConfiguration, no server, servlet or network start. */
public class JettyWarProbe {
    static Object call(Object target, String name, Class<?>[] types, Object... values) throws Exception {
        try { return target.getClass().getMethod(name,types).invoke(target,values); }
        catch(InvocationTargetException e) { throw new AssertionError(name,e.getCause()); }
    }
    static Path origin(Class<?> type) throws Exception {
        return Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
    }
    public static void main(String[] args) throws Exception {
        ClassLoader previous=Thread.currentThread().getContextClassLoader();
        try { execute(args); }
        finally {
            Thread.currentThread().setContextClassLoader(previous);
            for(var nar:NarProbe.loaders.values())nar.close();
        }
    }
    static void execute(String[] args) throws Exception {
        NarProbe.root=Path.of(args[0]);
        for(String line:Files.readAllLines(Path.of(args[1]))) {
            String[] fields=line.split("\t",-1);NarProbe.parents.put(fields[0],fields[1]);
        }
        String id=args[2], family=args[4], version=args[5], defining=args[6];
        Path war=Path.of(args[3]);
        ClassLoader parent=NarProbe.loader(id);
        Class<?> contextType=Class.forName("org.eclipse.jetty.ee11.webapp.WebAppContext",true,parent);
        Object context=contextType.getConstructor(String.class,String.class).newInstance(war.toString(),"/cnc-component-proof");
        Path temporary=war.resolveSibling(war.getFileName()+"-jetty-"+(Boolean.parseBoolean(args[7])?"negative":"normal"));
        Files.createDirectory(temporary);
        call(context,"setTempDirectory",new Class<?>[]{java.io.File.class},temporary.toFile());
        Class<?> loaderType=Class.forName("org.eclipse.jetty.ee.webapp.WebAppClassLoader",true,parent);
        Class<?> contract=Class.forName("org.eclipse.jetty.ee.webapp.WebAppClassLoader$Context",true,parent);
        ClassLoader loader=(ClassLoader)loaderType.getConstructor(ClassLoader.class,contract).newInstance(parent,context);
        call(context,"setClassLoader",new Class<?>[]{ClassLoader.class},loader);
        // Same loadWar defaults as official NiFi2.12 JettyServer; no parent-priority override.
        if(!Boolean.FALSE.equals(call(context,"isParentLoaderPriority",new Class<?>[]{})))throw new AssertionError("unexpected Jetty WAR parent priority");
        if(Boolean.parseBoolean(args[7]))call(context,"setParentLoaderPriority",new Class<?>[]{boolean.class},true);
        Class<?> configType=Class.forName("org.eclipse.jetty.ee11.webapp.WebInfConfiguration",true,parent);
        Object configuration=configType.getConstructor().newInstance();
        configType.getMethod("preConfigure",contextType).invoke(configuration,context);
        configType.getMethod("configure",contextType).invoke(configuration,context);
        Thread.currentThread().setContextClassLoader(loader);
        String ns=family.equals("3")?"tools.jackson":"com.fasterxml.jackson";
        Class<?> mapperType=Class.forName(ns+".databind.json.JsonMapper",true,loader);
        Class<?> core=Class.forName(ns+".core.json.PackageVersion",true,loader);
        Class<?> db=Class.forName(ns+".databind.cfg.PackageVersion",true,loader);
        if(!core.getField("VERSION").get(null).toString().equals(version)||!db.getField("VERSION").get(null).toString().equals(version))throw new AssertionError("unexpected effective Jackson version");
        Path expected=defining.equals("WAR")?war.resolve("WEB-INF/lib/jackson-databind-"+version+".jar"):NarProbe.root.resolve(defining).resolve("NAR-INF/bundled-dependencies/jackson-databind-"+version+".jar");
        ClassLoader expectedLoader=defining.equals("WAR")?loader:NarProbe.loader(defining);
        if(mapperType.getClassLoader()!=expectedLoader||!origin(mapperType).equals(expected.toRealPath()))throw new AssertionError("Jetty Jackson origin mismatch: "+origin(mapperType)+" expected "+expected);
        Path expectedCore=defining.equals("WAR")?war.resolve("WEB-INF/lib/jackson-core-"+version+".jar"):NarProbe.root.resolve(defining).resolve("NAR-INF/bundled-dependencies/jackson-core-"+version+".jar");
        if(core.getClassLoader()!=expectedLoader||db.getClassLoader()!=expectedLoader||!origin(core).equals(expectedCore.toRealPath())||!origin(db).equals(expected.toRealPath()))throw new AssertionError("Jetty core/databind origin mismatch");
        Object builder=mapperType.getMethod("builder").invoke(null);
        Object mapper=call(builder,"build",new Class<?>[]{});
        Object decoded=call(mapper,"readValue",new Class<?>[]{String.class,Class.class},"{\"value\":7,\"state\":\"ok\"}",Map.class);
        if(!(decoded instanceof Map<?,?> map)||!Integer.valueOf(7).equals(map.get("value"))||!"ok".equals(map.get("state")))throw new AssertionError("WAR mapper read mismatch");
        String encoded=(String)call(mapper,"writeValueAsString",new Class<?>[]{Object.class},decoded);
        Object again=call(mapper,"readValue",new Class<?>[]{String.class,Class.class},encoded,Map.class);
        if(!decoded.equals(again))throw new AssertionError("WAR mapper roundtrip mismatch");
        for(int i=8;i<args.length;i++) {
            Class<?> consumer=Class.forName(args[i],true,loader);
            Path actual=origin(consumer);
            if(!actual.startsWith(war.resolve("WEB-INF/classes").toRealPath()))throw new AssertionError("consumer not from WAR classes");
            System.out.println("consumer-initialized\t"+consumer.getName()+"\t"+actual);
            if(consumer.getSimpleName().equals("ObjectMapperResolver")) {
                Object resolver=consumer.getConstructor().newInstance();
                Object actualMapper=call(resolver,"getContext",new Class<?>[]{Class.class},Map.class);
                Object actualMap=call(actualMapper,"readValue",new Class<?>[]{String.class,Class.class},"{\"probe\":true}",Map.class);
                if(!Boolean.TRUE.equals(((Map<?,?>)actualMap).get("probe")))throw new AssertionError("actual resolver Jackson call mismatch");
                System.out.println("actual-resolver-read\t"+consumer.getName()+"\tPASS");
            }
        }
        System.out.println("jetty-war-roundtrip\t"+id+"\t"+family+"\t"+version+"\t"+defining+"\t"+origin(mapperType));
        if(mapper instanceof AutoCloseable closeable)closeable.close();
        ((AutoCloseable)loader).close();
    }
}
