import java.io.*;
import java.lang.management.ManagementFactory;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.common.collect.MapMaker;
import com.rabbitmq.client.impl.*;
import com.rabbitmq.tools.json.JSONReader;
import net.jpountz.lz4.*;
import org.xerial.snappy.*;

/** Bounded component probes; no broker, NiFi, hostile native calls or OOM tests. */
public class LibraryProbe {
  static void check(boolean v, String s) { if (!v) throw new AssertionError(s); }
  interface Action { void run() throws Exception; }
  static void rejects(Action a) throws Exception {
    try { a.run(); } catch (IOException | IllegalArgumentException | IndexOutOfBoundsException e) { return; }
    throw new AssertionError("Malformed input accepted");
  }
  static byte[] serialize(Object o) throws Exception {
    var b=new ByteArrayOutputStream(); try(var s=new ObjectOutputStream(b)){s.writeObject(o);} return b.toByteArray();
  }
  static Object deserialize(byte[] b, boolean forged) throws Exception {
    try(var s=new ObjectInputStream(new ByteArrayInputStream(b)) {
      @Override public int readInt() throws IOException {int i=super.readInt();return forged?100_000:i;}
    }) {return s.readObject();}
  }
  static long allocated() {return ((com.sun.management.ThreadMXBean)ManagementFactory.getThreadMXBean()).getThreadAllocatedBytes(Thread.currentThread().threadId());}
  static void guava(boolean fixed) throws Exception {
    for(String type:List.of("CompactHashMap","CompactHashSet","MapMakerInternalMap")) {
      Object o;
      if(type.equals("MapMakerInternalMap")) {var m=new MapMaker().weakKeys().makeMap();m.put("k","v");o=m;}
      else {var c=Class.forName("com.google.common.collect."+type);var ctor=c.getDeclaredConstructor();ctor.setAccessible(true);o=ctor.newInstance();
        if(o instanceof Map m)m.put("k","v");else ((Set)o).add("k");}
      byte[] b=serialize(o);check(deserialize(b,false)!=null,"normal serialization");
      // Warm class initialization. A 100k size costs at most a few MiB in controls.
      try {deserialize(b,true);}catch(IOException expected){}
      long start=allocated();try {deserialize(b,true);}catch(IOException expected){}
      long used=allocated()-start;System.out.println(type+" forged allocated="+used);
      check(fixed ? used<200_000 : used>200_000,"deserialization allocation control: "+type);
    }
  }
  static void rabbit(boolean fixed, String mode) throws Exception {
    if(mode.equals("comment")){try {new JSONReader().read("// eof");}catch(IllegalStateException expected){}System.out.println("comment terminated");return;}
    check(((Map)new JSONReader().read("{\"ok\":1}")).containsKey("ok"),"JSON roundtrip");
    var out=new ByteArrayOutputStream();new ValueWriter(new DataOutputStream(out)).writeShortstr("Kaixo 世界");
    check(new ValueReader(new DataInputStream(new ByteArrayInputStream(out.toByteArray()))).readShortstr().equals("Kaixo 世界"),"UTF8 roundtrip");
    byte[] bad=new byte[256];bad[0]=(byte)255;Arrays.fill(bad,1,256,(byte)0x80);
    var reader=new ValueReader(new DataInputStream(new ByteArrayInputStream(bad)));
    if(fixed) {
      String decoded=reader.readShortstr();check(decoded.getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=255,"bounded UTF8");
      new ValueWriter(new DataOutputStream(new ByteArrayOutputStream())).writeShortstr(decoded);
      if(!mode.equals("shortstr")) for(String input:List.of("\"unfinished", "'unfinished", "{\"k\":\"unfinished")) {
        try {new JSONReader().read(input);throw new AssertionError("truncated string accepted");}catch(IllegalStateException expected){}
      }
    } else {
      String s=reader.readShortstr();rejects(()->new ValueWriter(new DataOutputStream(new ByteArrayOutputStream())).writeShortstr(s));
    }
    System.out.println("Rabbit JSON and shortstr PASS");
  }
  static void lz4(boolean fixed) throws Exception {
    byte[] data="NiFi bounded roundtrip".repeat(128).getBytes(java.nio.charset.StandardCharsets.UTF_8);
    var out=new ByteArrayOutputStream();try(var s=new LZ4BlockOutputStream(out)){s.write(data);}
    try(var s=new LZ4BlockInputStream(new ByteArrayInputStream(out.toByteArray()))){check(Arrays.equals(data,s.readAllBytes()),"block roundtrip");}
    // Empty blocks are Java decoding only, capped at 210 kB input.
    byte[] empty=new byte[21];System.arraycopy("LZ4Block".getBytes(java.nio.charset.StandardCharsets.US_ASCII),0,empty,0,8);empty[8]=0x10;
    out.reset();for(int i=0;i<10_000;i++)out.write(empty);
    try(var s=new LZ4BlockInputStream(new ByteArrayInputStream(out.toByteArray()),false)) {
      try {check(s.read()==-1,"empty blocks EOF");check(fixed,"old recursion unexpectedly survived");}
      catch(StackOverflowError e){check(!fixed,"fixed stack overflow");System.out.println("old empty-block stack control observed");}
    }
    out.reset();try(var s=new LZ4FrameOutputStream(out,LZ4FrameOutputStream.BLOCKSIZE.SIZE_4MB)){}
    byte[] frame=out.toByteArray();out.reset();for(int i=0;i<8;i++)out.write(frame);byte[] frames=out.toByteArray();
    long before=allocated();try(var s=new LZ4FrameInputStream(new ByteArrayInputStream(frames))){check(s.read()==-1,"empty frames EOF");}
    long used=allocated()-before;System.out.println("8 empty frames allocated="+used);check(fixed?used<12_000_000:used>50_000_000,"frame allocation control");
    rejects(()->{try(var s=new LZ4FrameInputStream(new ByteArrayInputStream(new byte[]{1,2,3,4}))){s.read();}});
    // Normal JNI initialization in a dedicated private tmp dir. Never race/symlink attack.
    var nativeFactory=LZ4Factory.nativeInstance();byte[] compressed=nativeFactory.fastCompressor().compress(data);
    check(Arrays.equals(data,nativeFactory.fastDecompressor().decompress(compressed,data.length)),"JNI normal roundtrip");
    try(var files=Files.list(Path.of(System.getProperty("java.io.tmpdir")))) {
      var names=files.map(p->p.getFileName().toString()).toList();System.out.println("extracted native files="+names);
      if(fixed)check(names.stream().anyMatch(n->n.startsWith("liblz4-java-")) && names.stream().noneMatch(n->n.endsWith(".lck")),"exclusive extraction file");
    }
  }
  static void snappy(boolean fixed) throws Exception {
    byte[] data="bounded normal JNI roundtrip".repeat(128).getBytes(java.nio.charset.StandardCharsets.UTF_8);
    check(Arrays.equals(data,Snappy.uncompress(Snappy.compress(data))),"snappy bytes");
    int[] ints={1,2,3};check(Arrays.equals(ints,Snappy.uncompressIntArray(Snappy.compress(ints))),"snappy ints");
    var out=new ByteArrayOutputStream();try(var s=new SnappyOutputStream(out)){s.write(data);}try(var s=new SnappyInputStream(new ByteArrayInputStream(out.toByteArray()))){check(Arrays.equals(data,s.readAllBytes()),"snappy stream");}
    if(fixed) {
      // Deterministic Java precondition checks only on corrected upstream code.
      byte[] three=Snappy.compress(new byte[]{1,2,3});
      rejects(()->Snappy.uncompressIntArray(three));rejects(()->Snappy.uncompressLongArray(three));rejects(()->Snappy.uncompressShortArray(three));
      rejects(()->Snappy.arrayCopy(new byte[4],-1,1,new byte[4],0));
      rejects(()->Snappy.arrayCopy(new byte[4],0,5,new byte[4],0));
      // Declared length 100000 from a 3-byte header; well under process heap even if regression.
      rejects(()->Snappy.uncompress(new byte[]{(byte)0xa0,(byte)0x8d,6}));
      rejects(()->{try(var s=new SnappyOutputStream(new ByteArrayOutputStream())){s.write(new int[2],1,2);}});
    }
    System.out.println("Snappy normal JNI / fixed Java bounds PASS; hostile old JNI NOT executed");
  }
  public static void main(String[] args) throws Exception {
    boolean fixed=args[1].equals("fixed");switch(args[0]) {
      case "guava":guava(fixed);break;case "rabbit":rabbit(fixed,args.length>2?args[2]:"");break;
      case "lz4":lz4(fixed);break;case "snappy":snappy(fixed);break;default:throw new IllegalArgumentException();
    }
    System.out.println("PASS "+Arrays.toString(args));
  }
}
