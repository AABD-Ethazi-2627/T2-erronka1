import java.io.*;
import java.nio.ByteBuffer;
import java.util.*;
import org.apache.hadoop.io.compress.*;
import org.apache.hadoop.io.compress.snappy.*;
import org.xerial.snappy.Snappy;

/** Bounded normal-input tests. Negative half-fixes only receive compressible A. */
public class CompatibilityProbe {
  static void check(boolean b, String message) { if (!b) throw new AssertionError(message); }
  static byte[] data(int n, boolean random) {
    byte[] b = new byte[n];
    if (random) new Random(77398032L + n).nextBytes(b); else Arrays.fill(b, (byte)'A');
    return b;
  }
  static void reject(SnappyCompressor c) throws Exception {
    byte[] a = data(4096, false); c.setInput(a, 0, a.length); c.finish();
    try { c.compress(new byte[8192], 0, 8192); throw new AssertionError("half-fix accepted"); }
    catch (IllegalArgumentException e) {
      check(e.getMessage().contains("not enough space for output") && e.getMessage().contains("remaining"), "intended guard: " + e);
      System.out.println("half-fix rejected: " + e.getMessage());
    }
  }
  static void direct(SnappyCompressor c, byte[] a, int readSize, boolean chunked) throws Exception {
    c.reset(); check(c.needsInput() && !c.finished(), "reset flags");
    check(c.getBytesRead()==0 && c.getBytesWritten()==0, "reset counters");
    if (chunked) {
      for (int i=0; i<a.length; i+=137) c.setInput(a,i,Math.min(137,a.length-i));
    } else c.setInput(a,0,a.length);
    check(c.compress(new byte[0],0,0)==0, "zero output");
    c.finish(); ByteArrayOutputStream out=new ByteArrayOutputStream(); byte[] b=new byte[readSize+4];
    for (int i=0; !c.finished() && i<100000; i++) {
      Arrays.fill(b,(byte)0x55); int n=c.compress(b,2,readSize);
      check(b[0]==0x55 && b[b.length-1]==0x55,"output offsets"); out.write(b,2,n);
    }
    check(c.finished(), "bounded completion");
    byte[] encoded=out.toByteArray();
    check(Arrays.equals(a, a.length==0 ? encoded : Snappy.uncompress(encoded)), "direct roundtrip " + a.length);
    check(c.getBytesRead()==a.length && c.getBytesWritten()==encoded.length,"counters");
    check(c.compress(b,0,b.length)==0 && c.finished(),"post finish");
  }
  static void saved(byte[] a) throws Exception {
    SnappyCompressor c = new SnappyCompressor(4096);
    c.setInput(a,0,a.length); check(!c.needsInput(),"saved input"); c.finish();
    ByteArrayOutputStream decoded = new ByteArrayOutputStream(); long written=0;
    byte[] b=new byte[8192];
    for(int i=0; !c.finished() && i<100; i++) {
      int n=c.compress(b,0,b.length); written+=n;
      if(n>0) decoded.write(Snappy.uncompress(Arrays.copyOf(b,n)));
    }
    check(c.finished() && Arrays.equals(a,decoded.toByteArray()),"saved multiblock");
    check(c.getBytesRead()==a.length && c.getBytesWritten()==written,"saved counters");
    c.reset(); direct(c,data(4096,true),7,false);
  }
  static void streams(byte[] a) throws Exception {
    ByteArrayOutputStream sink = new ByteArrayOutputStream();
    // Actual Hadoop block framing and actual compressor/decompressor, explicit instances.
    try (BlockCompressorStream out = new BlockCompressorStream(sink,new SnappyCompressor(4096),4096,4096/6+32)) {
      for(int i=0;i<a.length;i+=173) out.write(a,i,Math.min(173,a.length-i));
      out.finish();
    }
    ByteArrayOutputStream decoded=new ByteArrayOutputStream();
    try (BlockDecompressorStream in=new BlockDecompressorStream(new ByteArrayInputStream(sink.toByteArray()),new SnappyDecompressor(4096),4096)) {
      byte[] b=new byte[113]; int n; int loops=0;
      while((n=in.read(b,0,b.length))!=-1) { check(++loops<100000,"read bound"); decoded.write(b,0,n); }
    }
    check(Arrays.equals(a,decoded.toByteArray()),"Hadoop framed roundtrip " + a.length);
  }
  public static void main(String[] args) throws Exception {
    if(args[0].equals("reject")) { reject(new SnappyCompressor(4096)); return; }
    SnappyCompressor c=new SnappyCompressor(4096); int cases=0;
    for(int n:new int[]{0,1,2,31,32,137,4095,4096}) for(boolean random:new boolean[]{false,true})
      for(int chunk:new int[]{1,7,8192}) { direct(c,data(n,random),chunk,true); cases++; }
    for(int n:new int[]{0,1,4095,4096,4097,8192,16399,65536})
      for(boolean random:new boolean[]{false,true}) { streams(data(n,random)); cases++; }
    for(int n:new int[]{4097,8192,16399}) for(boolean random:new boolean[]{false,true}) { saved(data(n,random)); cases++; }
    c.reinit(null); check(c.getBytesRead()==0 && c.needsInput(),"reinit"); c.end();
    // Preserved security behavior, only normal input; fixed version's guard rejects before native writes.
    if(args.length>1 && args[1].equals("guard")) {
      ByteBuffer input=ByteBuffer.allocateDirect(4096); input.put(data(4096,false)).flip();
      for(int capacity:new int[]{4096,Snappy.maxCompressedLength(4096)}) {
        ByteBuffer output=ByteBuffer.allocateDirect(capacity);
        if(capacity>4096) output.limit(0);
        try { Snappy.compress(input,output); throw new AssertionError("security guard missing"); }
        catch(IllegalArgumentException e) { check(e.getMessage().contains("not enough space for output"),"guard message"); }
      }
      System.out.println("official fixed Snappy output-space guards PASS");
    }
    System.out.println("PASS " + cases + " direct/framed cases, reset/reuse/counters/chunking");
  }
}
