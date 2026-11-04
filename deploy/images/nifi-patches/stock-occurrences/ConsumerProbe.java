import java.io.*;
import java.nio.*;
import java.util.*;
import org.apache.kafka.common.compress.Compression;
import org.apache.kafka.common.utils.*;
import org.xerial.snappy.Snappy;
import com.google.common.jimfs.*;
import java.nio.file.*;

/** Normal, safely bounded inputs only. Real Kafka codec, isolated classpath. */
public class ConsumerProbe {
  static void check(boolean ok, String m) { if (!ok) throw new AssertionError(m); }
  public static void main(String[] args) throws Exception {
    try (var fs = Jimfs.newFileSystem(Configuration.unix())) {
      Path file = fs.getPath("/normal.txt");
      Files.writeString(file, "NiFi Guava consumer");
      check(Files.readString(file).equals("NiFi Guava consumer"), "Jimfs Guava");
    }
    System.out.println("Jimfs Guava normal filesystem PASS");
    byte[] data = "NiFi normal bounded compression payload 世界".repeat(100).getBytes("UTF-8");
    for (String type : List.of("snappy", "lz4")) {
      var codec = Compression.of(type).build();
      var target = new ByteBufferOutputStream(ByteBuffer.allocate(32768));
      try (var out = codec.wrapForOutput(target, (byte)2)) {out.write(data);}
      ByteBuffer bytes = target.buffer(); bytes.flip();
      try (var buffers = BufferSupplier.create(); var in = codec.wrapForInput(bytes, (byte)2, buffers)) {
        check(Arrays.equals(data, in.readAllBytes()), "Kafka " + type);
      }
      System.out.println("Kafka " + type + " normal roundtrip PASS");
    }
    // Respect the stricter maxCompressedLength precondition on BOTH versions.
    byte[] compressed = new byte[Snappy.maxCompressedLength(data.length)];
    int size = Snappy.rawCompress(data, 0, data.length, compressed, 0);
    check(Arrays.equals(data, Snappy.uncompress(Arrays.copyOf(compressed, size))), "rawCompress");
    var src = ByteBuffer.allocateDirect(data.length); src.put(data).flip();
    var dst = ByteBuffer.allocateDirect(Snappy.maxCompressedLength(data.length));
    Snappy.compress(src, dst);
    var decoded = ByteBuffer.allocateDirect(data.length); Snappy.uncompress(dst, decoded);
    byte[] roundtrip = new byte[decoded.remaining()]; decoded.get(roundtrip);
    check(Arrays.equals(data, roundtrip), "direct buffer");
    System.out.println("Snappy maxCompressedLength array/direct PASS");
  }
}
